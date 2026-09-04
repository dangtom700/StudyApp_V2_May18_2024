#ifndef SQL_HPP
#define SQL_HPP

#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sqlite3.h>

/**
 * Checked SQLite execution, shared by every stage.
 *
 * The rule here is that a statement never fails quietly. Return codes from
 * sqlite3_prepare_v2 and sqlite3_step used to go unchecked in the topic stages,
 * so a statement that inserted nothing -- a missing table, a violated CHECK --
 * still let the stage print that it had finished.
 */
namespace SQL
{
    /**
     * Execute one or more statements that take no parameters.
     *
     * @throws std::runtime_error if the batch fails, after printing the SQLite
     *         message and the offending SQL.
     */
    inline void execute(sqlite3 *db, const std::string &sql)
    {
        char *error_message = nullptr;
        if (sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &error_message) != SQLITE_OK)
        {
            std::cerr << "Error executing SQL: " << (error_message ? error_message : "unknown error")
                      << std::endl
                      << "SQL: " << sql << std::endl;
            sqlite3_free(error_message);
            throw std::runtime_error("SQL execution failed");
        }
    }

    /**
     * Prepare, bind, step and finalize a single parameterised statement.
     *
     * @param bind Called once with the prepared statement to bind its parameters.
     * @return The number of rows the statement changed.
     *
     * @throws std::runtime_error if preparation or execution fails.
     */
    inline int execute_prepared(sqlite3 *db,
                                const std::string &sql,
                                const std::function<void(sqlite3_stmt *)> &bind)
    {
        sqlite3_stmt *stmt = nullptr;
        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK)
        {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl
                      << "SQL: " << sql << std::endl;
            throw std::runtime_error("SQL preparation failed");
        }

        bind(stmt);

        const int rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE && rc != SQLITE_ROW)
        {
            std::cerr << "Error executing statement: " << sqlite3_errmsg(db) << std::endl
                      << "SQL: " << sql << std::endl;
            sqlite3_finalize(stmt);
            throw std::runtime_error("SQL execution failed");
        }

        sqlite3_finalize(stmt);
        return sqlite3_changes(db);
    }
}

#endif // SQL_HPP
