#ifndef BD_HPP
#define BD_HPP

#include<sqlite3.h>
#include<string>
#include<cstdlib>

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

std::string concanate_command(const std::string& declare_base, const std::string properties_list []) {
    std::string fill_base = "";
    for (std::string property : properties_list) {
        fill_base += property + ", ";
    }
    return declare_base + "(" + fill_base + ");";
}
// create logging table
void create_log_table(sqlite3* db) {

    sqlite3_stmt* stmt;
    const char* command = concanate_command("CREATE TABLE IF NOT EXISTS log_message", log_properties).c_str();

    sqlite3_prepare_v2(db, command, -1, &stmt, NULL);

    sqlite3_step(stmt);
    sqlite3_finalize(stmt);

    sqlite3_close(db);
}

// create file_list table

// conditional duplicate coverage analysis

// dynamic table???

#endif // BD_HPP