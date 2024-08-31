#ifndef BD_HPP
#define BD_HPP

#include<sqlite3.h>
#include<string>
#include<iostream>

#include "env_var.hpp"

const std::string file_list_properties[] = {"id TEXT PRIMARY KEY",
                                    "file_name TEXT",
                                    "file_path TEXT",
                                    "file_type TEXT",
                                    "file_size INTEGER",
                                    "modified_time TEXT",
                                    "epoch_time INTEGER",
                                    "start_ID INTEGER",
                                    "end_ID INTEGER",
                                    "chunk_count INTEGER"};

const std::string log_properties[] = {"id INTEGER PRIMARY KEY AUTOINCREMENT",
                                    "time TEXT",
                                    "message TEXT"};

std::string concatenate_command(const std::string& declare_base, const std::string properties_list[]) {
    std::string fill_base;
    size_t size = sizeof(properties_list) / sizeof(properties_list[0]);
    for (size_t i = 0; i < size; ++i) {
        fill_base += properties_list[i];
        if (i < size - 1) {
            fill_base += ", ";
        }
    }
    return declare_base + " (" + fill_base + ");";
}

void create_table(sqlite3* db, const std::string& declare_base, const std::string properties_list[], size_t size) {
    sqlite3_stmt* stmt;
    std::string command = concatenate_command(declare_base, properties_list, size);
    
    // Prepare the SQL statement
    int rc = sqlite3_prepare_v2(db, command.c_str(), -1, &stmt, NULL);
    if (rc == SQLITE_NOMEM) {
        std::cerr << "Memory allocation failed during table creation." << std::endl;
        return;
    } else if (rc != SQLITE_OK) {
        if (rc == SQLITE_ERROR) {
            std::cerr << "SQL syntax error or another problem: " << sqlite3_errmsg(db) << std::endl;
        }
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


// create file_list table

// conditional duplicate coverage analysis

// dynamic table???

#endif // BD_HPP