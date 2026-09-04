#ifndef FEATURE_HPP
#define FEATURE_HPP

#include <filesystem>
#include <vector>
#include <map>
#include <fstream>
#include <memory> // For smart pointers
#include <sqlite3.h>
#include <unordered_map>
#include <unordered_set>
#include <mutex>
#include <thread>
#include <nlohmann/json.hpp>
#include <time.h>
#include <chrono>
#include <algorithm>
#include <print>
#include <random>

using json = nlohmann::json;

#include "utilities.hpp"
#include "env.hpp"
#include "schema.hpp"
#include "transform.hpp"
#include "updateDB.hpp"
#include "recommend.hpp"

namespace FEATURE
{

    /**
     * Execute a SQL query on the given database.
     *
     * @param db The database to execute the query on.
     * @param sql The SQL query to execute.
     *
     * @throws std::runtime_error if the query fails with an error message.
     */
    void execute_sql(sqlite3 *db, const std::string &sql)
    {
        SQL::execute(db, sql);
    }

    /**
     * Prepare the tables a stage owns.
     *
     * The DDL itself lives in config/schema.sql -- see src/lib/schema.hpp. This
     * only expresses the stage's intent: reset_table means "start this stage's
     * output over", otherwise the tables are kept and the stage resumes into them.
     *
     * @param db          Open database handle.
     * @param owned       The tables this stage writes; dropped when reset_table.
     * @param reset_table If true, drop them before recreating from the schema.
     *
     * @throws std::runtime_error if the schema cannot be applied.
     */
    void prepare_tables(sqlite3 *db,
                        std::initializer_list<std::string> owned,
                        const bool reset_table = false)
    {
        if (reset_table)
            SCHEMA::reset(db, owned);
        else
            SCHEMA::apply(db);
    }

    /**
     * Rebuild a derived table from a query.
     *
     * Only for the --runCutoffAnalysis snapshots: their columns come from their
     * SELECT rather than from a declaration, so config/schema.sql cannot hold
     * them and every run recomputes them from scratch.
     *
     * @throws std::runtime_error if either statement fails.
     */
    void rebuild_derived(sqlite3 *db,
                         const std::string &table_name,
                         const std::string &create_sql)
    {
        execute_sql(db, "DROP TABLE IF EXISTS " + table_name + ";");
        execute_sql(db, create_sql);
    }

