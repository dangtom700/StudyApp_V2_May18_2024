#ifndef BD_HPP
#define BD_HPP

#include <sqlite3.h>
#include <string>
#include <iostream>
#include <map>
#include <vector>

#include "env_var.hpp"

// Constants
const std::vector<std::string> file_list_properties = {
    "id TEXT PRIMARY KEY",
    "file_name TEXT",
    "file_path TEXT",
    "file_type TEXT",
    "file_size INTEGER",
    "modified_time TEXT",
    "epoch_time INTEGER",
    "start_ID INTEGER",
    "end_ID INTEGER",
    "chunk_count INTEGER"
};

const std::vector<std::string> word_freq_properties = {
    "word TEXT PRIMARY KEY",
    "frequency INTEGER"
};

const std::vector<std::string> log_properties = {
    "id INTEGER PRIMARY KEY AUTOINCREMENT",
    "time TEXT",
    "message TEXT"
};

const std::map<std::string, std::vector<std::string>> table_properties = {
    {"file_list", file_list_properties},
    {"word_freq", word_freq_properties},
    {"log", log_properties},
    {"coverage", word_freq_properties}
};

// Functions
std::string concatenate_command(const std::string& declare_base, const std::vector<std::string>& properties_list) {
    std::string fill_base;
    for (size_t i = 0; i < properties_list.size(); ++i) {
        fill_base += properties_list[i];
        if (i < properties_list.size() - 1) {
            fill_base += ", ";
        }
    }
    return declare_base + " (" + fill_base + ");";
}

void create_table(sqlite3* db, const std::string& declare_base, const std::vector<std::string>& properties_list) {
    sqlite3_stmt* stmt;
    std::string command = concatenate_command(declare_base, properties_list);

    // Prepare the SQL statement
    int rc = sqlite3_prepare_v2(db, command.c_str(), -1, &stmt, NULL);
    if (rc == SQLITE_NOMEM) {
        std::cerr << "Memory allocation failed during table creation." << std::endl;
        return;
    } else if (rc != SQLITE_OK) {
        std::cerr << "SQL syntax error or another problem: " << sqlite3_errmsg(db) << std::endl;
        sqlite3_finalize(stmt);
        return;
    }

    // Execute the SQL statement
    rc = sqlite3_step(stmt);
    if (rc == SQLITE_DONE) {
        std::cout << "Table created successfully." << std::endl;
    } else if (rc == SQLITE_CONSTRAINT) {
        std::cerr << "Table already exists or a constraint failed: " << sqlite3_errmsg(db) << std::endl;
    } else if (rc == SQLITE_ERROR) {
        std::cerr << "SQL error during execution: " << sqlite3_errmsg(db) << std::endl;
    }

    // Finalize the statement
    sqlite3_finalize(stmt);
}

void initialize_database(const std::string& db_name, const std::map<std::string, std::vector<std::string>>& table_properties = table_properties) {
    sqlite3* db;

    // Open the SQLite database connection
    int rc = sqlite3_open(db_name.c_str(), &db);
    if (rc != SQLITE_OK) {
        std::cerr << "Cannot open database: " << sqlite3_errmsg(db) << std::endl;
        sqlite3_close(db);
        exit(0);
    }

    // Create the tables
    for (const auto& [table_name, properties_list] : table_properties) {
        create_table(db, "CREATE TABLE IF NOT EXISTS " + table_name, properties_list);
    }

    // Close the SQLite database connection
    sqlite3_close(db);
}

#endif // BD_HPP
