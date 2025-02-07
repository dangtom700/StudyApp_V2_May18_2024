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
#include <thread>
#include <mutex>

#include "utilities.hpp"

/* The purposes of this header are to:
    1. Randomly assigned tags to a list of files
    2. User can correctly fix tags to the files
    3. Teach the algorithm to assign tags to the files
    4. Export the tags to a CSV file (done)
    5. Import the tags from a CSV file (done)

*/
namespace Tagging{
    const std::string topics[] = {
    "environment", "journalism", "health", "psychology", "data", "meteorology", "literature", 
    "ethics", "computing", "architecture", "game", "mathematics", "mechanics", "HR", "zoology", 
    "textbook", "research", "religion", "networking", "sociology", "development", "interior", 
    "accounting", "sports", "responsibility", "business", "programming", "robotics", "graphic", 
    "modeling", "philosophy", "technology", "film", "software", "law", "industrial", "electronics", 
    "IoT", "social", "guide", "cybersecurity", "physics", "history", "botany", "entrepreneurship", 
    "medicine", "engineering", "science", "security", "statistics", "economics", "database", 
    "education", "simulation", "archaeology", "culture", "corporate", "electrics", "media", 
    "astronomy", "AI", "oceanography", "computer", "geography", "analytics", "others", "introductory", 
    "chemistry", "arts", "biology", "communication", "urban", "nanotechnology", "finance", "fashion", 
    "anthropology", "big", "mobile", "leadership", "linguistics", "music", "planning", "design", "food", 
    "politics", "landscape", "marketing", "web", "travel", "government", "genetics", "theater", 
    "management", "ecology", "hardware", "product", "cloud"
    };

    const int topicsSize = sizeof(topics)/sizeof(topics[0]);

    //--------------------The functions below are implemented in the main code base. Not the above ones----------------------

    // Fetch unique titles
    std::vector<std::string> fetch_unique_titles(sqlite3* db) {
        std::vector<std::string> unique_titles;
        sqlite3_stmt* stmt;
        const char* query = "SELECT DISTINCT file_name FROM relation_distance";

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

    // Compute distances in parallel and write results directly
    void compute_and_store_distances(
        const std::vector<std::string>& unique_titles,
        const std::unordered_map<std::string, std::unordered_map<std::string, float>>& data,
        const std::filesystem::path& output_filename) {

        std::ofstream csv_file(output_filename);
        if (!csv_file.is_open()) {
            std::cerr << "Error: Could not open file " << output_filename << " for writing." << std::endl;
            return;
        }

        csv_file << "Source,Target,Distance\n"; // CSV header

        std::vector<std::tuple<std::string, std::string, float>> db_data; // Buffer for batched DB insert
        std::mutex file_mutex, db_mutex; // Mutex for CSV and DB writes

        int num_threads = std::thread::hardware_concurrency();
        std::vector<std::thread> threads;
        
        auto compute_chunk = [&](int start, int end) {
            std::vector<std::tuple<std::string, std::string, float>> local_db_data;

            for (int i = start; i < end; ++i) {
                for (uint16_t j = 0; j < unique_titles.size(); ++j) {
                    if (i == j) continue; // Skip self-comparisons

                    float total_distance = 0.0f;
                    const auto& token_distance_pairs = data.at(unique_titles[i]);
                    const auto& target_token_distance_pairs = data.at(unique_titles[j]);

                    for (const auto& [token, distance] : token_distance_pairs) {
                        auto it = target_token_distance_pairs.find(token);
                        float target_distance = (it != target_token_distance_pairs.end()) ? it->second : 0.0f;
                        total_distance += distance + target_distance;
                    }

                    {
                        std::lock_guard<std::mutex> lock(file_mutex);
                        csv_file << unique_titles[i] << "," << unique_titles[j] << "," << total_distance << "\n";
                    }

                    local_db_data.emplace_back(unique_titles[i], unique_titles[j], total_distance);

                    if (local_db_data.size() >= 1000) { // Batch insert every 1000 records
                        std::lock_guard<std::mutex> lock(db_mutex);
                        insert_item_matrix(local_db_data);
                        local_db_data.clear();
                    }
                }
            }

            if (!local_db_data.empty()) {
                std::lock_guard<std::mutex> lock(db_mutex);
                insert_item_matrix(local_db_data);
            }
        };

        int chunk_size = (unique_titles.size() + num_threads - 1) / num_threads;
        for (int t = 0; t < num_threads; ++t) {
            int start = t * chunk_size;
            int end = std::min(start + chunk_size, static_cast<int>(unique_titles.size()));
            threads.emplace_back(compute_chunk, start, end);
        }

        for (auto& thread : threads) {
            thread.join();
        }

        csv_file.close();
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

    // Function to create a route and write to a file
    void create_route(const std::string& start, int num_steps, 
                    const std::vector<std::vector<float>>& item_matrix, 
                    const std::vector<std::string>& titles,
                    std::ofstream& output_file) {
        // Find index of the start node
        auto it = std::find(titles.begin(), titles.end(), start);
        if (it == titles.end()) {
            std::cerr << "Error: Invalid start node '" << start << "'.\n";
            return;
        }

        int curr_index = it - titles.begin();
        std::vector<bool> visited(titles.size(), false);
        float total_distance = 0.0f;

        output_file << start.substr(6) << "," << total_distance << ",";
        visited[curr_index] = true;

        for (int step = 0; step < num_steps; step++) {
            float max_value = 0.0f;
            int next_index = -1;

            for (size_t j = 0; j < item_matrix[curr_index].size(); j++) {
                if (!visited[j] && item_matrix[curr_index][j] > max_value) {
                    max_value = item_matrix[curr_index][j];
                    next_index = static_cast<int>(j);
                }
            }

            if (next_index == -1) {
                break; // No valid next node found
            }

            total_distance += max_value;

            output_file << titles[next_index].substr(6) << "," << total_distance << ",";
            visited[next_index] = true;
            curr_index = next_index;
        }

        output_file << "END\n";
    }

}
