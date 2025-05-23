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

    /**
     * Collects unique IDs and their associated file names from the database.
     *
     * @param db The SQLite database connection.
     * @return A map containing unique IDs as keys (prefixed with "title_") 
     *         and their corresponding file names as values.
     *
     * This function queries the file_info table for entries where the 
     * chunk_count is greater than 0, retrieves the ID and file name for 
     * each entry, and stores them in a map with the ID prefixed by "title_".
     * If the statement cannot be prepared, an empty map is returned.
     */
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

    /**
     * Load tokens and their attributes from the database for a given file.
     *
     * @param db The SQLite database connection.
     * @param id The identifier of the file whose tokens are to be retrieved.
     * @return A vector of tuples, each containing a token, its frequency, and its relational distance.
     *
     * This function queries the relation_distance table to retrieve tokens, their frequencies,
     * and relational distances for the specified file. The results are stored in a vector
     * of tuples and returned. If the statement preparation or execution fails, an empty
     * vector is returned.
     */
    std::vector<std::tuple<std::string, int, double>> load_token_map(sqlite3* db, const std::string& id) {
        std::vector<std::tuple<std::string, int, double>> filtered_tokens;
        std::string sql = "SELECT Token, frequency, relational_distance FROM relation_distance WHERE file_name = ? AND frequency > 3";
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

    /**
     * Load the relational distances of tokens related to the given tokens for
     * all files in the database.
     *
     * @param db The SQLite database connection.
     * @param filtered_tokens A vector of tuples containing the tokens and their
     *                        attributes to be used for filtering.
     * @param unique_ids A map of unique IDs to file names.
     * @return A map of file names to maps of tokens to their relational distances.
     *
     * This function queries the relation_distance table to retrieve the relational
     * distances of tokens related to the tokens in the given vector. The results
     * are stored in a map of file names to maps of tokens to their relational
     * distances and returned. If the statement preparation or execution fails, an
     * empty map is returned.
     */
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

    /**
     * @brief Applies TF-IDF to a given vector of filtered tokens.
     *
     * Applies TF-IDF to a given vector of filtered tokens. The TF-IDF values are
     * retrieved from the tf_idf table in the database and added to the base
     * distance of each token. The results are stored in the vector itself.
     *
     * @param db The SQLite database connection.
     * @param filtered_tokens The vector of filtered tokens to which TF-IDF is to be
     * applied.
     */
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

    /**
     * Computes recommendations for a given source file based on the filtered tokens
     * and relational distance map.
     *
     * The recommendations are computed by summing the product of the relational
     * distance and the base distance of each token across all files in the
     * relational distance map. The results are sorted in descending order of
     * score.
     *
     * @param filtered_tokens The filtered tokens to which relational distance is to
     * be applied.
     * @param relation_distance_map The relational distance map.
     * @param unique_ids The map of unique ids.
     * @param source_id The source file id.
     * @return A vector of tuples, each containing the file name, unique id, and
     * score of the recommended file.
     */
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

        return RESULT;
    }

    /**
     * Inserts the given vector of recommendations into the item_matrix table in the
     * database. The recommendations are sorted by rank, which is computed from the
     * index of each element in the vector.
     *
     * @param RESULT The vector of recommendations to be inserted.
     * @param db The SQLite database connection.
     * @param origin A pair of strings containing the source file ID and name.
     */
    void insert_item_matrix(
        std::vector<std::tuple<std::string, std::string, double>>& RESULT,
        sqlite3* db,
        const std::pair<std::string, std::string>& origin) {

        std::string insert_sql = "INSERT INTO item_matrix (target_id, target_name, source_id, source_name, distance) VALUES (?, ?, ?, ?, ?);";
        sqlite3_stmt* stmt = prepareStatement(db, insert_sql);
        if (!stmt) return;

        const auto& [source_id, source_name] = origin;
        for (const auto& [target_id, target_name, distance] : RESULT) {
            sqlite3_bind_text(stmt, 1, target_id.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, target_name.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 3, source_id.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 4, source_name.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_double(stmt, 5, distance);
            sqlite3_step(stmt);
            sqlite3_reset(stmt);
        }
        sqlite3_finalize(stmt);
    }

    /**
     * Resets the item_matrix table in the database. If the table already exists, it is
     * dropped and recreated. The table has the following columns:
     *
     * - target_id: The ID of the target item.
     * - target_name: The name of the target item.
     * - source_id: The ID of the source item.
     * - source_name: The name of the source item.
     * - distance: The distance between the source and target items.
     * - rank: The rank of the target item relative to the source item.
     *
     * @param db The SQLite database connection.
     */
    void reset_item_matrix(sqlite3* db) {
        execute_sql(db, "DROP TABLE IF EXISTS item_matrix;");
        execute_sql(db, "CREATE TABLE item_matrix (target_id TEXT, target_name TEXT, source_id TEXT, source_name TEXT, distance REAL);");
    }

    /**
     * Remove entries from the map, found in item_matrix
     * This function retrieves all the source_id from the item_matrix table and removes
     * the corresponding entries from the given map.
     *
     * @param db The SQLite database connection.
     * @param unique_ids A map containing the unique IDs as keys and their names as values.
     * @return void
     */
    void add_item_matrix(sqlite3* db, std::map<std::string, std::string>& unique_ids){
        // Remove entries from the map, found in item_matrix
        std::string sql = "SELECT DISTINCT source_id FROM item_matrix;";
        sqlite3_stmt* stmt = prepareStatement(db, sql);
        if (!stmt) return;

        while (sqlite3_step(stmt) == SQLITE_ROW) {
            std::string source_id = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
            unique_ids.erase(source_id);
        }
        sqlite3_finalize(stmt);
    }

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
    
        // Prepare SQL statement for fetching relational distances
        sqlite3_stmt* stmt;
        const char* query = R"(
            SELECT target_name
            FROM item_matrix
            WHERE source_id = ? AND distance = (SELECT MAX(distance) FROM item_matrix WHERE source_id = ?)
        )";
    
        if (sqlite3_prepare_v2(db, query, -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return;
        }
    
        // Initialize a map to store relational distances
        std::map<std::string, float> target_and_relation_distance;
        std::vector<std::string> visited;
        visited.reserve(unique_titles.size());
        std::string curr_file = start;

        // Find the node with the highest relational distance
        output_file << "Start: " << (look_up_table.count(curr_file) ? look_up_table.at(curr_file) : "[UNKNOWN]");

        while (true) {
            std::vector<std::string> max_distance_titles;
            max_distance_titles.clear();

            sqlite3_reset(stmt);
            sqlite3_clear_bindings(stmt);
            sqlite3_bind_text(stmt, 1, curr_file.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, curr_file.c_str(), -1, SQLITE_TRANSIENT);

            while (sqlite3_step(stmt) == SQLITE_ROW) {
                std::string target_name = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
                max_distance_titles.push_back(target_name);
            }

            if (max_distance_titles.empty()) {
                output_file << " -> None\nThere is no further route from this node.\n";
                break;
            }

            if (max_distance_titles.size() > 1) {
                output_file << " -> (Multiple Choices)\n";
                for (const std::string& title : max_distance_titles) {
                    output_file << "-> " << (look_up_table.count(title) ? look_up_table.at(title) : "[UNKNOWN]") << "\n";
                }
                output_file << "Path is diverged.\n";
                break;
            }

            std::string next_title = max_distance_titles[0];

            bool is_in_unique = std::find(unique_titles.begin(), unique_titles.end(), next_title) != unique_titles.end();
            bool is_visited = std::find(visited.begin(), visited.end(), next_title) != visited.end();

            if (is_in_unique && !is_visited) {
                visited.push_back(next_title);
                curr_file = next_title;
                output_file << " -> " << (look_up_table.count(curr_file) ? look_up_table.at(curr_file) : "[UNKNOWN]");
            } else {
                output_file << " -> " << (look_up_table.count(next_title) ? look_up_table.at(next_title) : "[UNKNOWN]");
                output_file << "\nLoop detected or unreachable node.\n";
                break;
            }
        }

        output_file << "\nEND.\n";
        sqlite3_finalize(stmt);
        sqlite3_close(db);
    }    
}
