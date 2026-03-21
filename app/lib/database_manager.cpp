#include "database_manager.hpp"

DatabaseManager::DatabaseManager(const std::string& dbPath) : db(nullptr) {
    if (sqlite3_open(dbPath.c_str(), &db) != SQLITE_OK) {
        std::cerr << "Can't open database: " << sqlite3_errmsg(db) << "\n";
    } else {
        initSchema();
    }
}

DatabaseManager::~DatabaseManager() {
    if (db) {
        sqlite3_close(db);
    }
}

void DatabaseManager::initSchema() {
    const char* sql = R"(
        CREATE TABLE IF NOT EXISTS Books (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            reader TEXT,
            available_date INTEGER
        );
        CREATE TABLE IF NOT EXISTS Borrowers (
            phone_number TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT
        );
        CREATE TABLE IF NOT EXISTS Transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_code TEXT NOT NULL,
            borrower_phone TEXT NOT NULL,
            borrow_date INTEGER NOT NULL,
            due_date INTEGER,
            return_date INTEGER
        );
    )";
    execute(sql);
}

bool DatabaseManager::execute(const std::string& query) {
    char* zErrMsg = 0;
    int rc = sqlite3_exec(db, query.c_str(), nullptr, 0, &zErrMsg);
    if (rc != SQLITE_OK) {
        std::cerr << "SQL error: " << zErrMsg << "\n";
        sqlite3_free(zErrMsg);
        return false;
    }
    return true;
}

static int selectCallback(void* data, int argc, char** argv, char** azColName) {
    auto results = static_cast<std::vector<std::map<std::string, std::string>>*>(data);
    std::map<std::string, std::string> row;
    for (int i = 0; i < argc; i++) {
        row[azColName[i]] = argv[i] ? argv[i] : "";
    }
    results->push_back(row);
    return 0;
}

std::vector<std::map<std::string, std::string>> DatabaseManager::selectQuery(const std::string& query) {
    std::vector<std::map<std::string, std::string>> results;
    char* zErrMsg = 0;
    int rc = sqlite3_exec(db, query.c_str(), selectCallback, &results, &zErrMsg);
    if (rc != SQLITE_OK) {
        std::cerr << "SQL error in selectQuery: " << zErrMsg << "\n";
        sqlite3_free(zErrMsg);
    }
    return results;
}
