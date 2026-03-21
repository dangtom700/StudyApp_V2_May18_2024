#pragma once

#include <string>
#include <vector>
#include <map>
#include <sqlite3.h>
#include <iostream>

class DatabaseManager {
public:
    DatabaseManager(const std::string& dbPath);
    ~DatabaseManager();

    bool execute(const std::string& query);
    std::vector<std::map<std::string, std::string>> selectQuery(const std::string& query);

private:
    sqlite3* db;
    void initSchema();
};
