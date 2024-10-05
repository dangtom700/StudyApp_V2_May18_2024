#ifndef FEATURE_HPP
#define FEATURE_HPP

#include <filesystem>
#include <vector>
#include <map>
#include <fstream>
#include <memory> // For smart pointers
#include <sqlite3.h>

#include "utilities.hpp"
#include "env.hpp"
#include "transform.hpp"
#include "updateDB.hpp"

namespace FEATURE {
    void execute_sql(sqlite3* db, const std::string& sql) {
        char* errMsg;
        int exit = sqlite3_exec(db, sql.c_str(), nullptr, 0, &errMsg);
        if (exit != SQLITE_OK) {
            std::cerr << "Error executing SQL: " << errMsg << std::endl;
            sqlite3_free(errMsg);
        }
    }

    void computeRelationalDistance(const std::vector<std::filesystem::path>& filtered_files,
                                const bool show_progress = true,
                                const bool reset_table = true,
                                const bool is_dumped = true) {
        try {
            // Set up SQLite database connection
            sqlite3* db;
            int exit = sqlite3_open(ENV_HPP::database_path.string().c_str(), &db);
            if (exit) {
                std::cerr << "Error opening SQLite database: " << sqlite3_errmsg(db) << std::endl;
                return;
            }

            // Create table if reset_table is true
            if (reset_table) {
                std::string create_table_sql = R"(
                    DROP TABLE IF EXISTS DataDump;
                    CREATE TABLE IF NOT EXISTS DataDump (
                        file_name TEXT PRIMARY KEY
                        Total_tokens INTEGER
                        Unique_tokens INTEGER
                        Relational_distance REAL
                    );
                )";
                
                execute_sql(db, create_table_sql);
                std::cout << "Table created successfully" << std::endl;

                create_table_sql = R"(
                    DROP TABLE IF EXISTS RelationalDistance;
                    CREATE TABLE IF NOT EXISTS RelationalDistance (
                        file_name TEXT PRIMARY KEY
                        Token TEST PRIMARY KEY
                        Frequency INTEGER
                        Relational_distance REAL
                    );
                )";
                execute_sql(db, create_table_sql);
                std::cout << "Table created successfully" << std::endl;
            }

            bool tirgger_once = true;
            for (const std::filesystem::path& file : filtered_files) {
                if (tirgger_once && is_dumped) {
                    tirgger_once = false;
                    UTILITIES_HPP::Basic::reset_data_dumper(ENV_HPP::data_dumper_path);
                }

                std::map<std::string, int> json_map = TRANSFORMER::json_to_map(file);

                DataEntry row = {
                    .path = file,
                    .sum = TRANSFORMER::compute_sum_token_json(json_map),
                    .num_unique_tokens = TRANSFORMER::count_unique_tokens(json_map),
                    .relational_distance = TRANSFORMER::Pythagoras(json_map),
                };
                
                row.filtered_tokens = TRANSFORMER::token_filter(json_map,
                                                                ENV_HPP::max_length,
                                                                ENV_HPP::min_value,
                                                                row.relational_distance);

                // Dump the contents of a DataEntry to a file
                if(is_dumped) UTILITIES_HPP::Basic::data_entry_dump(row);

                // Update or insert the row into the database
                if (reset_table) {
                    // Insert the row into the database
                    std::string insert_sql = R"(
                        INSERT INTO DataDump (file_name, Total_tokens, Unique_tokens, Relational_distance)
                        VALUES (?, ?, ?, ?);
                    )";
                    sqlite3_stmt* stmt;
                    sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, NULL);
                    sqlite3_bind_text(stmt, 1, row.path.string().c_str(), -1, SQLITE_STATIC);
                    sqlite3_bind_int(stmt, 2, row.sum);
                    sqlite3_bind_int(stmt, 3, row.num_unique_tokens);
                    sqlite3_bind_double(stmt, 4, row.relational_distance);
                    sqlite3_step(stmt);
                    sqlite3_finalize(stmt);

                    // Insert the filtered token into a dedicated table
                    insert_sql = R"(
                        INSERT INTO RelationalDistance (file_name, Token, Frequency, Relational_distance)
                        VALUES (?, ?, ?, ?);
                    )";
                    stmt;
                    sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, NULL);

                    for (const std::tuple<std::string, int, double>& token : row.filtered_tokens) {
                        sqlite3_bind_text(stmt, 1, row.path.string().c_str(), -1, SQLITE_STATIC);
                        sqlite3_bind_text(stmt, 2, std::get<0>(token).c_str(), -1, SQLITE_STATIC);
                        sqlite3_bind_int(stmt, 3, std::get<1>(token));
                        sqlite3_bind_double(stmt, 4, std::get<2>(token));
                        sqlite3_step(stmt);
                    }
                    sqlite3_finalize(stmt);
                } else {
                    // Update or append the row into the database
                    std::string update_sql = R"(
                        UPDATE DataDump
                        SET Total_tokens = ?, Unique_tokens = ?, Relational_distance = ?
                        WHERE file_name = ?;
                    )";
                    sqlite3_stmt* stmt;
                    sqlite3_prepare_v2(db, update_sql.c_str(), -1, &stmt, NULL);
                    sqlite3_bind_int(stmt, 1, row.sum);
                    sqlite3_bind_int(stmt, 2, row.num_unique_tokens);
                    sqlite3_bind_double(stmt, 3, row.relational_distance);
                    sqlite3_bind_text(stmt, 4, row.path.string().c_str(), -1, SQLITE_STATIC);
                    sqlite3_step(stmt);
                    sqlite3_finalize(stmt);

                    // Update or append the filtered token into a dedicated table
                    update_sql = R"(
                        UPDATE RelationalDistance
                        SET Frequency = ?, Relational_distance = ?
                        WHERE file_name = ? AND Token = ?;
                    )";
                    stmt;
                    sqlite3_prepare_v2(db, update_sql.c_str(), -1, &stmt, NULL);
                    for (const std::tuple<std::string, int, double>& token : row.filtered_tokens) {
                        sqlite3_bind_int(stmt, 1, std::get<1>(token));
                        sqlite3_bind_double(stmt, 2, std::get<2>(token));
                        sqlite3_bind_text(stmt, 3, row.path.string().c_str(), -1, SQLITE_STATIC);
                        sqlite3_bind_text(stmt, 4, std::get<0>(token).c_str(), -1, SQLITE_STATIC);
                        sqlite3_step(stmt);
                    }
                    sqlite3_finalize(stmt);
                }

                if (show_progress) std::cout << "Processed: " << file << std::endl;
            }
            sqlite3_close(db);
            std::cout << "Computing relational distance data finished" << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "Error: " << e.what() << std::endl;
        }
    }


    void computeResourceData(const std::vector<std::filesystem::path>& filtered_files,
                             const bool& show_progress = true,
                             const bool& reset_table = true,
                             const bool& is_dumped = true) {
        try{
            // Connect to the database
            sqlite3* db;
            int exit = sqlite3_open(ENV_HPP::database_path.string().c_str(), &db);
            if (exit != SQLITE_OK) {
                std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
                sqlite3_close(db);
                return;
            }
            
            if (reset_table) {
                std::string create_table_sql = R"(
                    CREATE TABLE IF NOT EXISTS FILE_INFO (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    last_write_time TEXT NOT NULL,
                    epoch_time INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    starting_id INTEGER NOT NULL,
                    ending_id INTEGER NOT NULL
                    );
                )";
                execute_sql(db, create_table_sql);
            }

            
        } catch (const std::exception& e) {
            std::cerr << "Error: " << e.what() << std::endl;
        }
    }
}

#endif // FEATURE_HPP