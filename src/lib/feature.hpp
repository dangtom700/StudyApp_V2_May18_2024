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

using json = nlohmann::json;

#include "utilities.hpp"
#include "env.hpp"
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
        char *error_message = nullptr;
        int exit = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &error_message);
        if (exit != SQLITE_OK)
        {
            std::cerr << "Error executing SQL: " << error_message << std::endl
                      << "SQL: " << sql << std::endl;
            sqlite3_free(error_message);
            throw std::runtime_error("SQL execution failed");
        }
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
                                   const bool &is_dumped = true)
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

            // Create tables if reset_table is true
            if (reset_table)
            {
                // Only drop tables
                std::string drop_sql = R"(
                    DROP TABLE IF EXISTS file_token;
                    DROP TABLE IF EXISTS relation_distance;
                )";
                execute_sql(db, drop_sql);
            }

            // Only create tables if they do not exist
            std::string create_sql = R"(
                CREATE TABLE IF NOT EXISTS file_token (
                    file_name           TEXT    NOT NULL PRIMARY KEY,
                    total_tokens        INTEGER NOT NULL DEFAULT 0,
                    unique_tokens       INTEGER NOT NULL DEFAULT 0,
                    relational_distance REAL    NOT NULL DEFAULT 0.0
                ) WITHOUT ROWID;
            )";
            execute_sql(db, create_sql);

            create_sql = R"(
                CREATE TABLE IF NOT EXISTS relation_distance (
                    file_name           TEXT    NOT NULL,
                    token               TEXT    NOT NULL,
                    frequency           INTEGER NOT NULL DEFAULT 0,
                    relational_distance REAL    NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (file_name, token)
                ) WITHOUT ROWID;
            )";
            execute_sql(db, create_sql);

            // // Covering index: token -> (file_name, relational_distance) lookup
            // // used by processPrompt and load_related_tokens JOIN.
            // execute_sql(db,
            //             "CREATE INDEX IF NOT EXISTS idx_rd_token_covering "
            //             "ON relation_distance(token, file_name, relational_distance);");

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
                INSERT OR REPLACE INTO relation_distance (file_name, token, frequency, relational_distance)
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
                    sqlite3_bind_text(stmt_rd, 1, row.path.c_str(), -1, SQLITE_STATIC);
                    sqlite3_bind_text(stmt_rd, 2, std::get<0>(token).c_str(), -1, SQLITE_STATIC);
                    sqlite3_bind_int(stmt_rd, 3, std::get<1>(token));
                    sqlite3_bind_double(stmt_rd, 4, std::get<2>(token));
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

            // Re-enable synchronous mode (optional, depending on your use case)
            execute_sql(db, "PRAGMA synchronous = FULL;");

            // Close the SQLite database connection
            sqlite3_close(db);
            std::cout << "Computing relational distance data finished" << std::endl;
        }
        catch (const std::exception &e)
        {
            std::cerr << "Error: " << e.what() << std::endl;
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

        // Create or reset the table if required
        if (reset_table)
            execute_sql(db, "DROP TABLE IF EXISTS file_info");

        // WITHOUT ROWID: file_name is the PK, making point-lookups single B-tree ops.
        // UNIQUE(id) enforces id uniqueness used by collect_unique_id().
        std::string create_table_sql = R"(
            CREATE TABLE IF NOT EXISTS file_info (
                id          TEXT    NOT NULL UNIQUE,
                file_name   TEXT    NOT NULL PRIMARY KEY,
                file_path   TEXT    NOT NULL DEFAULT '',
                epoch_time  INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0
            ) WITHOUT ROWID;
        )";
        execute_sql(db, create_table_sql);

        // INSERT OR IGNORE handles uniqueness at DB level — no separate SELECT check needed.
        const std::string insert_sql = R"(
            INSERT OR IGNORE INTO file_info (id, file_name, file_path, epoch_time, chunk_count)
            VALUES (?, ?, ?, ?, ?);
        )";
        sqlite3_stmt *stmt;
        sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, nullptr);

        // Start a transaction for batch processing
        execute_sql(db, "BEGIN TRANSACTION;");

        bool trigger_once = true;
        for (const std::filesystem::path &file : filtered_files)
        {
            // Process the file
            DataInfo entry = {
                .file_name = file.stem().generic_string(),
                .file_path = file.generic_string(),
                .epoch_time = UPDATE_INFO::get_epoch_time(file),
                .chunk_count = UPDATE_INFO::count_chunk_for_each_title(db, entry.file_name + ".txt")};

            entry.id = UPDATE_INFO::create_unique_id(entry.file_path);

            // Bind the values to the statement
            sqlite3_bind_text(stmt, 1, entry.id.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 2, entry.file_name.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 3, entry.file_path.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_int(stmt, 4, entry.epoch_time);
            sqlite3_bind_int(stmt, 5, entry.chunk_count);

            if (sqlite3_step(stmt) != SQLITE_DONE)
                std::cerr << "Error inserting into file_info: " << sqlite3_errmsg(db) << std::endl;

            sqlite3_reset(stmt);

            // sqlite3_changes() == 0 means the row was a duplicate and was skipped
            const bool inserted = (sqlite3_changes(db) > 0);
            if (inserted)
            {
                if (trigger_once && is_dumped)
                {
                    UTILITIES_HPP::Basic::reset_file_info_dumper(ENV_HPP::data_info_path);
                    trigger_once = false;
                }
                if (is_dumped)
                    UTILITIES_HPP::Basic::data_info_dump(entry);
                if (show_progress)
                    std::cout << "Processed: " << file << std::endl;
            }
            else if (show_progress)
            {
                std::cout << "Skipped (file_name exists): " << entry.file_name << std::endl;
            }
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

            std::string relation_sql = "SELECT file_name, Token, relational_distance FROM relation_distance WHERE Token IN (" + token_in_clause + ");";
            sqlite3_stmt *rel_stmt = prepareStatement(db, relation_sql, "Error preparing statement (relation_distance)");
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
        catch (const std::exception &e)
        {
            std::cerr << "Error: " << e.what() << std::endl;
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
                FROM relation_distance
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

        // WITHOUT ROWID: word IS the PK B-tree key, so WHERE word=? is a single
        // B-tree lookup — no separate secondary index is needed.
        execute_sql(db,
                    "CREATE TABLE IF NOT EXISTS tf_idf ("
                    "word      TEXT    NOT NULL PRIMARY KEY, "
                    "id INTEGER AUTOINCREMENT, "
                    "freq      INTEGER NOT NULL DEFAULT 0, "
                    "doc_count INTEGER NOT NULL DEFAULT 0, "
                    "tf_idf    REAL    NOT NULL DEFAULT 0.0"
                    ") WITHOUT ROWID;");

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
            "SELECT token, COUNT(DISTINCT file_name) FROM relation_distance GROUP BY token;";

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
        query = "SELECT COUNT(DISTINCT file_name) FROM relation_distance;";

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
                           const bool reset_table = true)
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

        if (reset_table)
        {
            execute_sql(db, "DROP TABLE IF EXISTS item_matrix;");
        }
        // Be extra sure about there is always a table to process, otherwise the following code will break
        // PK order: (source_id, target_id) — range scans in expand_degree filter
        // by source first, so the PK B-tree must start with source_id.
        // CHECK eliminates invalid zero-score pairs at DB level.
        execute_sql(db,
                    "CREATE TABLE IF NOT EXISTS item_matrix ("
                    "source_id   TEXT NOT NULL, "
                    "source_name TEXT NOT NULL DEFAULT '', "
                    "target_id   TEXT NOT NULL, "
                    "target_name TEXT NOT NULL DEFAULT '', "
                    "distance    REAL NOT NULL DEFAULT 0.0 CHECK(distance > 0.0), "
                    "PRIMARY KEY (source_id, target_id)"
                    ") WITHOUT ROWID;");
        // // expand_degree JOINs on source_name and target_name — these indexes
        // // avoid full scans of the N^2 table on every degree expansion.
        // execute_sql(db,
        //             "CREATE INDEX IF NOT EXISTS idx_im_source_name "
        //             "ON item_matrix(source_name);");
        // execute_sql(db,
        //             "CREATE INDEX IF NOT EXISTS idx_im_target_name "
        //             "ON item_matrix(target_name);");

        std::map<std::string, std::string> unique_ids = RECOMMEND::collect_unique_id(db);
        std::map<std::string, std::string> processing_ids = RECOMMEND::collect_processing_id(db, reset_table, unique_ids, "SELECT DISTINCT source_id FROM item_matrix");
        std::map<std::string, std::string> comparison_list = unique_ids; // Copy of unique_ids for comparison

        std::cout << "Found " << processing_ids.size() << " files to process\n";

        for (const auto &id_pair : processing_ids)
        {
            // If found, process the id_pair
            const std::string &id = id_pair.first;
            const std::string &file_name = id_pair.second;
            std::vector<std::tuple<std::string, std::string, std::string, std::string, double>> result;

            auto filtered_tokens = RECOMMEND::load_token_map(db, id);
            if (filtered_tokens.empty())
                continue;

            RECOMMEND::apply_tfidf(db, filtered_tokens);
            auto relation_distance_map = RECOMMEND::load_related_tokens(db, filtered_tokens);
            std::vector<std::tuple<std::string, std::string, double>> results = RECOMMEND::compute_recommendations(filtered_tokens, relation_distance_map, id, comparison_list);

            for (const auto &[target_id, target_name, distance] : results)
            {
                std::tuple<std::string, std::string, std::string, std::string, double> row =
                    {target_id, target_name, id, file_name, distance};
                result.push_back(row);
            }

            comparison_list.erase(id); // Remove the current id from comparison list to speed up the iteration

            execute_sql(db, "BEGIN;");
            RECOMMEND::insert_item_matrix(result, db);
            execute_sql(db, "COMMIT;");

            if (show_progress)
                std::cout << id << std::endl;
        }

        sqlite3_close(db);
    }

    void label_topics(bool show_progress, bool reset_table)
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

        // Create or reset the tags table
        if (reset_table)
        {
            std::string drop_table_sql = "DROP TABLE IF EXISTS tags_full";
            execute_sql(db, drop_table_sql);
        }

        std::string create_full_table_sql = R"(
            CREATE TABLE IF NOT EXISTS tags_full (
                name     TEXT NOT NULL DEFAULT '',
                ID       TEXT NOT NULL,
                distance REAL NOT NULL DEFAULT 0.0 CHECK(distance > 0.0 AND distance <= 1.0),
                topic    TEXT NOT NULL,
                PRIMARY KEY (ID, topic)
            ) WITHOUT ROWID;
        )";
        execute_sql(db, create_full_table_sql);
        // // Index used by iterative_topic_expansion when it queries tags_full(ID, topic)
        // execute_sql(db,
        //             "CREATE INDEX IF NOT EXISTS idx_tags_full_id_topic "
        //             "ON tags_full(ID, topic);");

        std::map<std::string, std::string> unique_ids = RECOMMEND::collect_unique_id(db);
        std::vector<std::string> unique_topics = RECOMMEND::collect_unique_topic(db);
        std::map<std::string, std::string> processing_ids = RECOMMEND::collect_processing_id(db, reset_table, unique_ids, "SELECT DISTINCT ID FROM tags_full");

        for (const std::string &topic : unique_topics)
        {
            auto filtered_tokens = RECOMMEND::load_topic_token_map(db, topic);
            if (filtered_tokens.empty())
                continue;

            RECOMMEND::apply_tfidf(db, filtered_tokens);
            auto relation_distance_map = RECOMMEND::load_related_tokens(db, filtered_tokens);
            std::vector<std::tuple<std::string, std::string, double>> recommendations = RECOMMEND::compute_recommendations(filtered_tokens, relation_distance_map, topic, processing_ids);

            execute_sql(db, "BEGIN;");
            RECOMMEND::insert_tags_full(recommendations, topic, db);
            execute_sql(db, "COMMIT;");

            if (show_progress)
                std::cout << "Completed Topic: " << topic << ", Tokens: " << filtered_tokens.size() << std::endl;
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

        if (reset_table)
            execute_sql(db, "DROP TABLE IF EXISTS tags;");

        // -------------------------------------------------
        // Create optimized tags table
        // -------------------------------------------------
        std::string create_table_sql = R"(
        CREATE TABLE IF NOT EXISTS tags (
            name     TEXT NOT NULL,
            ID       TEXT NOT NULL,
            distance REAL NOT NULL CHECK(distance > 0 AND distance <= 1),
            topic    TEXT NOT NULL,
            degree   INTEGER NOT NULL CHECK(degree >= 1),
            PRIMARY KEY (ID, topic)
        ) WITHOUT ROWID;
        )";

        execute_sql(db, create_table_sql);

        // -------------------------------------------------
        // Required indexes
        // -------------------------------------------------
        execute_sql(db,
                    "CREATE INDEX IF NOT EXISTS idx_tags_degree "
                    "ON tags(degree);");

        execute_sql(db,
                    "CREATE INDEX IF NOT EXISTS idx_imf_source "
                    "ON item_matrix_filtered(source_name);");

        execute_sql(db,
                    "CREATE INDEX IF NOT EXISTS idx_imf_target "
                    "ON item_matrix_filtered(target_name);");

        execute_sql(db,
                    "CREATE INDEX IF NOT EXISTS idx_tf_id_topic "
                    "ON tags_full(ID, topic);");

        std::cout << "Database setup completed. Starting iterative topic expansion..." << std::endl;
        // -------------------------------------------------
        // Degree 1 (seed)
        // -------------------------------------------------
        const char *insert_degree1_sql = R"(
            INSERT OR IGNORE INTO tags (name, ID, distance, topic, degree)
            SELECT name, ID, distance, topic, 1
            FROM tags_full
            WHERE distance >= ?;
        )";

        execute_sql(db, "BEGIN;");

        sqlite3_stmt *stmt = nullptr;
        sqlite3_prepare_v2(db, insert_degree1_sql, -1, &stmt, nullptr);
        sqlite3_bind_double(stmt, 1, threshold_degree1);
        sqlite3_step(stmt);
        sqlite3_finalize(stmt);

        execute_sql(db, "COMMIT;");
        std::cout << "Completed expanding to degree 1 (seed)" << std::endl;

        // -------------------------------------------------
        // Iterative Expansion
        // -------------------------------------------------
        for (int degree = 1; degree <= max_degree; ++degree)
        {
            execute_sql(db, "BEGIN;");
            RECOMMEND::expand_degree(db, degree, degree + 1, threshold);
            execute_sql(db, "COMMIT;");

            std::cout << "Completed expanding to degree " << degree + 1 << std::endl;
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

        // STEP 1: Indexes (optimized for your workload)
        std::cout << "[STEP 1] Creating indexes...\n";
        execute_sql(db, R"(
            CREATE INDEX IF NOT EXISTS idx_rd_token_freq 
            ON relation_distance(token, frequency);

            CREATE INDEX IF NOT EXISTS idx_rd_file_freq 
            ON relation_distance(file_name, frequency);

            CREATE INDEX IF NOT EXISTS idx_rd_freq 
            ON relation_distance(frequency);

            CREATE INDEX IF NOT EXISTS idx_tfidf_freq 
            ON tf_idf(freq);
        )");

        execute_sql(db, "BEGIN;");

        // STEP 2: Frequency distribution (direct)
        std::cout << "[STEP 2] Building freq_dist...\n";
        execute_sql(db, R"(
            DROP TABLE IF EXISTS freq_dist;
            CREATE TABLE freq_dist AS
            SELECT frequency AS freq, COUNT(*) AS cnt, SUM(frequency) AS total_freq
            FROM relation_distance
            GROUP BY frequency;
        )");

        // STEP 3: Token distribution
        std::cout << "[STEP 3] Building token_dist...\n";
        execute_sql(db, R"(
            DROP TABLE IF EXISTS token_dist;
            CREATE TABLE token_dist AS
            SELECT MAX(frequency) AS freq, COUNT(*) AS cnt
            FROM relation_distance
            GROUP BY token;
        )");

        // STEP 4: File distribution
        std::cout << "[STEP 4] Building file_dist...\n";
        execute_sql(db, R"(
            DROP TABLE IF EXISTS file_dist;
            CREATE TABLE file_dist AS
            SELECT MAX(frequency) AS freq, COUNT(*) AS cnt
            FROM relation_distance
            GROUP BY file_name;
        )");

        // STEP 5: Word distribution (simplified due to PK(word))
        std::cout << "[STEP 5] Building word_dist...\n";
        execute_sql(db, R"(
            DROP TABLE IF EXISTS word_dist;
            CREATE TABLE word_dist AS
            SELECT freq, COUNT(*) AS cnt
            FROM tf_idf
            GROUP BY freq;
        )");

        // STEP 6: Totals
        std::cout << "[STEP 6] Computing totals...\n";
        execute_sql(db, R"(
            DROP TABLE IF EXISTS totals;
            CREATE TABLE totals AS
            SELECT 
                (SELECT SUM(total_freq) FROM freq_dist) AS total_freq,
                (SELECT SUM(cnt) FROM token_dist) AS total_tokens,
                (SELECT SUM(cnt) FROM file_dist) AS total_files,
                (SELECT SUM(cnt) FROM word_dist) AS total_words;
        )");

        // STEP 7: Final cutoff table
        std::cout << "[STEP 7] Computing cutoff_analysis...\n";
        execute_sql(db, R"(
            DROP TABLE IF EXISTS cutoff_analysis;

            CREATE TABLE cutoff_analysis AS
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

        std::cout << "[DONE] cutoff_analysis ready.\n";

        sqlite3_close(db);
    }
}
#endif // FEATURE_HPP