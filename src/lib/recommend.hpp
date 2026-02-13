#include <filesystem>
#include <vector>
#include <map>
#include <unordered_map>
#include <fstream>
#include <sqlite3.h>
#include <thread>
#include "lib/utilities.hpp"
#include "lib/env.hpp" // Include ENV_HPP definition
#include "lib/transform.hpp"

namespace RECOMMEND
{
    sqlite3_stmt *prepareStatement(sqlite3 *db, const std::string &query)
    {
        sqlite3_stmt *stmt = nullptr;
        int rc = sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr);
        if (rc != SQLITE_OK)
        {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl
                      << "SQL: " << query << std::endl;
            return nullptr;
        }
        return stmt;
    }

    std::map<std::string, std::string> collect_processing_id(sqlite3 *db, bool reset_table)
    {
        std::map<std::string, std::string> unique_ids;
        std::string sql = "SELECT id, file_name FROM file_info WHERE chunk_count > 0";
        sqlite3_stmt *stmt = prepareStatement(db, sql);
        if (!stmt)
            return unique_ids;

        while (sqlite3_step(stmt) == SQLITE_ROW)
        {
            const unsigned char *id_txt = sqlite3_column_text(stmt, 0);
            const unsigned char *name_txt = sqlite3_column_text(stmt, 1);
            if (id_txt && name_txt)
            {
                std::string key = reinterpret_cast<const char *>(id_txt);
                std::string value = reinterpret_cast<const char *>(name_txt);
                unique_ids["title_" + key] = value;
            }
        }
        sqlite3_finalize(stmt);

        // Remove key that already exists in item_matrix
        if (reset_table)
            return unique_ids;
        else
        {
            sql = "SELECT DISTINCT source_id FROM item_matrix";
            stmt = prepareStatement(db, sql);
            if (!stmt)
                return unique_ids;

            while (sqlite3_step(stmt) == SQLITE_ROW)
            {
                const unsigned char *id_txt = sqlite3_column_text(stmt, 0);
                if (id_txt)
                {
                    std::string key = reinterpret_cast<const char *>(id_txt);
                    unique_ids.erase(key);
                }
            }
            sqlite3_finalize(stmt);
        }
        return unique_ids;
    }

    std::map<std::string, std::string> collect_unique_id(sqlite3 *db)
    {
        std::map<std::string, std::string> unique_ids;
        std::string sql = "SELECT id, file_name FROM file_info WHERE chunk_count > 0";
        sqlite3_stmt *stmt = prepareStatement(db, sql);
        if (!stmt)
            return unique_ids;

        while (sqlite3_step(stmt) == SQLITE_ROW)
        {
            const unsigned char *id_txt = sqlite3_column_text(stmt, 0);
            const unsigned char *name_txt = sqlite3_column_text(stmt, 1);
            if (id_txt && name_txt)
            {
                std::string key = reinterpret_cast<const char *>(id_txt);
                std::string value = reinterpret_cast<const char *>(name_txt);
                unique_ids["title_" + key] = value;
            }
        }
        sqlite3_finalize(stmt);
        return unique_ids;
    }

    std::vector<std::tuple<std::string, int, double>> load_token_map(sqlite3 *db, const std::string &id)
    {
        std::vector<std::tuple<std::string, int, double>> filtered_tokens;
        std::string sql = "SELECT Token, frequency, relational_distance FROM relation_distance WHERE file_name = ?";
        sqlite3_stmt *stmt = prepareStatement(db, sql);
        if (!stmt)
            return filtered_tokens;

        if (sqlite3_bind_text(stmt, 1, id.c_str(), -1, SQLITE_TRANSIENT) != SQLITE_OK)
        {
            sqlite3_finalize(stmt);
            return filtered_tokens;
        }

        while (sqlite3_step(stmt) == SQLITE_ROW)
        {
            const unsigned char *token_txt = sqlite3_column_text(stmt, 0);
            if (!token_txt)
                continue;
            std::string token = reinterpret_cast<const char *>(token_txt);
            int freq = sqlite3_column_int(stmt, 1);
            double base_distance = sqlite3_column_double(stmt, 2);
            filtered_tokens.emplace_back(token, freq, base_distance);
        }
        sqlite3_finalize(stmt);
        return filtered_tokens;
    }

    std::map<std::string, std::map<std::string, double>> load_related_tokens(
        sqlite3 *db,
        const std::vector<std::tuple<std::string, int, double>> &filtered_tokens)
    {
        std::map<std::string, std::map<std::string, double>> relation_distance_map;
        if (filtered_tokens.empty())
            return relation_distance_map;

        char *err = nullptr;

        // 1. Create temporary table
        const char *create_sql = "CREATE TEMP TABLE IF NOT EXISTS temp_tokens ("
                                 " token TEXT PRIMARY KEY"
                                 ");"
                                 "DELETE FROM temp_tokens;"; // clear previous contents
        if (sqlite3_exec(db, create_sql, nullptr, nullptr, &err) != SQLITE_OK)
        {
            sqlite3_free(err);
            return relation_distance_map;
        }

        // 2. Insert tokens using prepared statement
        const char *insert_sql = "INSERT OR IGNORE INTO temp_tokens (token) VALUES (?);";
        sqlite3_stmt *insert_stmt = nullptr;
        if (sqlite3_prepare_v2(db, insert_sql, -1, &insert_stmt, nullptr) != SQLITE_OK)
        {
            return relation_distance_map;
        }

        for (const auto &[token, _, __] : filtered_tokens)
        {
            sqlite3_reset(insert_stmt);
            sqlite3_bind_text(insert_stmt, 1, token.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_step(insert_stmt);
        }
        sqlite3_finalize(insert_stmt);

        // 3. Query related tokens via JOIN
        const char *query_sql = "SELECT r.file_name, r.Token, r.relational_distance "
                                "FROM relation_distance r "
                                "JOIN temp_tokens t ON r.Token = t.token;";
        sqlite3_stmt *stmt = nullptr;
        if (sqlite3_prepare_v2(db, query_sql, -1, &stmt, nullptr) != SQLITE_OK)
        {
            return relation_distance_map;
        }

        while (sqlite3_step(stmt) == SQLITE_ROW)
        {
            const unsigned char *file_txt = sqlite3_column_text(stmt, 0);
            const unsigned char *token_txt = sqlite3_column_text(stmt, 1);
            if (!file_txt || !token_txt)
                continue;
            std::string file = reinterpret_cast<const char *>(file_txt);
            std::string token = reinterpret_cast<const char *>(token_txt);
            double dist = sqlite3_column_double(stmt, 2);
            relation_distance_map[file][token] = dist;
        }
        sqlite3_finalize(stmt);
        return relation_distance_map;
    }

    void apply_tfidf(
        sqlite3 *db,
        std::vector<std::tuple<std::string, int, double>> &filtered_tokens)
    {
        if (filtered_tokens.empty())
            return;

        // Load tf-idf table once
        std::unordered_map<std::string, double> tfidf_map;
        tfidf_map.reserve(filtered_tokens.size());
        const char *sql = "SELECT word, tf_idf FROM tf_idf;";
        sqlite3_stmt *stmt = prepareStatement(db, sql);
        if (!stmt)
            return;

        while (sqlite3_step(stmt) == SQLITE_ROW)
        {
            const unsigned char *word_txt = sqlite3_column_text(stmt, 0);
            if (!word_txt)
                continue;
            std::string word = reinterpret_cast<const char *>(word_txt);
            double tfidf = sqlite3_column_double(stmt, 1);
            if (std::isnan(tfidf))
                tfidf = 0.0;
            tfidf_map.emplace(std::move(word), tfidf);
        }
        sqlite3_finalize(stmt);

        // Apply tf-idf
        for (auto &[token, freq, base_distance] : filtered_tokens)
        {
            auto it = tfidf_map.find(token);
            if (it != tfidf_map.end() && freq > 0)
            {
                base_distance += it->second / freq;
            }
        }
    }

    void insert_item_matrix(
        std::vector<std::tuple<std::string, std::string, std::string, std::string, double>> &RESULT,
        sqlite3 *db)
    {
        std::string insert_sql = "INSERT OR IGNORE INTO item_matrix (target_id, target_name, source_id, source_name, distance) VALUES (?, ?, ?, ?, ?);";
        sqlite3_stmt *stmt = prepareStatement(db, insert_sql);
        if (!stmt)
            return;

        for (const auto &[target_id, target_name, source_id, source_name, distance] : RESULT)
        {
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

    std::vector<std::tuple<std::string, std::string, double>> compute_recommendations(
        const std::vector<std::tuple<std::string, int, double>> &filtered_tokens,
        const std::map<std::string, std::map<std::string, double>> &relation_distance_map,
        const std::string &source_id,
        const std::map<std::string, std::string> &unique_ids)
    {
        std::vector<std::tuple<std::string, std::string, double>> result;

        // Precompute token weights
        std::unordered_map<std::string, double> token_weights;
        token_weights.reserve(filtered_tokens.size());
        for (const auto &[token, _, base_distance] : filtered_tokens)
        {
            token_weights.emplace(token, base_distance);
        }

        // Iterate through related files
        for (const auto &[file_name, token_data] : relation_distance_map)
        {
            if (file_name == source_id)
                continue;

            double score = 0.0;
            // Iterate over smaller map (token_data)
            for (const auto &[token, rel_dist] : token_data)
            {
                auto it = token_weights.find(token);
                if (it != token_weights.end())
                {
                    score += rel_dist * it->second;
                }
            }

            if (score <= 0.0)
                continue;
            auto name_it = unique_ids.find(file_name);
            if (name_it == unique_ids.end())
                continue;
            result.emplace_back(file_name, name_it->second, score);
        }
        return result;
    }
}