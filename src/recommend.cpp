#include <filesystem>
#include <vector>
#include <map>
#include <unordered_map>
#include <fstream>
#include <sqlite3.h>
#include <thread>
#include <iostream>
#include <cmath>

#include "lib/utilities.hpp"
#include "lib/env.hpp"
#include "lib/transform.hpp"

void execute_sql(sqlite3* db, const std::string& sql) {
    char* error_message = nullptr;
    int exit = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &error_message);
    if (exit != SQLITE_OK) {
        std::cerr << "SQL error: " << error_message << "\nSQL: " << sql << std::endl;
        sqlite3_free(error_message);
        throw std::runtime_error("SQL execution failed");
    }
}

sqlite3_stmt* prepareStatement(sqlite3* db, const std::string& query) {
    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr);
    if (rc != SQLITE_OK) {
        std::cerr << "Prepare error: " << sqlite3_errmsg(db)
                  << "\nSQL: " << query << std::endl;
        return nullptr;
    }
    return stmt;
}

std::map<std::string,std::string> collect_unique_id(sqlite3* db) {
    std::map<std::string,std::string> ids;
    sqlite3_stmt* stmt = prepareStatement(db,
        "SELECT id, file_name FROM file_info WHERE chunk_count > 0");
    if (!stmt) return ids;

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        std::string id   = reinterpret_cast<const char*>(sqlite3_column_text(stmt,0));
        std::string name = reinterpret_cast<const char*>(sqlite3_column_text(stmt,1));
        ids["title_" + id] = name;
    }
    sqlite3_finalize(stmt);
    return ids;
}

std::vector<std::tuple<std::string,int,double>>
load_token_map(sqlite3* db, const std::string& id) {
    std::vector<std::tuple<std::string,int,double>> tokens;

    sqlite3_stmt* stmt = prepareStatement(db,
        "SELECT Token, frequency, relational_distance "
        "FROM relation_distance WHERE file_name = ?");

    if (!stmt) return tokens;
    sqlite3_bind_text(stmt,1,id.c_str(),-1,SQLITE_TRANSIENT);

    while (sqlite3_step(stmt)==SQLITE_ROW) {
        std::string token =
            reinterpret_cast<const char*>(sqlite3_column_text(stmt,0));
        int freq = sqlite3_column_int(stmt,1);
        double dist = sqlite3_column_double(stmt,2);
        tokens.emplace_back(token,freq,dist);
    }
    sqlite3_finalize(stmt);
    return tokens;
}

void apply_tfidf(sqlite3* db,
                 std::vector<std::tuple<std::string,int,double>>& tokens)
{
    std::unordered_map<std::string,double> tfidf;
    sqlite3_stmt* stmt = prepareStatement(db,
        "SELECT word, tf_idf FROM tf_idf");
    if (!stmt) return;

    while (sqlite3_step(stmt)==SQLITE_ROW) {
        std::string word =
            reinterpret_cast<const char*>(sqlite3_column_text(stmt,0));
        double val = sqlite3_column_double(stmt,1);
        if (std::isnan(val)) val = 0.0;
        tfidf[word] = val;
    }
    sqlite3_finalize(stmt);

    for (auto& [tok,freq,dist] : tokens) {
        auto it = tfidf.find(tok);
        if (it != tfidf.end() && freq>0)
            dist += it->second / freq;
    }
}

std::map<std::string,std::map<std::string,double>>
load_related_tokens(sqlite3* db,
 const std::vector<std::tuple<std::string,int,double>>& tokens)
{
    std::map<std::string,std::map<std::string,double>> out;
    if (tokens.empty()) return out;

    execute_sql(db,
        "CREATE TEMP TABLE IF NOT EXISTS temp_tokens(token TEXT PRIMARY KEY);"
        "DELETE FROM temp_tokens;");

    sqlite3_stmt* ins = prepareStatement(db,
        "INSERT OR IGNORE INTO temp_tokens VALUES(?)");
    for (auto& [tok,_,__] : tokens) {
        sqlite3_bind_text(ins,1,tok.c_str(),-1,SQLITE_TRANSIENT);
        sqlite3_step(ins);
        sqlite3_reset(ins);
    }
    sqlite3_finalize(ins);

    sqlite3_stmt* stmt = prepareStatement(db,
        "SELECT r.file_name, r.Token, r.relational_distance "
        "FROM relation_distance r JOIN temp_tokens t ON r.Token=t.token");

    while (sqlite3_step(stmt)==SQLITE_ROW) {
        std::string file =
            reinterpret_cast<const char*>(sqlite3_column_text(stmt,0));
        std::string tok =
            reinterpret_cast<const char*>(sqlite3_column_text(stmt,1));
        double dist = sqlite3_column_double(stmt,2);
        out[file][tok] = dist;
    }
    sqlite3_finalize(stmt);
    return out;
}

