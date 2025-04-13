#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <map>
#include <sqlite3.h>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>
#include <tuple>

#include "utilities.hpp"

namespace Tagging{
    // Fetch unique titles
    std::vector<std::string> fetch_unique_titles(sqlite3* db) {
        std::vector<std::string> unique_titles;
        sqlite3_stmt* stmt;
        const char* query = "SELECT DISTINCT file_name FROM file_token";

        if (sqlite3_prepare_v2(db, query, -1, &stmt, nullptr) == SQLITE_OK) {
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                unique_titles.emplace_back(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
            }
        } else {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl;
        }

        sqlite3_finalize(stmt);
        return unique_titles;
    }

    // Fetch data in chunks for efficiency
    void fetch_all_data(sqlite3* db, std::unordered_map<std::string, std::unordered_map<std::string, float>>& data) {
        sqlite3_stmt* stmt;
        const char* query = "SELECT file_name, token, relational_distance FROM relation_distance";

        if (sqlite3_prepare_v2(db, query, -1, &stmt, nullptr) == SQLITE_OK) {
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                std::string file_name(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
                std::string token(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1)));
                float distance = static_cast<float>(sqlite3_column_double(stmt, 2));

                data[file_name][token] = distance;
            }
        } else {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl;
        }

        sqlite3_finalize(stmt);
    }

    // Optimized database insert function (batch insert)
    void insert_item_matrix(const std::vector<std::tuple<std::string, std::string, float>>& data) {
        sqlite3* db;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            return;
        }

        std::string create_table_sql = R"(
            CREATE TABLE IF NOT EXISTS item_matrix (
                source TEXT,
                target TEXT,
                distance REAL,
                PRIMARY KEY (source, target)
            );
        )";

        char* error_msg = nullptr;
        if (sqlite3_exec(db, create_table_sql.c_str(), nullptr, nullptr, &error_msg) != SQLITE_OK) {
            std::cerr << "Error creating table: " << error_msg << std::endl;
            sqlite3_free(error_msg);
            sqlite3_close(db);
            return;
        }

        sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, nullptr);

        std::string insert_sql = "INSERT OR REPLACE INTO item_matrix (source, target, distance) VALUES (?, ?, ?);";
        sqlite3_stmt* stmt;
        if (sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "Error preparing insert statement: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return;
        }

        for (const auto& [source, target, distance] : data) {
            sqlite3_bind_text(stmt, 1, source.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, target.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_double(stmt, 3, distance);

            sqlite3_step(stmt);
            sqlite3_reset(stmt);
        }

        sqlite3_finalize(stmt);
        sqlite3_exec(db, "COMMIT;", nullptr, nullptr, nullptr);
        sqlite3_close(db);
    }

    void compute_chunk(size_t start, size_t end, const std::vector<std::string>& titles,
        const std::unordered_map<std::string, std::unordered_map<std::string, float>>& data,
        int thread_id, const std::filesystem::path& output_dir) {

        std::string filename = (output_dir / ("item_matrix_part_" + std::to_string(thread_id) + ".csv")).string();
        std::ofstream csv_file(filename);
        if (!csv_file.is_open()) {
            std::cerr << "Thread " << thread_id << " failed to open file: " << filename << std::endl;
            return;
        }

        csv_file << "Source,Target,Distance\n";

        for (size_t i = start; i < end; ++i) {
            for (size_t j = 0; j < titles.size(); ++j) {
                if (i == j) continue;

                float total_distance = 0.0f;

                const auto& it1 = data.find(titles[i]);
                const auto& it2 = data.find(titles[j]);
                if (it1 == data.end() || it2 == data.end()) continue;

                const auto& source_data = it1->second;
                const auto& target_data = it2->second;

                for (const auto& [token, dist] : source_data) {
                    float other_dist = target_data.count(token) ? target_data.at(token) : 0.0f;
                    total_distance += dist + other_dist;
                }

            csv_file << titles[i] << "," << titles[j] << "," << total_distance << "\n";
            }
        }

        csv_file.close();
    }

    void bulk_insert_from_csv(const std::filesystem::path& csv_file) {
        std::ifstream file(csv_file);
        if (!file.is_open()) {
            std::cerr << "Could not open CSV file for DB insert: " << csv_file << std::endl;
            return;
        }

        std::string line;
        std::getline(file, line); // skip header

        std::vector<std::tuple<std::string, std::string, float>> batch;
        while (std::getline(file, line)) {
            std::stringstream ss(line);
            std::string source, target, dist_str;
            std::getline(ss, source, ',');
            std::getline(ss, target, ',');
            std::getline(ss, dist_str, ',');

            batch.emplace_back(source, target, std::stof(dist_str));

            if (batch.size() >= 1000) {
                insert_item_matrix(batch);
                batch.clear();
            }
        }

        if (!batch.empty()) {
            insert_item_matrix(batch);
        }

        file.close();
    }
    
    void encrypted_file_name_list(sqlite3* db, std::vector<std::string>& titles) {
        /* This function modifies the `titles` vector:
         * - Replaces each title with its corresponding ID from the database, prefixed with "title_".
         * - If a title is not found, it is removed from the vector.
         */
    
        const std::string query = "SELECT id FROM file_info WHERE file_name = ?";
        sqlite3_stmt* stmt = nullptr;
        std::vector<std::string> updated_titles; // Temporary vector to store valid encrypted titles
    
        // Prepare the statement once
        if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "SQL Error: " << sqlite3_errmsg(db) << std::endl;
            return;
        }
    
        for (const std::string& title : titles) {
            sqlite3_reset(stmt);  // Reset the prepared statement for reuse
            sqlite3_clear_bindings(stmt);
    
            // Bind the title to the query
            if (sqlite3_bind_text(stmt, 1, title.c_str(), -1, SQLITE_TRANSIENT) != SQLITE_OK) {
                std::cerr << "Binding Error: " << sqlite3_errmsg(db) << std::endl;
                continue;
            }
    
            // Execute query
            if (sqlite3_step(stmt) == SQLITE_ROW) {
                std::string id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
                updated_titles.push_back("title_" + id);
            }
        }
    
        sqlite3_finalize(stmt); // Finalize the statement
    
        // Replace original titles with the updated ones
        titles = std::move(updated_titles);
    }

    // Function to read numeric data from CSV
    std::vector<std::vector<float>> get_numeric_data_from_csv(const std::string& filename) {
        std::vector<std::vector<float>> item_matrix;
        std::ifstream csv_file(filename);
        if (!csv_file.is_open()) {
            std::cerr << "Error: Could not open file " << filename << " for reading.\n";
            return item_matrix;
        }

        std::string line;
        std::getline(csv_file, line); // Skip the header row

        while (std::getline(csv_file, line)) {
            std::vector<float> row;
            std::istringstream token_stream(line);
            std::string token;

            std::getline(token_stream, token, ','); // Skip first column

            while (std::getline(token_stream, token, ',')) {
                try {
                    row.push_back(std::stof(token));
                } catch (...) {
                    row.push_back(0.0f); // Default to 0 if conversion fails
                }
            }
            item_matrix.push_back(row);
        }

        csv_file.close();
        return item_matrix;
    }

    // Function to read headers from CSV
    std::vector<std::string> get_headers_from_csv(const std::string& filename) {
        std::vector<std::string> headers;
        std::ifstream csv_file(filename);
        if (!csv_file.is_open()) {
            std::cerr << "Error: Could not open file " << filename << " for reading.\n";
            return headers;
        }

        std::string line;
        std::getline(csv_file, line);
        std::istringstream token_stream(line);
        std::string token;

        std::getline(token_stream, token, ','); // Skip first column

        while (std::getline(token_stream, token, ',')) {
            headers.push_back(token);
        }

        csv_file.close();
        return headers;
    }

    std::map<std::string, std::string> get_look_up_table_title(sqlite3* db){
        std::map<std::string, std::string> result;
        const char* query = "SELECT id, file_name FROM file_info";
        sqlite3_stmt* stmt;
        std::string encrypted_key, decrypted_key;

        if (sqlite3_prepare_v2(db, query, -1, &stmt, nullptr) == SQLITE_OK) {
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                encrypted_key = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
                decrypted_key = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
                result[encrypted_key] = decrypted_key;
            }
        } else {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl;
        }

        sqlite3_finalize(stmt);
        return result;
    }

    // Function to create a route and write it to a file
    void create_route(const std::string& start, const uint16_t num_steps,
                      const std::vector<std::string> unique_titles,
                      const std::map<std::string, std::string> look_up_table,
                      std::ofstream& output_file) {
        // Open the SQLite connection
        sqlite3* db;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            return;
        }
    
        // Find the index of the start node
        auto it = std::find(unique_titles.begin(), unique_titles.end(), start);
        if (it == unique_titles.end()) {
            std::cerr << "Error: Invalid start node '" << start << "'.\n";
            sqlite3_close(db);
            return;
        }
    
        int curr_index = it - unique_titles.begin();
        std::vector<bool> visited(unique_titles.size(), false);
    
        // Prepare SQL statement for fetching relational distances
        sqlite3_stmt* stmt;
        const char* query = "SELECT target, distance FROM item_matrix WHERE source = ?";
    
        if (sqlite3_prepare_v2(db, query, -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return;
        }
    
        // Initialize a map to store relational distances
        std::map<std::string, float> target_and_relation_distance;
        for (const std::string& title : unique_titles) {
            target_and_relation_distance[title] = 0.0f;
        }
    
        output_file << look_up_table.at(start.substr(6)) << ",";
        visited[curr_index] = true;
    
        for (int step = 0; step < num_steps; step++) {
    
            // Reset the distance map for the current node
            for (auto& pair : target_and_relation_distance) {
                pair.second = 0.0f;
            }
    
            // Bind the current title and fetch relational distances
            sqlite3_reset(stmt);
            sqlite3_clear_bindings(stmt);
            sqlite3_bind_text(stmt, 1, unique_titles[curr_index].c_str(), -1, SQLITE_TRANSIENT);
    
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                std::string target = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
                float distance = static_cast<float>(sqlite3_column_double(stmt, 1));
                target_and_relation_distance[target] = distance;
            }
    
            // Find the next node with the highest relational distance that hasn't been visited
            float max_value = 0.0f;
            int next_index = -1;
    
            for (size_t i = 0; i < unique_titles.size(); i++) {
                if (!visited[i] && target_and_relation_distance[unique_titles[i]] > max_value) {
                    max_value = target_and_relation_distance[unique_titles[i]];
                    next_index = i;
                }
            }
    
            // If no valid next node is found, terminate the route early
            if (next_index == -1) {
                std::cout << "No more valid next nodes. Ending search.\n";
                break;
            }
    
            // Move to the next node
            curr_index = next_index;
            visited[curr_index] = true;
    
            // Write the selected node to the output file
            output_file << look_up_table.at(unique_titles[curr_index].substr(6)) << "," << max_value << ",";
        }
    
        output_file << "END\n";
    
        // Finalize the statement and close the database
        sqlite3_finalize(stmt);
        sqlite3_close(db);
    }    
}
