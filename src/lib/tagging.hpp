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

    sqlite3_stmt* prepareStatement(sqlite3* db, const std::string& query) {
        sqlite3_stmt* stmt = nullptr;
        int rc = sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr);
        if (rc != SQLITE_OK) {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl
                    << "SQL: " << query << std::endl;
            return nullptr;
        }
        return stmt;
}

    std::map<std::string, std::string> collect_unique_id(sqlite3* db) {
        std::map<std::string, std::string> unique_ids;
        std::string sql = "SELECT id, file_name FROM file_info WHERE chunk_count > 0";
        sqlite3_stmt* stmt = prepareStatement(db, sql);
        if (!stmt) return unique_ids;

        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* id_txt = sqlite3_column_text(stmt, 0);
            const unsigned char* name_txt = sqlite3_column_text(stmt, 1);
            if (id_txt && name_txt) {
                std::string key = reinterpret_cast<const char*>(id_txt);
                std::string value = reinterpret_cast<const char*>(name_txt);
                unique_ids["title_" + key] = value;
            }
        }
        sqlite3_finalize(stmt);
        return unique_ids;
    }

    std::vector<std::tuple<std::string, int, double>> load_token_map(sqlite3* db, const std::string& id) {
        std::vector<std::tuple<std::string, int, double>> filtered_tokens;
        std::string sql = "SELECT Token, frequency, relational_distance FROM relation_distance WHERE file_name = ?";
        sqlite3_stmt* stmt = prepareStatement(db, sql);
        if (!stmt) return filtered_tokens;

        if (sqlite3_bind_text(stmt, 1, id.c_str(), -1, SQLITE_TRANSIENT) != SQLITE_OK) {
            sqlite3_finalize(stmt);
            return filtered_tokens;
        }

        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* token_txt = sqlite3_column_text(stmt, 0);
            if (!token_txt) continue;
            std::string token = reinterpret_cast<const char*>(token_txt);
            int freq = sqlite3_column_int(stmt, 1);
            double base_distance = sqlite3_column_double(stmt, 2);
            filtered_tokens.emplace_back(token, freq, base_distance);
        }
        sqlite3_finalize(stmt);
        return filtered_tokens;
    }

    std::map<std::string, std::map<std::string, double>> load_related_tokens(
        sqlite3* db, 
        const std::vector<std::tuple<std::string, int, double>>& filtered_tokens,
        const std::map<std::string, std::string>& unique_ids
    ) {
        std::map<std::string, std::map<std::string, double>> relation_distance_map;
        if (filtered_tokens.empty()) return relation_distance_map;

        std::string token_in_clause;
        for (const auto& [token, _, __] : filtered_tokens)
            token_in_clause += "'" + token + "',";
        if (!token_in_clause.empty()) token_in_clause.pop_back(); // remove last comma

        std::string file_name_clause;
        for (const auto& [key, _] : unique_ids)
            file_name_clause += "'" + key + "',";
        if (!file_name_clause.empty()) file_name_clause.pop_back(); // remove last comma

        std::string sql = "SELECT file_name, Token, relational_distance FROM relation_distance WHERE Token IN (" + token_in_clause + ") AND file_name IN (" + file_name_clause + ");";
        sqlite3_stmt* stmt = prepareStatement(db, sql);
        if (!stmt) return relation_distance_map;

        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* file_txt = sqlite3_column_text(stmt, 0);
            const unsigned char* token_txt = sqlite3_column_text(stmt, 1);
            if (!file_txt || !token_txt) continue;
            std::string rel_file = reinterpret_cast<const char*>(file_txt);
            std::string token = reinterpret_cast<const char*>(token_txt);
            double rel_dist = sqlite3_column_double(stmt, 2);
            relation_distance_map[rel_file][token] = rel_dist;
        }
        sqlite3_finalize(stmt);
        return relation_distance_map;
    }

    void apply_tfidf(sqlite3* db, std::vector<std::tuple<std::string, int, double>>& filtered_tokens) {
        std::string sql = "SELECT tf_idf FROM tf_idf WHERE word = ?";
        sqlite3_stmt* stmt = prepareStatement(db, sql);
        if (!stmt) return;

        for (auto& [token, freq, base_distance] : filtered_tokens) {
            sqlite3_reset(stmt);
            if (sqlite3_bind_text(stmt, 1, token.c_str(), -1, SQLITE_TRANSIENT) != SQLITE_OK) continue;
            if (sqlite3_step(stmt) == SQLITE_ROW) {
                double tfidf = sqlite3_column_double(stmt, 0);
                if (std::isnan(tfidf)) tfidf = 0.0;
                base_distance += tfidf / freq;
            }
        }
        sqlite3_finalize(stmt);
    }

    std::vector<std::tuple<std::string, std::string, double>> compute_recommendations(
        std::vector<std::tuple<std::string, int, double>>& filtered_tokens,
        std::map<std::string, std::map<std::string, double>>& relation_distance_map,
        std::map<std::string, std::string>& unique_ids,
        const std::string& source_id) {

        std::vector<std::tuple<std::string, std::string, double>> RESULT;
        std::string rel_file_key = source_id;
        if (relation_distance_map.find(rel_file_key) == relation_distance_map.end()) return RESULT;

        // const auto& token_map = relation_distance_map[rel_file_key];
        for (const auto& [file_name, token_data] : relation_distance_map) {
            if (file_name == rel_file_key) continue;
            double score = 0.0;
            for (const auto& [token, _, base_distance] : filtered_tokens) {
                auto it = token_data.find(token);
                if (it != token_data.end()) {
                    score += it->second * base_distance;
                }
            }
            if (score > 0.0)
                RESULT.emplace_back(file_name, unique_ids[file_name], score);
        }

        std::sort(RESULT.begin(), RESULT.end(), [](const auto& a, const auto& b) {
            return std::get<2>(a) > std::get<2>(b);
        });
        return RESULT;
    }

    void insert_item_matrix(
        std::vector<std::tuple<std::string, std::string, double>>& RESULT,
        sqlite3* db,
        const std::pair<std::string, std::string>& origin) {

        std::string insert_sql = "INSERT INTO item_matrix (target_id, target_name, source_id, source_name, distance, rank) VALUES (?, ?, ?, ?, ?, ?);";
        sqlite3_stmt* stmt = prepareStatement(db, insert_sql);
        if (!stmt) return;

        const auto& [source_id, source_name] = origin;
        for (size_t rank = 1; rank <= RESULT.size(); ++rank) {
            const auto& [target_id, target_name, distance] = RESULT[rank - 1];
            sqlite3_bind_text(stmt, 1, target_id.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, target_name.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 3, source_id.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 4, source_name.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_double(stmt, 5, distance);
            sqlite3_bind_int(stmt, 6, rank);
            sqlite3_step(stmt);
            sqlite3_reset(stmt);
        }
        sqlite3_finalize(stmt);
    }

    void reset_item_matrix(sqlite3* db) {
        execute_sql(db, "DROP TABLE IF EXISTS item_matrix;");
        execute_sql(db, "CREATE TABLE item_matrix (target_id TEXT, target_name TEXT, source_id TEXT, source_name TEXT, distance REAL, rank INTEGER);");
    }

    void add_item_matrix(sqlite3* db, std::map<std::string, std::string>& unique_ids){
        // Remove entries from the map, found in item_matrix
        std::string sql = "SELECT source_id FROM item_matrix;";
        sqlite3_stmt* stmt = prepareStatement(db, sql);
        if (!stmt) return;

        while (sqlite3_step(stmt) == SQLITE_ROW) {
            std::string source_id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
            unique_ids.erase(source_id);
        }
        sqlite3_finalize(stmt);
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