double compute_single_similarity(
    const std::vector<std::tuple<std::string,int,double>>& tokens,
    const std::map<std::string,std::map<std::string,double>>& relmap,
    const std::string& target_id)
{
    auto file_it = relmap.find(target_id);
    if (file_it == relmap.end()) return 0.0;

    std::unordered_map<std::string,double> weights;
    for (auto& [tok,_,dist] : tokens)
        weights[tok]=dist;

    double score = 0.0;
    for (auto& [tok,rel] : file_it->second) {
        auto it = weights.find(tok);
        if (it!=weights.end())
            score += rel * it->second;
    }
    return score;
}

void insert_item_matrix_triangle(
    const std::vector<std::tuple<std::string,std::string,
                                  std::string,std::string,double>>& rows,
    sqlite3* db)
{
    sqlite3_stmt* stmt = prepareStatement(db,
        "INSERT OR IGNORE INTO item_matrix_triangle "
        "(target_id,target_name,source_id,source_name,distance)"
        " VALUES(?,?,?,?,?)");

    for (auto& [tid,tname,sid,sname,dist] : rows) {
        sqlite3_bind_text(stmt,1,tid.c_str(),-1,SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt,2,tname.c_str(),-1,SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt,3,sid.c_str(),-1,SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt,4,sname.c_str(),-1,SQLITE_TRANSIENT);
        sqlite3_bind_double(stmt,5,dist);
        sqlite3_step(stmt);
        sqlite3_reset(stmt);
    }
    sqlite3_finalize(stmt);
}

void ensure_item_matrix_triangle(sqlite3* db, bool reset) {
    if (reset) {
        execute_sql(db, "DROP TABLE IF EXISTS item_matrix_triangle;");
    }

    execute_sql(db,
        "CREATE TABLE IF NOT EXISTS item_matrix_triangle ("
        "target_id   TEXT,"
        "target_name TEXT,"
        "source_id   TEXT,"
        "source_name TEXT,"
        "distance    REAL,"
        "UNIQUE(target_id, source_id)"
        ");"
    );
}

void mappingItemMatrix() {

    constexpr bool RESET_TABLE = false;   // <<< Toggle true to rebuild table

    sqlite3* db;
    if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
        std::cerr << "Error opening database.\n";
        return;
    }

    execute_sql(db, "PRAGMA journal_mode=WAL;");
    execute_sql(db, "PRAGMA synchronous=OFF;");
    execute_sql(db, "PRAGMA temp_store=MEMORY;");

    // Ensure table exists (and optionally reset)
    ensure_item_matrix_triangle(db, RESET_TABLE);

    auto unique_ids = collect_unique_id(db);

    // Convert map → indexed vector for i,j iteration
    std::vector<std::pair<std::string,std::string>>
        items(unique_ids.begin(), unique_ids.end());

    size_t n = items.size();
    std::cout << "Processing " << n << " items\n";

    std::vector<std::tuple<std::string,std::string,
                             std::string,std::string,double>> tank;

    const size_t threshold = 100000;

    for (size_t i = 0; i < n; ++i) {
        auto& [source_id, source_name] = items[i];

        auto tokens = load_token_map(db, source_id);
        if (tokens.empty()) continue;

        apply_tfidf(db, tokens);
        auto relmap = load_related_tokens(db, tokens);

        for (size_t j = i + 1; j < n; ++j) {
            auto& [target_id, target_name] = items[j];

            double score = compute_single_similarity(tokens, relmap, target_id);
            if (score <= 0.0) continue;

            tank.emplace_back(
                target_id, target_name,
                source_id, source_name,
                score
            );
        }

        if (tank.size() >= threshold) {
            execute_sql(db, "BEGIN;");
            insert_item_matrix_triangle(tank, db);
            execute_sql(db, "COMMIT;");
            tank.clear();
        }

        std::cout << "Completed: " << source_name << " (" << (i+1) << "/" << n << "). Tank size: " << tank.size() << "\n";
    }

    if (!tank.empty()) {
        execute_sql(db, "BEGIN;");
        insert_item_matrix_triangle(tank, db);
        execute_sql(db, "COMMIT;");
    }

    sqlite3_close(db);
}

int main() {
    // g++ src/recommend.cpp -o recommend -I./src -lm -l sqlite3 -lssl
    mappingItemMatrix();
    return 0;
}