    /**
     * Prepare an SQL statement for execution.
     *
     * @param db The SQLite database connection.
     * @param query The SQL query to be prepared.
     * @return A prepared sqlite3_stmt object if successful, otherwise nullptr on failure.
     *
     * This function prepares an SQL statement for execution by compiling the query
     * into a byte-code program that can be executed. If the preparation fails, it
     * outputs an error message to the standard error and returns nullptr.
     */
    sqlite3_stmt *prepareStatement(sqlite3 *db, const std::string &query, const std::string &content)
    {
        sqlite3_stmt *stmt = nullptr;
        int rc = sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr);
        if (rc != SQLITE_OK)
        {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl
                      << "SQL: " << query << std::endl
                      << "Content: " << content << std::endl;
            return nullptr;
        }
        return stmt;
    }

    /**
     * Compute the relational distance of each token in the given map of strings to
     * integers and store the result in a SQLite database.
     *
     * @param filtered_files A vector of file paths to process.
     * @param show_progress If true, print progress messages to the console.
     * @param reset_table If true, reset the table before adding new data.
     * @param is_dumped If true, dump the data to a file.
     *
     * @throws std::runtime_error if the database connection or query fails.
     */
    void computeRelationalDistance(const std::vector<std::filesystem::path> &filtered_files,
                                   const bool &show_progress = true,
                                   const bool &reset_table = true,
                                   const bool &is_dumped = true,
                                   const int freq_thres = 30)
    {
        try
        {
            // Set up SQLite database connection
            sqlite3 *db;
            int exit = sqlite3_open(ENV_HPP::database_path.string().c_str(), &db);
            if (exit)
            {
                std::cerr << "Error opening SQLite database: " << sqlite3_errmsg(db) << std::endl;
                return;
            }

            // Disable synchronous mode to speed up inserts (optional)
            execute_sql(db, "PRAGMA synchronous = OFF;");

            // This stage reads JSON produced by --processWordFreq, not the database,
            // so it has no table inputs to check -- only its own outputs to prepare.
            prepare_tables(db, {"file_token", "relation_distance_filtered"}, reset_table);

            // Hoist prepared statements OUTSIDE the loop.
            // Re-calling sqlite3_prepare_v2 on every iteration re-compiles the query
            // bytecode each time — one of the most expensive SQLite anti-patterns.
            const std::string insert_ft_sql = R"(
                INSERT OR REPLACE INTO file_token (file_name, total_tokens, unique_tokens, relational_distance)
                VALUES (?, ?, ?, ?);
            )";
            sqlite3_stmt *stmt_ft = nullptr;
            sqlite3_prepare_v2(db, insert_ft_sql.c_str(), -1, &stmt_ft, nullptr);

            const std::string insert_rd_sql = R"(
                INSERT OR REPLACE INTO relation_distance_filtered (file_name, token, frequency, relational_distance)
                VALUES (?, ?, ?, ?);
            )";
            sqlite3_stmt *stmt_rd = nullptr;
            sqlite3_prepare_v2(db, insert_rd_sql.c_str(), -1, &stmt_rd, nullptr);

            // Start a transaction to speed up multiple inserts
            execute_sql(db, "BEGIN TRANSACTION;");

            bool trigger_once = true;
            for (const std::filesystem::path &file : filtered_files)
            {
                if (trigger_once && is_dumped)
                {
                    trigger_once = false;
                    UTILITIES_HPP::Basic::reset_data_dumper(ENV_HPP::data_dumper_path);
                }

                std::map<std::string, int> json_map = TRANSFORMER::json_to_map(file);

                for (auto it = json_map.begin(); it != json_map.end();)
                {
                    const std::string &key = it->first;
                    const int value = it->second;

                    if (value < ENV_HPP::min_value || key.length() > ENV_HPP::max_length ||
                        !std::all_of(key.begin(), key.end(), [](char c)
                                     { return c >= 'a' && c <= 'z'; }))
                    {
                        it = json_map.erase(it);
                    }
                    else
                    {
                        ++it;
                    }
                }

                DataEntry row = {
                    .path = file.stem().generic_string(),
                    .sum = TRANSFORMER::compute_sum_token_json(json_map),
                    .num_unique_tokens = TRANSFORMER::count_unique_tokens(json_map),
                    .relational_distance = TRANSFORMER::Pythagoras(json_map),
                };

                row.filtered_tokens = TRANSFORMER::token_filter(json_map, ENV_HPP::max_length, ENV_HPP::min_value, row.relational_distance);

                if (is_dumped)
                    UTILITIES_HPP::Basic::data_entry_dump(row);

                // Insert into file_token (reuse hoisted statement)
                sqlite3_bind_text(stmt_ft, 1, row.path.c_str(), -1, SQLITE_STATIC);
                sqlite3_bind_int(stmt_ft, 2, row.sum);
                sqlite3_bind_int(stmt_ft, 3, row.num_unique_tokens);
                sqlite3_bind_double(stmt_ft, 4, row.relational_distance);
                sqlite3_step(stmt_ft);
                sqlite3_reset(stmt_ft);

                // Insert filtered tokens into relation_distance (reuse hoisted statement)
                for (const auto &token : row.filtered_tokens)
                {
                    if (std::get<1>(token) < freq_thres)
                        continue;
                    sqlite3_bind_text(stmt_rd, 1, row.path.c_str(), -1, SQLITE_STATIC);           // file_name
                    sqlite3_bind_text(stmt_rd, 2, std::get<0>(token).c_str(), -1, SQLITE_STATIC); // token
                    sqlite3_bind_int(stmt_rd, 3, std::get<1>(token));                             // frequency
                    sqlite3_bind_double(stmt_rd, 4, std::get<2>(token));                          // relational_distance
                    sqlite3_step(stmt_rd);
                    sqlite3_reset(stmt_rd);
                }

                if (show_progress)
                    std::cout << "Processed: " << file << std::endl;
            }
            // Finalize hoisted statements after the loop
            sqlite3_finalize(stmt_ft);
            sqlite3_finalize(stmt_rd);

            // Commit the transaction to apply all inserts
            execute_sql(db, "COMMIT TRANSACTION;");

            // Close the SQLite database connection
            sqlite3_close(db);
            std::cout << "Computing relational distance data finished" << std::endl;
        }
        catch (const std::exception &)
        {
            // Re-thrown so main() names the stage and exits non-zero. Swallowing it here
            // meant a SCHEMA::require failure printed an error and still finished with
            // "Finished: ..." and status 0. main() prints the message, so none here.
            throw;
        }
    }

    /**
     * @brief Compute and store resource data from the given filtered files
     *
     * @param filtered_files A vector of file paths to compute resource data from
     * @param show_progress Whether to show progress in the console
     * @param reset_table Whether to reset the resource data table, default is true
     * @param is_dumped Whether to dump resource data to a file, default is true
     *
     * This function will compute resource data from the given filtered files and store it in a database.
     * The resource data includes the last write time, epoch time, chunk count, starting id, and ending id.
     * The function will also dump the resource data to a file if is_dumped is true.
     * If reset_table is true, the resource data table will be reset before computing the resource data.
     * If show_progress is true, the progress will be shown in the console.
     * If an error occurs, an error message will be printed to the console.
     */
    void computeResourceData(const std::vector<std::filesystem::path> &filtered_files,
                             const bool &show_progress = true,
                             const bool &reset_table = false,
                             const bool &is_dumped = true)
    {
        // Connect to the database
        sqlite3 *db;
        int exit = sqlite3_open(ENV_HPP::database_path.string().c_str(), &db);
        if (exit != SQLITE_OK)
        {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return;
        }

        // Disable synchronous mode for faster inserts
        execute_sql(db, "PRAGMA synchronous = OFF;");

        prepare_tables(db, {"file_info"}, reset_table);

        // chunk_count is read straight out of pdf_chunks below, so a run before the
        // text is in the database would record 0 for every file -- and every
        // downstream stage filters on chunk_count > 0.
        SCHEMA::require(db, {{"pdf_chunks", "python src/main.py --extractText"}},
                        "--updateDatabaseInformation");

        // Upsert rather than INSERT OR IGNORE: file_name (the content hash stem) is the
        // identity, and the rest are facts about the file as it is now. Ignoring a
        // conflict froze file_path, epoch_time and chunk_count at whatever the first run
        // saw -- a file first seen before its text was extracted kept chunk_count = 0 and
        // stayed invisible to every later stage, silently and permanently.
        const std::string insert_sql = R"(
            INSERT INTO file_info (id, file_name, file_path, epoch_time, chunk_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_name) DO UPDATE SET
                id          = excluded.id,
                file_path   = excluded.file_path,
                epoch_time  = excluded.epoch_time,
                chunk_count = excluded.chunk_count;
        )";
        sqlite3_stmt *stmt;
        sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, nullptr);

        // Which files were already recorded, so the log can still distinguish a new book
        // from a refreshed one. sqlite3_changes() cannot: an upsert always reports a change.
        std::unordered_set<std::string> known_files;
        {
            sqlite3_stmt *known_stmt = prepareStatement(db, "SELECT file_name FROM file_info;", "");
            if (known_stmt)
            {
                while (sqlite3_step(known_stmt) == SQLITE_ROW)
                {
                    const unsigned char *name = sqlite3_column_text(known_stmt, 0);
                    if (name)
                        known_files.insert(reinterpret_cast<const char *>(name));
                }
                sqlite3_finalize(known_stmt);
            }
        }

        // Start a transaction for batch processing
        execute_sql(db, "BEGIN TRANSACTION;");

        bool trigger_once = true;
        for (const std::filesystem::path &file : filtered_files)
        {
            // Process the file
            const std::string stem = file.stem().generic_string();
            DataInfo entry = {
                .file_name = stem,
                .file_path = file.generic_string(),
                .epoch_time = UPDATE_INFO::get_epoch_time(file),
                .chunk_count = UPDATE_INFO::count_chunk_for_each_title(db, stem + ".txt")};

            entry.id = UPDATE_INFO::create_unique_id(file);

            // Bind the values to the statement
            sqlite3_bind_text(stmt, 1, entry.id.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 2, entry.file_name.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 3, entry.file_path.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_int(stmt, 4, entry.epoch_time);
            sqlite3_bind_int(stmt, 5, entry.chunk_count);

            if (sqlite3_step(stmt) != SQLITE_DONE)
                std::cerr << "Error inserting into file_info: " << sqlite3_errmsg(db) << std::endl;

            sqlite3_reset(stmt);

            if (trigger_once && is_dumped)
            {
                UTILITIES_HPP::Basic::reset_file_info_dumper(ENV_HPP::data_info_path);
                trigger_once = false;
            }
            if (is_dumped)
                UTILITIES_HPP::Basic::data_info_dump(entry);
            if (show_progress)
                std::cout << (known_files.count(entry.file_name) ? "Refreshed: " : "Processed: ")
                          << file << std::endl;
        }

        // Finalize the prepared statement
        sqlite3_finalize(stmt);

        // Commit the transaction to apply all inserts
        execute_sql(db, "COMMIT TRANSACTION;");

        // Re-enable synchronous mode (optional, depending on use case)
        execute_sql(db, "PRAGMA synchronous = FULL;");

        // Close the database connection
        sqlite3_close(db);
        std::cout << "Computing resource data finished" << std::endl;
    }

    /**
     * Process the prompt in the buffer.json file and computes the top N most related
     * documents to the prompt. The results are stored in the outputPrompt.txt file.
     * The output format is as follows:
     * Top N Results:
     * -----------------------------------------------------------------
     * ID: <id>
     * Distance: <distance>
     * Rank: <rank>
     * Name: [[<name>]]
     * -----------------------------------------------------------------
     *
     */
    void processPrompt()
    {
        try
        {
            // Step 1: Token preparation
            std::map<std::string, int> tokens = TRANSFORMER::json_to_map(ENV_HPP::buffer_json_path);
            int distance = TRANSFORMER::Pythagoras(tokens);
            std::vector<std::tuple<std::string, int, double>> filtered_tokens = TRANSFORMER::token_filter(tokens, 16, 1, distance);
            tokens.clear();

            // Step 2: Open database
            std::ofstream output_file(ENV_HPP::outputPrompt);
            output_file << ""; // Clear the file

            sqlite3 *db;
            if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK)
            {
                std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
                return;
            }

            SCHEMA::require(db,
                            {{"file_info", "word_tokenizer --updateDatabaseInformation"},
                             {"relation_distance_filtered", "word_tokenizer --computeRelationalDistance"}},
                            "--processPrompt");

            // SQLite PRAGMAs
            sqlite3_exec(db, "PRAGMA journal_mode=WAL;", nullptr, nullptr, nullptr);
            sqlite3_exec(db, "PRAGMA synchronous=OFF;", nullptr, nullptr, nullptr);
            sqlite3_exec(db, "PRAGMA temp_store=MEMORY;", nullptr, nullptr, nullptr);
            sqlite3_exec(db, "BEGIN;", nullptr, nullptr, nullptr);

            // Step 3: Prepare file_info reader
            std::string file_info_sql = "SELECT id, file_name FROM file_info;";
            sqlite3_stmt *file_stmt = prepareStatement(db, file_info_sql, "Error preparing statement (file_info)");
            if (!file_stmt)
            {
                sqlite3_close(db);
                return;
            }

            // Step 4: Load relation_distance map
            std::map<std::string, std::map<std::string, double>> relation_distance_map;
            std::string token_in_clause;
            for (const auto &[token, _, __] : filtered_tokens)
                token_in_clause += "'" + token + "',";
            if (!token_in_clause.empty())
                token_in_clause.pop_back();

            std::string relation_sql = "SELECT file_name, Token, relational_distance FROM relation_distance_filtered WHERE Token IN (" + token_in_clause + ");";
            sqlite3_stmt *rel_stmt = prepareStatement(db, relation_sql, "Error preparing statement (relation_distance_filtered)");
            if (!rel_stmt)
            {
                sqlite3_finalize(file_stmt);
                sqlite3_close(db);
                return;
            }

            while (sqlite3_step(rel_stmt) == SQLITE_ROW)
            {
                std::string rel_file = reinterpret_cast<const char *>(sqlite3_column_text(rel_stmt, 0));
                std::string token = reinterpret_cast<const char *>(sqlite3_column_text(rel_stmt, 1));
                double rel_dist = sqlite3_column_double(rel_stmt, 2);
                relation_distance_map[rel_file][token] = rel_dist;
            }

            sqlite3_finalize(rel_stmt);

            // Step 5: Load TF-IDF values
            std::string tfidf_sql = "SELECT tf_idf FROM tf_idf WHERE word = ?;";
            sqlite3_stmt *tfidf_stmt = prepareStatement(db, tfidf_sql, "Error preparing statement (tf_idf)");
            if (!tfidf_stmt)
            {
                sqlite3_finalize(file_stmt);
                sqlite3_close(db);
                return;
            }

            for (auto &[token, freq, base_distance] : filtered_tokens)
            {
                sqlite3_reset(tfidf_stmt);
                sqlite3_bind_text(tfidf_stmt, 1, token.c_str(), -1, SQLITE_TRANSIENT);
                if (sqlite3_step(tfidf_stmt) == SQLITE_ROW)
                {
                    double tfidf = sqlite3_column_double(tfidf_stmt, 0);
                    // Adjust to 0.0 if TF-IDF value is not found
                    if (std::isnan(tfidf))
                        tfidf = 0.0;
                    // Update base_distance with addition of TF-IDF value
                    base_distance += tfidf / freq;
                }
            }
            sqlite3_finalize(tfidf_stmt);

            // Step 6: Compute scores
            std::vector<std::tuple<std::string, std::string, double>> RESULT;

            while (sqlite3_step(file_stmt) == SQLITE_ROW)
            {
                std::string id(reinterpret_cast<const char *>(sqlite3_column_text(file_stmt, 0)));
                std::string file_name(reinterpret_cast<const char *>(sqlite3_column_text(file_stmt, 1)));

                std::string rel_file_key = "title_" + id;
                if (relation_distance_map.find(rel_file_key) == relation_distance_map.end())
                    continue;

                double score = 0.0;
                const auto &token_map = relation_distance_map[rel_file_key];

                for (const auto &[token, _, base_distance] : filtered_tokens)
                {
                    auto rel_it = token_map.find(token);
                    if (rel_it == token_map.end())
                        continue;

                    double rel_dist = rel_it->second;
                    score += rel_dist * base_distance;
                }

                if (score > 0.0)
                {
                    RESULT.emplace_back(id, file_name, score);
                }

                relation_distance_map.erase(rel_file_key);
            }

            sqlite3_exec(db, "COMMIT;", nullptr, nullptr, nullptr);
            sqlite3_finalize(file_stmt);
            sqlite3_close(db);

            // Free up memory
            relation_distance_map.clear();
            filtered_tokens.clear();

            // Step 7: Sort and output
            std::sort(RESULT.begin(), RESULT.end(), [](const auto &a, const auto &b)
                      { return std::get<2>(a) > std::get<2>(b); });

            output_file << "Results:\n"
                        << "-----------------------------------------------------------------\n";
            for (uint16_t i = 0; i < RESULT.size(); i++)
            {
                output_file << "ID: " << std::get<0>(RESULT[i]) << "\n"
                            << "Distance: " << std::get<2>(RESULT[i]) << "\n"
                            << "Rank: " << i + 1 << "\n"
                            << "Name: [[" << std::get<1>(RESULT[i]) << "]]\n"
                            << "-----------------------------------------------------------------\n";
            }
        }
        catch (const std::exception &)
        {
            // Re-thrown so main() names the stage and exits non-zero. Swallowing it here
            // meant a SCHEMA::require failure printed an error and still finished with
            // "Finished: ..." and status 0. main() prints the message, so none here.
            throw;
        }
    }

    /**
     * Skim a list of files and return a new list containing only the files that are
     * not present in the database.
     *
     * @param files The list of files to be skimmed.
     * @param extension The extension of the files to be skimmed. Supported values
     *                  are ".pdf" and ".json". If any other value is provided, the
     *                  original list is returned.
     * @return A new list containing only the files that are not present in the
     * database.
     */
    std::vector<std::filesystem::path> skim_files(std::vector<std::filesystem::path> &files, const std::string &extension)
    {
        // Step 1: Open the database connection
        sqlite3 *db;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK)
        {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            return files; // Return the original list if the database cannot be opened
        }

        // Step 2: Prepare the SQL query to fetch all file names in the database
        std::string fetch_sql;
        if (extension == ".pdf")
        {
            fetch_sql = R"(
                SELECT DISTINCT file_name 
                FROM file_info
            )";
        }
        else if (extension == ".json")
        {
            fetch_sql = R"(
                SELECT DISTINCT file_name 
                FROM relation_distance_filtered
            )";
        }
        else
        {
            std::cerr << "Unsupported extension: " << extension << std::endl;
            sqlite3_close(db);
            return files; // Return the original list if the extension is unsupported
        }

        // Prepare the SQL statement
        sqlite3_stmt *stmt;
        if (sqlite3_prepare_v2(db, fetch_sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK)
        {
            std::cerr << "Error preparing SQL statement: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return files; // Return the original list if the statement cannot be prepared
        }

        // Step 3: Retrieve all entries from the database
        std::unordered_set<std::string> db_files;
        while (sqlite3_step(stmt) == SQLITE_ROW)
        {
            const unsigned char *db_file = sqlite3_column_text(stmt, 0);
            if (db_file)
            {
                db_files.insert(reinterpret_cast<const char *>(db_file));
            }
        }

        // Finalize the statement and close the database connection
        sqlite3_finalize(stmt);
        sqlite3_close(db);

        // Step 4: Filter the files based on the database entries
        auto filter_condition = [&db_files, &extension](const std::filesystem::path &file)
        {
            if (file.extension() == extension)
            {
                // Remove the extension and compare with database values
                std::string file_name_no_ext = file.filename().stem().string(); // Strips the extension
                return !(db_files.find(file_name_no_ext) == db_files.end());    // Return true if not in database
            }
            return true; // If unsupported extension, mark for removal
        };

        files.erase(std::remove_if(files.begin(), files.end(), filter_condition), files.end());
        return files; // Return the filtered list
    }

    /**
     * Computes TF-IDF values for all words in the database.
     *
     * TF-IDF (Term Frequency-Inverse Document Frequency) is a measure of how important a word is in a document.
     * It takes into account the frequency of the word in the current document and the frequency of the word in all
     * documents in the database.
     *
     * The function does the following steps:
     * 1. Loads the JSON file containing the global word frequencies.
     * 2. Filters out words with a frequency less than MIN_THRES_FREQ.
     * 3. Computes the TF-IDF value for each filtered word.
     * 4. Stores the TF-IDF values in the database.
     *
     * @param MIN_THRES_FREQ The minimum frequency of a word to be included in the computation.
     * @param BUFFER_SIZE The number of records to process at once. This is used to speed up the computation.
     */

    struct TFIDFRecord
    {
        std::string word;
        int freq;
        int doc_count;
        double tf_idf;
    };

    void computeTFIDF(const uint16_t &MIN_THRES_FREQ = 1,
                      const uint16_t &BUFFER_SIZE = 1000)
    {
        const std::string db_path = ENV_HPP::database_path.string();
        const std::string GLOBAL_JSON_PATH = ENV_HPP::global_terms_path.string();
        const std::string DATASET_FOLDER = ENV_HPP::json_path.string();

        sqlite3 *db;
        if (sqlite3_open(db_path.c_str(), &db) != SQLITE_OK)
        {
            std::cerr << "Can't open database\n";
            return;
        }

        execute_sql(db, "PRAGMA journal_mode=WAL;");
        execute_sql(db, "PRAGMA synchronous = OFF;");

        // This stage has no reset flag: it always accumulates into the existing table.
        prepare_tables(db, {"tf_idf"});

        SCHEMA::require(db,
                        {{"relation_distance_filtered", "word_tokenizer --computeRelationalDistance"}},
                        "--computeTFIDF");

        std::unordered_map<std::string, int> global_freq;

        bool loaded_from_backup = false;

        if (std::filesystem::exists(GLOBAL_JSON_PATH))
        {
            try
            {
                std::ifstream in(GLOBAL_JSON_PATH);
                json j;
                in >> j;

                for (auto &[word, freq] : j.items())
                    global_freq[word] = freq.get<int>();

                loaded_from_backup = true;
                std::cout << "[INFO] Loaded global frequency from backup\n";
            }
            catch (...)
            {
                std::cerr << "[WARNING] Backup corrupted. Rebuilding...\n";
            }
        }

        if (!loaded_from_backup)
        {
            std::cout << "[INFO] Aggregating JSON files...\n";

            for (const auto &entry : std::filesystem::recursive_directory_iterator(DATASET_FOLDER))
            {
                if (entry.path().extension() != ".json")
                    continue;

                std::ifstream in(entry.path());
                if (!in.is_open())
                    continue;

                try
                {
                    json j;
                    in >> j;

                    for (auto &[word, freq] : j.items())
                    {
                        global_freq[word] += freq.get<int>();
                    }
                    std::cout << "Completed: " << entry.path() << std::endl;
                }
                catch (...)
                {
                    std::cerr << "[WARNING] Skipping bad JSON: "
                              << entry.path() << std::endl;
                }
            }

            std::cout << "[INFO] Saving backup...\n";

            json out_json;
            for (auto &[word, freq] : global_freq)
                out_json[word] = freq;

            std::string temp_path = GLOBAL_JSON_PATH + ".tmp";

            {
                std::ofstream out(temp_path);
                out << out_json.dump();
            }

            std::filesystem::rename(temp_path, GLOBAL_JSON_PATH);
        }

        std::unordered_map<std::string, int> filtered_words;
        int sum_freq = 0;

        for (auto &[word, freq] : global_freq)
        {
            if (freq >= MIN_THRES_FREQ && word.length() > 1)
            {
                filtered_words[word] = freq;
                sum_freq += freq;
            }
        }

        std::unordered_map<std::string, int> word_doc_counts;

        sqlite3_stmt *stmt;
        std::string query =
            "SELECT token, COUNT(DISTINCT file_name) FROM relation_distance_filtered GROUP BY token;";

        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr) == SQLITE_OK)
        {
            while (sqlite3_step(stmt) == SQLITE_ROW)
            {
                std::string token(reinterpret_cast<const char *>(sqlite3_column_text(stmt, 0)));
                int count = sqlite3_column_int(stmt, 1);
                word_doc_counts[token] = count;
            }
        }
        sqlite3_finalize(stmt);

        int total_docs = 0;
        query = "SELECT COUNT(DISTINCT file_name) FROM relation_distance_filtered;";

        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr) == SQLITE_OK &&
            sqlite3_step(stmt) == SQLITE_ROW)
        {
            total_docs = sqlite3_column_int(stmt, 0);
        }
        sqlite3_finalize(stmt);

        execute_sql(db, "BEGIN TRANSACTION;");

        std::vector<TFIDFRecord> buffer;

        sqlite3_stmt *insertStmt;
        std::string sql =
            "INSERT INTO tf_idf (word, freq, doc_count, tf_idf) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET "
            "freq=excluded.freq, doc_count=excluded.doc_count, tf_idf=excluded.tf_idf;";

        sqlite3_prepare_v2(db, sql.c_str(), -1, &insertStmt, nullptr);

        for (auto &[word, freq] : filtered_words)
        {
            int doc_count = word_doc_counts[word];

            double tf = static_cast<double>(freq) / sum_freq;
            double idf = log10((total_docs + 1.0) / (doc_count + 1.0)) + 1.0;
            double tf_idf = tf * idf;

            sqlite3_bind_text(insertStmt, 1, word.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_int(insertStmt, 2, freq);
            sqlite3_bind_int(insertStmt, 3, doc_count);
            sqlite3_bind_double(insertStmt, 4, tf_idf);

            sqlite3_step(insertStmt);
            sqlite3_reset(insertStmt);
        }

        sqlite3_finalize(insertStmt);

        execute_sql(db, "COMMIT;");
        sqlite3_close(db);

        std::cout << "[INFO] TF-IDF computation completed.\n";
    }

    void mappingItemMatrix(const bool &show_progress = true,
                           const bool &reset_table = true,
                           const uint8_t &update_freq = 50)
    {
        sqlite3 *db;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK)
        {
            std::cerr << "Error opening database." << std::endl;
            return;
        }

        execute_sql(db, "PRAGMA journal_mode=WAL;");
        execute_sql(db, "PRAGMA synchronous=OFF;");
        execute_sql(db, "PRAGMA temp_store=MEMORY;");

        // Clear low similarity files if we are resetting the matrix
        if (reset_table)
        {
            std::ofstream clear_file(ENV_HPP::low_similarity_files.string().c_str(), std::ofstream::trunc);
            clear_file.close();
        }

        prepare_tables(db, {"comparison"}, reset_table);

        SCHEMA::require(db,
                        {{"file_info", "word_tokenizer --updateDatabaseInformation"},
                         {"relation_distance_filtered", "word_tokenizer --computeRelationalDistance"},
                         {"tf_idf", "word_tokenizer --computeTFIDF"}},
                        "--mappingItemMatrix");

        std::map<std::string, std::string> unique_ids = RECOMMEND::collect_unique_id(db);
        std::map<std::string, std::string> processing_ids = RECOMMEND::collect_processing_id(db, reset_table, unique_ids, "SELECT DISTINCT source_id FROM comparison");
        RECOMMEND::eliminate_low_similarity_processed_files(processing_ids);
        std::map<std::string, std::string> comparison_list = unique_ids; // Copy of unique_ids for comparison

        std::cout << "Found " << processing_ids.size() << " files to process\n";

        std::chrono::high_resolution_clock::time_point start_time = std::chrono::high_resolution_clock::now();
        std::vector<std::pair<std::string, std::string>> items;

        for (const auto &p : processing_ids)
            items.emplace_back(p.first, p.second);

        processing_ids.clear();

        uint16_t size = items.size(); // Update size after shuffling

        for (size_t i = 0; i < size; ++i)
        {
            const auto &id_pair = items[i];
            const std::string &id = id_pair.first;
            std::vector<std::tuple<std::string, std::string, double>> result;

            // Dynamically remove IDs that have already been compared with the current 'id'
            std::map<std::string, std::string> current_comparison_list = comparison_list;
            if (!reset_table)
            {
                std::string check_sql = "SELECT target_id FROM comparison WHERE source_id = ? UNION SELECT source_id FROM comparison WHERE target_id = ?";
                current_comparison_list = RECOMMEND::collect_processing_id(db, false, current_comparison_list, check_sql, {id, id});
            }

            auto filtered_tokens = RECOMMEND::load_token_map(db, id);
            if (filtered_tokens.empty())
                continue;

            RECOMMEND::apply_tfidf(db, filtered_tokens);
            auto relation_distance_map = RECOMMEND::load_related_tokens(db, filtered_tokens);
            std::vector<std::tuple<std::string, std::string, double>> results = RECOMMEND::compute_recommendations(filtered_tokens, relation_distance_map, id, current_comparison_list);

            for (const auto &[target_id, target_name, distance] : results)
            {
                if (distance < 0.4)
                    continue;
                std::tuple<std::string, std::string, double> row = {target_id, id, distance};
                result.push_back(row);
            }

            comparison_list.erase(id); // Remove the current id from comparison list to speed up the iteration

            // If the result is empty, check if it truly has no matches in the DB
            if (result.empty())
            {
                std::ofstream file(ENV_HPP::low_similarity_files.string().c_str(), std::ofstream::app);
                if (file.is_open())
                    file << id << "\n";
                else
                    std::cout << ENV_HPP::low_similarity_files.string() << " is fucked.\n";
                file.close();
            }
            else
            {

                execute_sql(db, "BEGIN;");
                RECOMMEND::insert_comparison(result, db);
                execute_sql(db, "COMMIT;");
            }

            if (show_progress)
                start_time = UTILITIES_HPP::Timer::show_update(i + 1, size, start_time, update_freq, id); // Reset start time after each update to get accurate ETA for next batch}
        }
        sqlite3_close(db);
    }

    void label_topics(bool show_progress, bool reset_table, const float &threshold = 0.4, bool clear_buffer = false, uint8_t update_freq = 50)
    {
        sqlite3 *db = nullptr;
        try
        {
            if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK)
            {
                std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
                if (db)
                    sqlite3_close(db);
                return;
            }

            execute_sql(db, "PRAGMA journal_mode=WAL;");
            execute_sql(db, "PRAGMA synchronous=OFF;");
            execute_sql(db, "PRAGMA temp_store=MEMORY;");

            prepare_tables(db, {"tags_full"}, reset_table);

            SCHEMA::require(db,
                            {{"topic_token", "python src/main.py --topicTokenize"},
                             {"file_info", "word_tokenizer --updateDatabaseInformation"},
                             {"relation_distance_filtered", "word_tokenizer --computeRelationalDistance"},
                             {"tf_idf", "word_tokenizer --computeTFIDF"}},
                            "--labelTopics");

            std::map<std::string, std::string> unique_ids = RECOMMEND::collect_unique_id(db);
            std::vector<std::string> unique_topics = RECOMMEND::collect_unique_topic(db);

            // Open a buffer text file to remove processed topics from the list in case of interruption
            if (clear_buffer)
            {
                std::ofstream buffer_file(ENV_HPP::processed_topics_buffer.string(), std::ofstream::trunc);
                buffer_file.close();
            }
            else
            {
                std::ifstream buffer_file(ENV_HPP::processed_topics_buffer.string());
                std::string topic;
                while (std::getline(buffer_file, topic))
                    unique_topics.erase(std::remove(unique_topics.begin(), unique_topics.end(), topic), unique_topics.end());
                buffer_file.close();
            }

            uint16_t size = unique_topics.size();
            std::chrono::high_resolution_clock::time_point start_time = std::chrono::high_resolution_clock::now();
            for (size_t i = 0; i < unique_topics.size(); ++i)
            {
                std::string topic = unique_topics[i];
                // Calculate which IDs need processing for THIS specific topic to support resuming correctly.
                // Scenario 1: New topics will have no entries in tags_full, so all unique_ids are processed.
                // Scenario 2: New file IDs will not be in tags_full for any topic, so they are processed for all.
                std::string check_sql = "SELECT ID FROM tags_full WHERE topic = ?";
                std::map<std::string, std::string> topic_processing_ids = RECOMMEND::collect_processing_id(db, reset_table, unique_ids, check_sql, {topic});

                if (topic_processing_ids.empty())
                    continue;

                auto filtered_tokens = RECOMMEND::load_topic_token_map(db, topic);
                if (filtered_tokens.empty())
                    continue;

                RECOMMEND::apply_tfidf(db, filtered_tokens);
                auto relation_distance_map = RECOMMEND::load_related_tokens(db, filtered_tokens);

                // Only compute recommendations for the IDs that are missing for this topic
                std::vector<std::tuple<std::string, std::string, double>> recommendations =
                    RECOMMEND::compute_recommendations(filtered_tokens, relation_distance_map, topic, topic_processing_ids);

                std::vector<std::tuple<std::string, std::string, double>> skimmy;

                // Skim down the recommendation list
                for (const auto &[target_id, target_name, distance] : recommendations)
                {
                    if (distance < threshold)
                        continue;
                    std::tuple<std::string, std::string, double> res = {target_id, topic, distance};
                    skimmy.emplace_back(res);
                }

                if (!skimmy.empty())
                {
                    execute_sql(db, "BEGIN;");
                    RECOMMEND::insert_tags_full(skimmy, db);
                    execute_sql(db, "COMMIT;");
                }

                // Append the processed topic to the buffer file to support resuming in case of interruption
                std::ofstream buffer_file(ENV_HPP::processed_topics_buffer.string(), std::ofstream::app);
                buffer_file << topic << "\n";
                buffer_file.close();

                if (show_progress)
                    start_time = UTILITIES_HPP::Timer::show_update(i + 1, size, start_time, update_freq, topic); // Reset start time after each update to get accurate ETA for next batch}
            }

            sqlite3_close(db);
            db = nullptr;
            // Clear the buffer file after successful completion
            std::ofstream clear_buffer(ENV_HPP::processed_topics_buffer.string(), std::ofstream::trunc);
            clear_buffer.close();
        }
        catch (const std::exception &)
        {
            // Re-thrown so main() names the stage and exits non-zero. Swallowing it here
            // meant a SCHEMA::require failure printed an error and still finished with
            // "Finished: ..." and status 0. main() prints the message, so none here.
            if (db)
                sqlite3_close(db);
            throw;
        }
    }

    void topicSimilarity(bool show_progress = true, bool reset_table = true, const float &threshold = 0.4)
    {
        sqlite3 *db = nullptr;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK)
        {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            if (db)
                sqlite3_close(db);
            return;
        }

        execute_sql(db, "PRAGMA journal_mode=WAL;");
        execute_sql(db, "PRAGMA synchronous=OFF;");
        execute_sql(db, "PRAGMA temp_store=MEMORY;");

        prepare_tables(db, {"topic_similarity"}, reset_table);

        SCHEMA::require(db, {{"topic_token", "python src/main.py --topicTokenize"}},
                        "--topicSimilarity");

        std::vector<std::string> unique_topics = RECOMMEND::collect_unique_topic(db);

        // Let's filter out processed pairs to support resuming
        std::map<std::string, std::vector<std::string>> processed_pairs;
        if (!reset_table)
        {
            std::string sql = "SELECT source_topic, target_topic FROM topic_similarity";
            sqlite3_stmt *stmt = prepareStatement(db, sql, "");
            if (stmt)
            {
                while (sqlite3_step(stmt) == SQLITE_ROW)
                {
                    std::string src = reinterpret_cast<const char *>(sqlite3_column_text(stmt, 0));
                    std::string tgt = reinterpret_cast<const char *>(sqlite3_column_text(stmt, 1));
                    processed_pairs[src].push_back(tgt);
                }
                sqlite3_finalize(stmt);
            }
        }

        // Load all topic tokens into memory
        std::map<std::string, std::vector<std::tuple<std::string, int, double>>> topic_tokens_map;
        for (const auto &topic : unique_topics)
        {
            auto tokens = RECOMMEND::load_topic_token_map(db, topic);
            RECOMMEND::apply_tfidf(db, tokens);
            topic_tokens_map[topic] = tokens;
        }

        uint16_t size = unique_topics.size();
        std::chrono::high_resolution_clock::time_point start_time = std::chrono::high_resolution_clock::now();

        for (size_t i = 0; i < size; ++i)
        {
            std::string source_topic = unique_topics[i];
            const auto &source_tokens = topic_tokens_map[source_topic];

            // Convert to fast map for dot product
            std::unordered_map<std::string, double> source_weights;
            for (const auto &[tok, _, dist] : source_tokens)
            {
                source_weights[tok] = dist;
            }

            std::vector<std::tuple<std::string, std::string, double>> results;

            for (size_t j = i + 1; j < size; ++j)
            {
                std::string target_topic = unique_topics[j];

                if (!reset_table)
                {
                    auto &processed = processed_pairs[source_topic];
                    if (std::find(processed.begin(), processed.end(), target_topic) != processed.end())
                    {
                        continue;
                    }
                }

                const auto &target_tokens = topic_tokens_map[target_topic];

                double score = 0.0;
                for (const auto &[tok, _, dist] : target_tokens)
                {
                    auto it = source_weights.find(tok);
                    if (it != source_weights.end())
                    {
                        score += dist * it->second;
                    }
                }

                if (score >= threshold)
                {
                    results.emplace_back(source_topic, target_topic, score);
                }
            }

            topic_tokens_map.erase(source_topic); // Free memory as we go

            if (!results.empty())
            {
                execute_sql(db, "BEGIN;");
                RECOMMEND::insert_topic_similarity(results, db);
                execute_sql(db, "COMMIT;");
            }

            if (show_progress)
                start_time = UTILITIES_HPP::Timer::show_update(i + 1, size, start_time, 50, source_topic); // Reset start time after each update to get accurate ETA for next batch}
        }

        sqlite3_close(db);
    }

    void iterative_topic_expansion(int max_degree,
                                   float threshold,
                                   float threshold_degree1,
                                   bool reset_table)
    {
        sqlite3 *db;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK)
        {
            std::cerr << "Error opening database." << std::endl;
            return;
        }

        execute_sql(db, "PRAGMA journal_mode=WAL;");
        execute_sql(db, "PRAGMA synchronous=OFF;");
        execute_sql(db, "PRAGMA temp_store=MEMORY;");
        execute_sql(db, "PRAGMA cache_size=-200000;"); // ~200MB cache if available

        // tags is this stage's own output; idx_tags_degree and idx_cmp_target -- the two
        // indexes expand_degree relies on -- come from config/schema.sql with it.
        prepare_tables(db, {"tags"}, reset_table);

        SCHEMA::require(db,
                        {{"tags_full", "word_tokenizer --labelTopics"},
                         {"comparison", "word_tokenizer --mappingItemMatrix"}},
                        "--expandTopics");

        std::cout << "Database setup completed. Starting iterative topic expansion..." << std::endl;
        // -------------------------------------------------
        // Degree 1 (seed)
        // -------------------------------------------------
        const std::string insert_degree1_sql = R"(
            INSERT OR IGNORE INTO tags (ID, distance, topic, degree)
            SELECT ID, distance, topic, 1
            FROM tags_full
            WHERE distance >= ?;
        )";

        execute_sql(db, "BEGIN;");
        const int seeded = SQL::execute_prepared(db, insert_degree1_sql, [&](sqlite3_stmt *stmt)
                                                 { sqlite3_bind_double(stmt, 1, threshold_degree1); });
        execute_sql(db, "COMMIT;");
        std::cout << "Completed expanding to degree 1 (seed): " << seeded << " tags" << std::endl;

        // -------------------------------------------------
        // Iterative Expansion
        // -------------------------------------------------
        for (int degree = 1; degree <= max_degree; ++degree)
        {
            execute_sql(db, "BEGIN;");
            const int added = RECOMMEND::expand_degree(db, degree, degree + 1, threshold);
            execute_sql(db, "COMMIT;");

            std::cout << "Completed expanding to degree " << degree + 1
                      << ": " << added << " tags" << std::endl;
        }

        sqlite3_close(db);
    }

    void run_cutoff_analysis()
    {
        sqlite3 *db;

        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db))
        {
            std::cerr << "Cannot open DB\n";
            return;
        }

        // PRAGMA (outside transaction)
        execute_sql(db, R"(
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;
            PRAGMA temp_store=MEMORY;
            PRAGMA cache_size=-200000;
        )");

        SCHEMA::require(db,
                        {{"relation_distance_filtered", "word_tokenizer --computeRelationalDistance"},
                         {"tf_idf", "word_tokenizer --computeTFIDF"}},
                        "--runCutoffAnalysis");

        // STEP 1: Indexes. Scoped to this stage rather than declared in
        // config/schema.sql: they exist only to group ~1.9M rows four ways, and every
        // other stage would pay to maintain them. STEP 8 drops them again.
        // idx_rd_file_freq is not among them -- the table's own PRIMARY KEY
        // (file_name, token) already orders by file_name.
        std::cout << "[STEP 1] Creating indexes...\n";
        execute_sql(db, R"(
            CREATE INDEX IF NOT EXISTS idx_rd_token_freq
            ON relation_distance_filtered(token, frequency);

            CREATE INDEX IF NOT EXISTS idx_rd_freq
            ON relation_distance_filtered(frequency);

            CREATE INDEX IF NOT EXISTS idx_tfidf_freq
            ON tf_idf(freq);
        )");

        execute_sql(db, "BEGIN;");

        // STEPS 2-7 are derived tables: each is a snapshot of the tables above it, so
        // every run rebuilds them from scratch. Their columns come from their SELECT,
        // which is why config/schema.sql cannot declare them.

        // STEP 2: Frequency distribution (direct)
        std::cout << "[STEP 2] Building freq_dist...\n";
        rebuild_derived(db, "freq_dist", R"(
            CREATE TABLE IF NOT EXISTS freq_dist AS
            SELECT frequency AS freq, COUNT(*) AS cnt, SUM(frequency) AS total_freq
            FROM relation_distance_filtered
            GROUP BY frequency;
        )");

        // STEP 3: Token distribution
        std::cout << "[STEP 3] Building token_dist...\n";
        rebuild_derived(db, "token_dist", R"(
            CREATE TABLE IF NOT EXISTS token_dist AS
            SELECT MAX(frequency) AS freq, COUNT(*) AS cnt
            FROM relation_distance_filtered
            GROUP BY token;
        )");

        // STEP 4: File distribution
        std::cout << "[STEP 4] Building file_dist...\n";
        rebuild_derived(db, "file_dist", R"(
            CREATE TABLE IF NOT EXISTS file_dist AS
            SELECT MAX(frequency) AS freq, COUNT(*) AS cnt
            FROM relation_distance_filtered
            GROUP BY file_name;
        )");

        // STEP 5: Word distribution (simplified due to PK(word))
        std::cout << "[STEP 5] Building word_dist...\n";
        rebuild_derived(db, "word_dist", R"(
            CREATE TABLE IF NOT EXISTS word_dist AS
            SELECT freq, COUNT(*) AS cnt
            FROM tf_idf
            GROUP BY freq;
        )");

        // STEP 6: Totals
        std::cout << "[STEP 6] Computing totals...\n";
        rebuild_derived(db, "totals", R"(
            CREATE TABLE IF NOT EXISTS totals AS
            SELECT
                (SELECT SUM(total_freq) FROM freq_dist) AS total_freq,
                (SELECT SUM(cnt) FROM token_dist) AS total_tokens,
                (SELECT SUM(cnt) FROM file_dist) AS total_files,
                (SELECT SUM(cnt) FROM word_dist) AS total_words;
        )");

        // STEP 7: Final cutoff table
        std::cout << "[STEP 7] Computing cutoff_analysis...\n";
        rebuild_derived(db, "cutoff_analysis", R"(
            CREATE TABLE IF NOT EXISTS cutoff_analysis AS
            WITH RECURSIVE targets(t) AS (
                SELECT 1
                UNION ALL
                SELECT t + 1 FROM targets WHERE t < 1000
            )
            SELECT
                t AS target,

                -- coverage metrics
                (SELECT SUM(total_freq) FROM freq_dist WHERE freq > t) * 1.0 / total_freq AS freq_cov,
                (SELECT SUM(cnt) FROM token_dist WHERE freq > t) * 1.0 / total_tokens AS token_cov,
                (SELECT SUM(cnt) FROM file_dist WHERE freq > t) * 1.0 / total_files AS file_cov,
                (SELECT SUM(cnt) FROM word_dist WHERE freq > t) * 1.0 / total_words AS word_cov,

                -- weighted score
                (
                    0.5 * (SELECT SUM(total_freq) FROM freq_dist WHERE freq > t) * 1.0 / total_freq +
                    0.2 * (SELECT SUM(cnt) FROM token_dist WHERE freq > t) * 1.0 / total_tokens +
                    0.2 * (SELECT SUM(cnt) FROM file_dist WHERE freq > t) * 1.0 / total_files +
                    0.1 * (SELECT SUM(cnt) FROM word_dist WHERE freq > t) * 1.0 / total_words
                ) AS weighted_score

            FROM targets, totals
            ORDER BY target;
        )");

        execute_sql(db, "COMMIT;");

        // STEP 8: hand the database back the way it was found. These indexes cost write
        // time on every later --computeRelationalDistance run and nothing else reads them.
        std::cout << "[STEP 8] Dropping analysis indexes...\n";
        execute_sql(db, R"(
            DROP INDEX IF EXISTS idx_rd_token_freq;
            DROP INDEX IF EXISTS idx_rd_freq;
            DROP INDEX IF EXISTS idx_tfidf_freq;
        )");

        std::cout << "[DONE] cutoff_analysis ready.\n";

        sqlite3_close(db);
    }
}
#endif // FEATURE_HPP