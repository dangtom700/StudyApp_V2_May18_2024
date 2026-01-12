#include <filesystem>
#include <vector>
#include <map>
#include <unordered_map>
#include <fstream>
#include <sqlite3.h>
#include <thread>

#include "lib/utilities.hpp"
#include "lib/env.hpp"  // Include ENV_HPP definition
#include "lib/transform.hpp"

#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>

using ItemRow = std::tuple<
    std::string, std::string,
    std::string, std::string,
    double
>;

std::queue<std::vector<ItemRow>> write_queue;
std::mutex queue_mutex;
std::condition_variable queue_cv;
std::atomic<bool> producers_done = false;
std::atomic<size_t> global_index = 0;
constexpr uint32_t IDS_PER_WORKER = 10;   // ids per cycle per worker
constexpr uint32_t WRITE_THRESHOLD = 10000;

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

std::map<std::string, std::string> collect_processing_id(sqlite3* db, bool reset_table) {
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

    // Remove key that already exists in item_matrix
    if (reset_table) return unique_ids;
    else{
        sql = "SELECT DISTINCT source_id FROM item_matrix";;
        stmt = prepareStatement(db, sql);
        if (!stmt) return unique_ids;
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            const unsigned char* id_txt = sqlite3_column_text(stmt, 0);
            if (id_txt) {
                std::string key = reinterpret_cast<const char*>(id_txt);
                unique_ids.erase(key);
            }
        }
        sqlite3_finalize(stmt);
    }

    return unique_ids;
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

std::map<std::string, std::map<std::string, double>>
load_related_tokens(sqlite3* db,
    const std::vector<std::tuple<std::string, int, double>>& filtered_tokens)
{
    std::map<std::string, std::map<std::string, double>> relation_distance_map;
    if (filtered_tokens.empty()) return relation_distance_map;

    char* err = nullptr;

    // 1. Create temporary table
    const char* create_sql =
        "CREATE TEMP TABLE IF NOT EXISTS temp_tokens ("
        " token TEXT PRIMARY KEY"
        ");"
        "DELETE FROM temp_tokens;";  // clear previous contents

    if (sqlite3_exec(db, create_sql, nullptr, nullptr, &err) != SQLITE_OK) {
        sqlite3_free(err);
        return relation_distance_map;
    }

    // 2. Insert tokens using prepared statement
    const char* insert_sql =
        "INSERT OR IGNORE INTO temp_tokens (token) VALUES (?);";

    sqlite3_stmt* insert_stmt = nullptr;
    if (sqlite3_prepare_v2(db, insert_sql, -1, &insert_stmt, nullptr) != SQLITE_OK) {
        return relation_distance_map;
    }

    for (const auto& [token, _, __] : filtered_tokens) {
        sqlite3_reset(insert_stmt);
        sqlite3_bind_text(insert_stmt, 1, token.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_step(insert_stmt);
    }
    sqlite3_finalize(insert_stmt);

    // 3. Query related tokens via JOIN
    const char* query_sql =
        "SELECT r.file_name, r.Token, r.relational_distance "
        "FROM relation_distance r "
        "JOIN temp_tokens t ON r.Token = t.token;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, query_sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return relation_distance_map;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const unsigned char* file_txt  = sqlite3_column_text(stmt, 0);
        const unsigned char* token_txt = sqlite3_column_text(stmt, 1);
        if (!file_txt || !token_txt) continue;

        std::string file  = reinterpret_cast<const char*>(file_txt);
        std::string token = reinterpret_cast<const char*>(token_txt);
        double dist = sqlite3_column_double(stmt, 2);

        relation_distance_map[file][token] = dist;
    }

    sqlite3_finalize(stmt);
    return relation_distance_map;
}

void apply_tfidf(
    sqlite3* db,
    std::vector<std::tuple<std::string, int, double>>& filtered_tokens)
{
    if (filtered_tokens.empty()) return;

    // Load tf-idf table once
    std::unordered_map<std::string, double> tfidf_map;
    tfidf_map.reserve(filtered_tokens.size());

    const char* sql = "SELECT word, tf_idf FROM tf_idf;";
    sqlite3_stmt* stmt = prepareStatement(db, sql);
    if (!stmt) return;

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        const unsigned char* word_txt = sqlite3_column_text(stmt, 0);
        if (!word_txt) continue;

        std::string word = reinterpret_cast<const char*>(word_txt);
        double tfidf = sqlite3_column_double(stmt, 1);
        if (std::isnan(tfidf)) tfidf = 0.0;

        tfidf_map.emplace(std::move(word), tfidf);
    }
    sqlite3_finalize(stmt);

    // Apply tf-idf
    for (auto& [token, freq, base_distance] : filtered_tokens) {
        auto it = tfidf_map.find(token);
        if (it != tfidf_map.end() && freq > 0) {
            base_distance += it->second / freq;
        }
    }
}

