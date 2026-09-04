#ifndef SCHEMA_HPP
#define SCHEMA_HPP

#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <sqlite3.h>

#include "env.hpp"
#include "sql.hpp"

/**
 * Table lifecycle for the C++ stages.
 *
 * Every CREATE TABLE / CREATE INDEX lives in config/schema.sql and nowhere else;
 * src/modules/schema.py loads the same file, so the two sides cannot drift.
 * A stage that resets its output drops the tables it owns and re-applies the
 * file -- it never carries DDL text of its own.
 */
namespace SCHEMA
{
    /**
     * Read config/schema.sql.
     *
     * @throws std::runtime_error if the file is missing or unreadable. It ships
     *         with the source, so its absence means the program is being run
     *         from the wrong directory (every ENV_HPP path is relative to the
     *         project root) rather than something recoverable.
     */
    inline std::string load_schema_text()
    {
        const std::filesystem::path &path = ENV_HPP::schema_path;
        std::ifstream in(path);
        if (!in)
        {
            throw std::runtime_error(
                "Cannot read schema file: " + path.string() +
                "\nRun the pipeline from the project root, where config/schema.sql lives.");
        }

        std::ostringstream buffer;
        buffer << in.rdbuf();
        return buffer.str();
    }

    /**
     * Create every pipeline table and index that does not exist yet.
     *
     * Idempotent -- every statement in the file is IF NOT EXISTS -- so a stage
     * can call this on entry without caring what ran before it.
     *
     * @throws std::runtime_error if the schema fails to apply.
     */
    inline void apply(sqlite3 *db)
    {
        const std::string sql = load_schema_text();

        char *error_message = nullptr;
        if (sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &error_message) != SQLITE_OK)
        {
            const std::string detail = error_message ? error_message : "unknown error";
            sqlite3_free(error_message);
            std::cerr << "Error applying " << ENV_HPP::schema_path.string() << ": " << detail << std::endl;
            throw std::runtime_error("Schema application failed");
        }
    }

    /**
     * Drop the named tables, then rebuild them from config/schema.sql.
     *
     * This is what `reset_table` means for a stage: start this stage's own
     * output over. Dropping and recreating are one call so they cannot drift
     * apart -- a drop whose matching create was edited to name a different
     * table only surfaces as a failure several statements later.
     *
     * Dropping a table also drops its indexes, which is why the re-apply is not
     * optional.
     *
     * @throws std::runtime_error if a drop or the re-apply fails.
     */
    inline void reset(sqlite3 *db, std::initializer_list<std::string> tables)
    {
        for (const std::string &table : tables)
        {
            const std::string sql = "DROP TABLE IF EXISTS " + table + ";";
            char *error_message = nullptr;
            if (sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &error_message) != SQLITE_OK)
            {
                const std::string detail = error_message ? error_message : "unknown error";
                sqlite3_free(error_message);
                std::cerr << "Error dropping " << table << ": " << detail << std::endl;
                throw std::runtime_error("Table reset failed");
            }
        }

        apply(db);
    }

    /**
     * True when the named table exists and holds at least one row.
     *
     * Emptiness counts as absence on purpose: an upstream stage that created its
     * table and then wrote nothing leaves the same hole for the stage that
     * follows, and reporting it here is far cheaper than a run that "succeeds"
     * against no data.
     */
    inline bool has_rows(sqlite3 *db, const std::string &table)
    {
        sqlite3_stmt *stmt = nullptr;
        const std::string sql =
            "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name=?);";
        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK)
            return false;

        sqlite3_bind_text(stmt, 1, table.c_str(), -1, SQLITE_TRANSIENT);
        const bool exists = (sqlite3_step(stmt) == SQLITE_ROW) && (sqlite3_column_int(stmt, 0) == 1);
        sqlite3_finalize(stmt);

        if (!exists)
            return false;

        const std::string count_sql = "SELECT EXISTS(SELECT 1 FROM \"" + table + "\" LIMIT 1);";
        if (sqlite3_prepare_v2(db, count_sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK)
            return false;

        const bool populated = (sqlite3_step(stmt) == SQLITE_ROW) && (sqlite3_column_int(stmt, 0) == 1);
        sqlite3_finalize(stmt);
        return populated;
    }

    /**
     * Check a stage's inputs before it does any work.
     *
     * Prints which input is missing and which stage produces it, then throws so
     * main() reports the failure and exits non-zero -- config/main.bat checks
     * %errorlevel% after every stage. The point is a stage that says what to run
     * next instead of aborting the process on an uncaught SQL error several
     * statements in, which is exactly how --expandTopics used to fail.
     *
     * Called before any stage opens a transaction, so throwing past the open
     * database handle cannot leave a write half-applied.
     *
     * @throws std::runtime_error if any input is missing or empty.
     */
    inline void require(sqlite3 *db,
                        std::initializer_list<std::pair<std::string, std::string>> inputs,
                        const std::string &stage)
    {
        std::vector<std::pair<std::string, std::string>> missing;
        for (const auto &input : inputs)
        {
            if (!has_rows(db, input.first))
                missing.push_back(input);
        }

        if (missing.empty())
            return;

        std::cerr << "[" << stage << "] cannot run: " << missing.size()
                  << (missing.size() == 1 ? " input is" : " inputs are")
                  << " missing or empty." << std::endl;
        for (const auto &[table, producer] : missing)
            std::cerr << "    " << table << " <- run " << producer << " first" << std::endl;

        throw std::runtime_error("missing inputs for " + stage);
    }
}

#endif // SCHEMA_HPP
