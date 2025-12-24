#ifndef FEATURE_HPP
#define FEATURE_HPP

#include <filesystem>
#include <vector>
#include <map>
#include <fstream>
#include <memory> // For smart pointers
#include <sqlite3.h>
#include <unordered_map>
#include <mutex>
#include <thread>

#include "utilities.hpp"
#include "env.hpp"
#include "transform.hpp"
#include "updateDB.hpp"
#include "tagging.hpp"

namespace FEATURE {
    
    /**
     * Execute a SQL query on the given database.
     *
     * @param db The database to execute the query on.
     * @param sql The SQL query to execute.
     *
     * @throws std::runtime_error if the query fails with an error message.
     */
    void execute_sql(sqlite3* db, const std::string& sql) {
        char* error_message = nullptr;
        int exit = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &error_message);
        if (exit != SQLITE_OK) {
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
    sqlite3_stmt* prepareStatement(sqlite3* db, const std::string& query, const std::string& content) {
        sqlite3_stmt* stmt = nullptr;
        int rc = sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr);
        if (rc != SQLITE_OK) {
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
    void computeRelationalDistance(const std::vector<std::filesystem::path>& filtered_files,
                                const bool& show_progress = true,
                                const bool& reset_table = true,
                                const bool& is_dumped = true) {
        try {
            // Set up SQLite database connection
            sqlite3* db;
            int exit = sqlite3_open(ENV_HPP::database_path.string().c_str(), &db);
            if (exit) {
                std::cerr << "Error opening SQLite database: " << sqlite3_errmsg(db) << std::endl;
                return;
            }

            // Disable synchronous mode to speed up inserts (optional)
            execute_sql(db, "PRAGMA synchronous = OFF;");

            // Create tables if reset_table is true
            if (reset_table) {
                std::string create_table_sql = R"(
                    DROP TABLE IF EXISTS file_token;
                    CREATE TABLE IF NOT EXISTS file_token (
                        file_name TEXT PRIMARY KEY,
                        total_tokens INTEGER,
                        unique_tokens INTEGER,
                        relational_distance REAL
                    );
                )";
                execute_sql(db, create_table_sql);

                create_table_sql = R"(
                    DROP TABLE IF EXISTS relation_distance;
                    CREATE TABLE IF NOT EXISTS relation_distance (
                        file_name TEXT,
                        token TEXT,
                        frequency INTEGER,
                        relational_distance REAL,
                        PRIMARY KEY (file_name, Token)
                    );
                )";
                execute_sql(db, create_table_sql);
                std::cout << "Tables created successfully" << std::endl;
            }

            // Start a transaction to speed up multiple inserts
            execute_sql(db, "BEGIN TRANSACTION;");

            bool trigger_once = true;
            for (const std::filesystem::path& file : filtered_files) {
                if (trigger_once && is_dumped) {
                    trigger_once = false;
                    UTILITIES_HPP::Basic::reset_data_dumper(ENV_HPP::data_dumper_path);
                }

                std::map<std::string, int> json_map = TRANSFORMER::json_to_map(file);
                
                for (auto it = json_map.begin(); it != json_map.end();) {
                    const std::string& key = it->first;
                    const int value = it->second;

                    if (value < ENV_HPP::min_value || key.length() > ENV_HPP::max_length || 
                        !std::all_of(key.begin(), key.end(), [](char c) { return c >= 'a' && c <= 'z'; })) {
                        it = json_map.erase(it); // Safely erase invalid entries
                    } else {
                        ++it; // Move to the next element
                    }
                }

                DataEntry row = {
                    .path = file.stem().generic_string(),
                    .sum = TRANSFORMER::compute_sum_token_json(json_map),
                    .num_unique_tokens = TRANSFORMER::count_unique_tokens(json_map),
                    .relational_distance = TRANSFORMER::Pythagoras(json_map),
                };

                // Compute the relational distance of each token
                // Double gated to filter tokens
                row.filtered_tokens = TRANSFORMER::token_filter(json_map, ENV_HPP::max_length, ENV_HPP::min_value, row.relational_distance);

                // Dump the contents of a DataEntry to a file
                if (is_dumped) UTILITIES_HPP::Basic::data_entry_dump(row);

                // Insert the row into file_token table using a prepared statement
                std::string insert_sql = R"(
                    INSERT OR REPLACE INTO file_token (file_name, total_tokens, unique_tokens, relational_distance)
                    VALUES (?, ?, ?, ?);
                )";
                sqlite3_stmt* stmt;
                sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, nullptr);
                sqlite3_bind_text(stmt, 1, row.path.c_str(), -1, SQLITE_STATIC);
                sqlite3_bind_int(stmt, 2, row.sum);
                sqlite3_bind_int(stmt, 3, row.num_unique_tokens);
                sqlite3_bind_double(stmt, 4, row.relational_distance);
                sqlite3_step(stmt);
                sqlite3_finalize(stmt);

                // Insert the filtered tokens into relation_distance table using a prepared statement
                insert_sql = R"(
                    INSERT OR REPLACE INTO relation_distance (file_name, token, frequency, relational_distance)
                    VALUES (?, ?, ?, ?);
                )";
                sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, nullptr);
                for (const auto& token : row.filtered_tokens) {
                    sqlite3_bind_text(stmt, 1, row.path.c_str(), -1, SQLITE_STATIC);
                    sqlite3_bind_text(stmt, 2, std::get<0>(token).c_str(), -1, SQLITE_STATIC);
                    sqlite3_bind_int(stmt, 3, std::get<1>(token));
                    sqlite3_bind_double(stmt, 4, std::get<2>(token));
                    sqlite3_step(stmt);
                    sqlite3_reset(stmt); // Reset the statement for re-use
                }
                sqlite3_finalize(stmt);

                if (show_progress) {
                    std::cout << "Processed: " << file << std::endl;
                }

                // Remove the file from the directory
                std::filesystem::remove(file);
            }

            // Commit the transaction to apply all inserts
            execute_sql(db, "COMMIT TRANSACTION;");

            // Re-enable synchronous mode (optional, depending on your use case)
            execute_sql(db, "PRAGMA synchronous = FULL;");

            // Close the SQLite database connection
            sqlite3_close(db);
            std::cout << "Computing relational distance data finished" << std::endl;
        } catch (const std::exception& e) {
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
    void computeResourceData(const std::vector<std::filesystem::path>& filtered_files,
                         const bool& show_progress = true,
                         const bool& reset_table = false,
                         const bool& is_dumped = true) {
        // Connect to the database
        sqlite3* db;
        int exit = sqlite3_open(ENV_HPP::database_path.string().c_str(), &db);
        if (exit != SQLITE_OK) {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return;
        }

        // Disable synchronous mode for faster inserts
        execute_sql(db, "PRAGMA synchronous = OFF;");

        // Create or reset the table if required
        if (reset_table) {
            std::string create_table_sql = R"(
                DROP TABLE IF EXISTS file_info;
                CREATE TABLE IF NOT EXISTS file_info (
                    id TEXT NOT NULL,
                    file_name TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    epoch_time INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL
                );
            )";
            execute_sql(db, create_table_sql);
        }

        // Start a transaction for batch processing
        execute_sql(db, "BEGIN TRANSACTION;");

        // Prepare the insert statement (using "INSERT OR IGNORE" to handle both insert/update)
        std::string insert_sql = R"(
            INSERT OR IGNORE INTO file_info (id, file_name, file_path, epoch_time, chunk_count)
            VALUES (?, ?, ?, ?, ?);
        )";
        sqlite3_stmt* stmt;
        sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, nullptr);

        std::string exists_sql = R"(
            SELECT 1 FROM file_info
            WHERE file_name = ?
            LIMIT 1;
        )";
        sqlite3_stmt* exists_stmt;
        sqlite3_prepare_v2(db, exists_sql.c_str(), -1, &exists_stmt, nullptr);


        bool trigger_once = true;
        for (const std::filesystem::path& file : filtered_files) {
            // Check file existed in table, yes to skip
            std::string file_name = file.stem().generic_string();

            // Bind
            sqlite3_bind_text(
                exists_stmt, 1,
                file_name.c_str(),
                -1, SQLITE_STATIC
            );

            // Check
            bool exists = (sqlite3_step(exists_stmt) == SQLITE_ROW);

            // Reset
            sqlite3_reset(exists_stmt);
            sqlite3_clear_bindings(exists_stmt);

            if (exists) {
                if (show_progress) {
                    std::cout << "Skipped (file_name exists): " << file_name << std::endl;
                }
                continue;
            }

            if (trigger_once && is_dumped) {
                UTILITIES_HPP::Basic::reset_file_info_dumper(ENV_HPP::data_info_path);
                trigger_once = false;
            }

            // Process the file
            DataInfo entry = {
                .file_name = file.stem().generic_string(),
                .file_path = file.generic_string(),
                .epoch_time = UPDATE_INFO::get_epoch_time(file),
                .chunk_count = UPDATE_INFO::count_chunk_for_each_title(db, entry.file_name+".txt")
            };

            entry.id = UPDATE_INFO::create_unique_id(entry.file_path);
            // Export data info if needed
            if (is_dumped) UTILITIES_HPP::Basic::data_info_dump(entry);

            // Bind the values to the statement
            sqlite3_bind_text(stmt, 1, entry.id.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 2, entry.file_name.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_text(stmt, 3, entry.file_path.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_int(stmt, 4, entry.epoch_time);
            sqlite3_bind_int(stmt, 5, entry.chunk_count);

            // Execute the statement
            if (sqlite3_step(stmt) != SQLITE_DONE) {
                std::cerr << "Error inserting into file_info: " << sqlite3_errmsg(db) << std::endl;
            }

            // Reset the statement to use it again
            sqlite3_reset(stmt);

            if (show_progress) {
                std::cout << "Processed: " << file << std::endl;
            }
        }

        // Finalize the prepared statement
        sqlite3_finalize(stmt);
        sqlite3_finalize(exists_stmt);

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
     * @param top_n The number of top results to output
    */
    void processPrompt(const int& top_n) {
        try {
            // Step 1: Token preparation
            std::map<std::string, int> tokens = TRANSFORMER::json_to_map(ENV_HPP::buffer_json_path);
            int distance = TRANSFORMER::Pythagoras(tokens);
            std::vector<std::tuple<std::string, int, double>> filtered_tokens = TRANSFORMER::token_filter(tokens, 16, 1, distance);
            tokens.clear();
    
            // Step 2: Open database
            std::ofstream output_file(ENV_HPP::outputPrompt);
            output_file << ""; // Clear the file
            
            sqlite3* db;
            if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
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
            sqlite3_stmt* file_stmt = prepareStatement(db, file_info_sql, "Error preparing statement (file_info)");
            if (!file_stmt) {
                sqlite3_close(db);
                return;
            }
    
            // Step 4: Load relation_distance map
            std::map<std::string, std::map<std::string, double>> relation_distance_map;
            std::string token_in_clause;
            for (const auto& [token, _, __] : filtered_tokens)
                token_in_clause += "'" + token + "',";
            if (!token_in_clause.empty()) token_in_clause.pop_back();
    
            std::string relation_sql = "SELECT file_name, Token, relational_distance FROM relation_distance WHERE Token IN (" + token_in_clause + ");";
            sqlite3_stmt* rel_stmt = prepareStatement(db, relation_sql, "Error preparing statement (relation_distance)");
            if (!rel_stmt) {
                sqlite3_finalize(file_stmt);
                sqlite3_close(db);
                return;
            }
    
            while (sqlite3_step(rel_stmt) == SQLITE_ROW) {
                std::string rel_file = reinterpret_cast<const char*>(sqlite3_column_text(rel_stmt, 0));
                std::string token = reinterpret_cast<const char*>(sqlite3_column_text(rel_stmt, 1));
                double rel_dist = sqlite3_column_double(rel_stmt, 2);
                relation_distance_map[rel_file][token] = rel_dist;
            }

            sqlite3_finalize(rel_stmt);
    
            // Step 5: Load TF-IDF values
            std::string tfidf_sql = "SELECT tf_idf FROM tf_idf WHERE word = ?;";
            sqlite3_stmt* tfidf_stmt = prepareStatement(db, tfidf_sql, "Error preparing statement (tf_idf)");
            if (!tfidf_stmt) {
                sqlite3_finalize(file_stmt);
                sqlite3_close(db);
                return;
            }
    
            for (auto& [token, freq, base_distance] : filtered_tokens) {
                sqlite3_reset(tfidf_stmt);
                sqlite3_bind_text(tfidf_stmt, 1, token.c_str(), -1, SQLITE_TRANSIENT);
                if (sqlite3_step(tfidf_stmt) == SQLITE_ROW) {
                    double tfidf = sqlite3_column_double(tfidf_stmt, 0);
                    // Adjust to 0.0 if TF-IDF value is not found
                    if (std::isnan(tfidf)) tfidf = 0.0;
                    // Update base_distance with addition of TF-IDF value
                    base_distance += tfidf / freq;
                }
            }
            sqlite3_finalize(tfidf_stmt);
    
            // Step 6: Compute scores
            std::vector<std::tuple<std::string, std::string, double>> RESULT;
    
            while (sqlite3_step(file_stmt) == SQLITE_ROW) {
                std::string id(reinterpret_cast<const char*>(sqlite3_column_text(file_stmt, 0)));
                std::string file_name(reinterpret_cast<const char*>(sqlite3_column_text(file_stmt, 1)));
    
                std::string rel_file_key = "title_" + id;
                if (relation_distance_map.find(rel_file_key) == relation_distance_map.end()) continue;
    
                double score = 0.0;
                const auto& token_map = relation_distance_map[rel_file_key];
    
                for (const auto& [token, _, base_distance] : filtered_tokens) {
                    auto rel_it = token_map.find(token);
                    if (rel_it == token_map.end()) continue;
    
                    double rel_dist = rel_it->second;
                    score += rel_dist * base_distance;
                }
    
                if (score > 0.0) {
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
            std::sort(RESULT.begin(), RESULT.end(), [](const auto& a, const auto& b) {
                return std::get<2>(a) > std::get<2>(b);
            });
    
            uint16_t top_n_value = std::min(static_cast<uint16_t>(RESULT.size()), static_cast<uint16_t>(top_n));
            output_file << "Top " << top_n_value << " Results:\n"
                        << "-----------------------------------------------------------------\n";
            for (uint16_t i = 0; i < top_n_value; i++) {
                output_file << "ID: " << std::get<0>(RESULT[i]) << "\n"
                            << "Distance: " << std::get<2>(RESULT[i]) << "\n"
                            << "Rank: " << i + 1 << "\n"
                            << "Name: [[" << std::get<1>(RESULT[i]) << "]]\n"
                            << "-----------------------------------------------------------------\n";
            }
    
        } catch (const std::exception& e) {
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
    std::vector<std::filesystem::path> skim_files(std::vector<std::filesystem::path>& files, const std::string& extension) {
        // Step 1: Open the database connection
        sqlite3* db;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            return files; // Return the original list if the database cannot be opened
        }

        // Step 2: Prepare the SQL query to fetch all file names in the database
        std::string fetch_sql;
        if (extension == ".pdf") {
            fetch_sql = R"(
                SELECT DISTINCT file_name 
                FROM file_info
            )";
        } else if (extension == ".json") {
            fetch_sql = R"(
                SELECT DISTINCT file_name 
                FROM relation_distance
            )";
        } else {
            std::cerr << "Unsupported extension: " << extension << std::endl;
            sqlite3_close(db);
            return files; // Return the original list if the extension is unsupported
        }

        // Prepare the SQL statement
        sqlite3_stmt* stmt;
        if (sqlite3_prepare_v2(db, fetch_sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "Error preparing SQL statement: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return files; // Return the original list if the statement cannot be prepared
        }

        // Step 3: Retrieve all entries from the database
        std::unordered_set<std::string> db_files;
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* db_file = sqlite3_column_text(stmt, 0);
            if (db_file) {
                db_files.insert(reinterpret_cast<const char*>(db_file));
            }
        }

        // Finalize the statement and close the database connection
        sqlite3_finalize(stmt);
        sqlite3_close(db);

        // Step 4: Filter the files based on the database entries
        auto filter_condition = [&db_files, &extension](const std::filesystem::path& file) {
            if (file.extension() == extension) {
                // Remove the extension and compare with database values
                std::string file_name_no_ext = file.filename().stem().string(); // Strips the extension
                return !(db_files.find(file_name_no_ext) == db_files.end()); // Return true if not in database
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
    void computeTFIDF(const uint16_t& MIN_THRES_FREQ = 4,
                      const uint16_t& BUFFER_SIZE = 1000) {

        const std::string& chunk_database_path = ENV_HPP::database_path.string();
        const std::string& GLOBAL_JSON_PATH = ENV_HPP::global_terms_path.string();

        sqlite3* db;
        if (sqlite3_open(chunk_database_path.c_str(), &db) != SQLITE_OK) {
            std::cerr << "Can't open database\n";
            return;
        }

        // Speed optimizations
        execute_sql(db, "PRAGMA journal_mode=WAL;");
        execute_sql(db, "PRAGMA synchronous = OFF;");

        // Create tf_idf table
        execute_sql(db,
            "CREATE TABLE IF NOT EXISTS tf_idf ("
            "word TEXT PRIMARY KEY, "
            "freq INTEGER, "
            "doc_count INTEGER, "
            "tf_idf REAL)"
        );

        // Load JSON
        std::ifstream inputFile(GLOBAL_JSON_PATH);
        json global_word_freq;
        inputFile >> global_word_freq;

        std::map<std::string, int> filtered_words;
        for (auto& [word, freq] : global_word_freq.items()) {
            if (freq >= MIN_THRES_FREQ && word.length() > 1) {
                filtered_words[word] = freq;
            }
        }

        int sum_freq = 0;
        for (const auto& [word, freq] : filtered_words) {
            sum_freq += freq;
        }

        // Get doc count per token
        std::map<std::string, int> word_doc_counts;
        sqlite3_stmt* stmt;

        std::string query = "SELECT token, COUNT(DISTINCT file_name) FROM relation_distance GROUP BY token;";
        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr) == SQLITE_OK) {
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                std::string token(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
                int count = sqlite3_column_int(stmt, 1);
                word_doc_counts[token] = count;
            }
        }
        sqlite3_finalize(stmt);

        // Get total number of documents
        int total_docs = 0;
        query = "SELECT COUNT(DISTINCT file_name) FROM relation_distance;";
        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr) == SQLITE_OK &&
            sqlite3_step(stmt) == SQLITE_ROW) {
            total_docs = sqlite3_column_int(stmt, 0);
        }
        sqlite3_finalize(stmt);

        // Begin transaction
        execute_sql(db, "BEGIN TRANSACTION;");
        std::vector<TFIDFRecord> buffer;

        for (const auto& [word, freq] : filtered_words) {
            int doc_count = word_doc_counts[word];
            double tf = static_cast<double>(freq) / sum_freq;
            double idf = log10((total_docs + 1.0) / (doc_count + 1.0)) + 1.0;
            double tf_idf = tf * idf;

            buffer.push_back({word, freq, doc_count, tf_idf});

            if (buffer.size() >= BUFFER_SIZE) {
                sqlite3_stmt* insertStmt;
                std::string sql = 
                    "INSERT INTO tf_idf (word, freq, doc_count, tf_idf) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(word) DO UPDATE SET "
                    "freq=excluded.freq, doc_count=excluded.doc_count, tf_idf=excluded.tf_idf;";
                sqlite3_prepare_v2(db, sql.c_str(), -1, &insertStmt, nullptr);

                for (const auto& record : buffer) {
                    sqlite3_bind_text(insertStmt, 1, record.word.c_str(), -1, SQLITE_TRANSIENT);
                    sqlite3_bind_int(insertStmt, 2, record.freq);
                    sqlite3_bind_int(insertStmt, 3, record.doc_count);
                    sqlite3_bind_double(insertStmt, 4, record.tf_idf);

                    sqlite3_step(insertStmt);
                    sqlite3_reset(insertStmt);
                }

                sqlite3_finalize(insertStmt);
                buffer.clear();
            }
        }

        // Insert remaining records
        if (!buffer.empty()) {
            sqlite3_stmt* insertStmt;
            std::string sql = 
                "INSERT INTO tf_idf (word, freq, doc_count, tf_idf) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(word) DO UPDATE SET "
                "freq=excluded.freq, doc_count=excluded.doc_count, tf_idf=excluded.tf_idf;";
            sqlite3_prepare_v2(db, sql.c_str(), -1, &insertStmt, nullptr);

            for (const auto& record : buffer) {
                sqlite3_bind_text(insertStmt, 1, record.word.c_str(), -1, SQLITE_TRANSIENT);
                sqlite3_bind_int(insertStmt, 2, record.freq);
                sqlite3_bind_int(insertStmt, 3, record.doc_count);
                sqlite3_bind_double(insertStmt, 4, record.tf_idf);

                sqlite3_step(insertStmt);
                sqlite3_reset(insertStmt);
            }

            sqlite3_finalize(insertStmt);
        }

        // Finalize
        execute_sql(db, "COMMIT;");
        sqlite3_close(db);

        std::cout << "TF-IDF computation completed." << std::endl;
    }

}

#endif // FEATURE_HPP