void insert_item_matrix(
    std::vector<std::tuple<std::string, std::string, std::string, std::string, double>>& RESULT, sqlite3* db
){ 
    std::string insert_sql = "INSERT OR IGNORE INTO item_matrix (target_id, target_name, source_id, source_name, distance) VALUES (?, ?, ?, ?, ?);"; 
    sqlite3_stmt* stmt = prepareStatement(db, insert_sql); 
    if (!stmt) return; 
    for (const auto& [target_id, target_name, source_id, source_name, distance] : RESULT) { 
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

std::vector<std::tuple<std::string, std::string, double>>
compute_recommendations(
    const std::vector<std::tuple<std::string, int, double>>& filtered_tokens,
    const std::map<std::string, std::map<std::string, double>>& relation_distance_map,
    const std::string& source_id,
    const std::map<std::string, std::string>& unique_ids)
{
    std::vector<std::tuple<std::string, std::string, double>> result;

    // Precompute token weights
    std::unordered_map<std::string, double> token_weights;
    token_weights.reserve(filtered_tokens.size());

    for (const auto& [token, _, base_distance] : filtered_tokens) {
        token_weights.emplace(token, base_distance);
    }

    // Iterate through related files
    for (const auto& [file_name, token_data] : relation_distance_map) {
        if (file_name == source_id) continue;

        double score = 0.0;

        // Iterate over smaller map (token_data)
        for (const auto& [token, rel_dist] : token_data) {
            auto it = token_weights.find(token);
            if (it != token_weights.end()) {
                score += rel_dist * it->second;
            }
        }

        if (score <= 0.0) continue;

        auto name_it = unique_ids.find(file_name);
        if (name_it == unique_ids.end()) continue;

        result.emplace_back(file_name, name_it->second, score);
    }

    return result;
}

void reset_item_matrix(sqlite3* db) {
    execute_sql(db, "DROP TABLE IF EXISTS item_matrix;");
    execute_sql(db, "CREATE TABLE item_matrix (target_id TEXT, target_name TEXT, source_id TEXT, source_name TEXT, distance REAL);");
}

void writer_thread_func() {
    sqlite3* db;
    if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
        std::cerr << "Writer failed to open database\n";
        return;
    }

    execute_sql(db, "PRAGMA journal_mode=WAL;");
    execute_sql(db, "PRAGMA synchronous=OFF;");
    execute_sql(db, "PRAGMA temp_store=MEMORY;");

    while (true) {
        std::vector<ItemRow> batch;

        {
            std::unique_lock<std::mutex> lock(queue_mutex);
            queue_cv.wait(lock, [] {
                return !write_queue.empty() || producers_done.load();
            });

            if (write_queue.empty() && producers_done.load())
                break;

            batch = std::move(write_queue.front());
            write_queue.pop();
        }

        insert_item_matrix(batch, db);
        std::cout << "Flush. ";
    }

    sqlite3_close(db);
}

void producer_worker_dynamic(
    const std::vector<std::pair<std::string, std::string>>& processing_ids,
    const std::map<std::string, std::string>& unique_ids,
    uint32_t ids_per_worker,
    uint32_t write_threshold)
{
    sqlite3* db;
    if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
        std::cerr << "Producer failed to open database\n";
        return;
    }

    execute_sql(db, "PRAGMA journal_mode=WAL;");
    execute_sql(db, "PRAGMA synchronous=OFF;");
    execute_sql(db, "PRAGMA temp_store=MEMORY;");

    std::vector<ItemRow> local_batch;
    local_batch.reserve(write_threshold);

    while (true) {
        // 1️ Claim a batch of work
        size_t start = global_index.fetch_add(ids_per_worker);
        if (start >= processing_ids.size()) break;

        size_t end = std::min(start + ids_per_worker, processing_ids.size());

        // 2️ Process claimed IDs
        for (size_t i = start; i < end; ++i) {
            const auto& [id, file_name] = processing_ids[i];

            auto filtered_tokens = load_token_map(db, id);
            if (filtered_tokens.empty()) continue;

            apply_tfidf(db, filtered_tokens);
            auto relation_distance_map = load_related_tokens(db, filtered_tokens);
            auto results = compute_recommendations(
                filtered_tokens,
                relation_distance_map,
                id,
                unique_ids
            );

            for (const auto& [target_id, target_name, distance] : results) {
                local_batch.emplace_back(
                    target_id, target_name,
                    id, file_name,
                    distance
                );
            }
        }

        // 3️ Flush frequently
        if (local_batch.size() >= write_threshold) {
            {
                std::lock_guard<std::mutex> lock(queue_mutex);
                write_queue.push(std::move(local_batch));
                std::cout << "Flush.";
            }
            queue_cv.notify_one();
            local_batch.clear();
        }
    }

    // Final flush
    if (!local_batch.empty()) {
        {
            std::lock_guard<std::mutex> lock(queue_mutex);
            write_queue.push(std::move(local_batch));
        }
        queue_cv.notify_one();
    }

    sqlite3_close(db);
}

void mappingItemMatrix() {
    bool reset_table = true;

    sqlite3* db;
    if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
        std::cerr << "Error opening database.\n";
        return;
    }

    if (reset_table) reset_item_matrix(db);

    auto unique_ids = collect_unique_id(db);
    auto processing_ids_map = collect_processing_id(db, reset_table);
    sqlite3_close(db);

    std::vector<std::pair<std::string, std::string>> processing_ids(
        processing_ids_map.begin(),
        processing_ids_map.end()
    );

    std::cout << "Found " << processing_ids.size() << " files to process\n";

    // Writer
    std::thread writer(writer_thread_func);

    // Producers
    unsigned int num_threads = std::thread::hardware_concurrency();
    if (num_threads == 0) num_threads = 5;

    std::vector<std::thread> producers;
    producers.reserve(num_threads);

    for (unsigned int i = 0; i < num_threads; ++i) {
        producers.emplace_back(
            producer_worker_dynamic,
            std::cref(processing_ids),
            std::cref(unique_ids),
            IDS_PER_WORKER,
            WRITE_THRESHOLD
        );
    }

    for (auto& t : producers)
        t.join();

    producers_done.store(true);
    queue_cv.notify_one();
    writer.join();
}

int main() {
    // Complie: g++ src/recommend.cpp -o recommend.exe -lm -l sqlite3 -lssl -lcrypto
    mappingItemMatrix();
    return 0;
}