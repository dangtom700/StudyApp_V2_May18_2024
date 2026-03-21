#include "database_manager.hpp"
#include <cassert>
#include <iostream>
#include <filesystem>

void test_database_manager() {
    std::string db_path = "test_db.sqlite";
    
    // Clean up before test
    if (std::filesystem::exists(db_path)) {
        std::filesystem::remove(db_path);
    }

    {
        DatabaseManager db(db_path);
        
        // Test basic execution
        bool success = db.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT);");
        assert(success && "Failed to create table");

        success = db.execute("INSERT INTO test_table (name) VALUES ('TestName');");
        assert(success && "Failed to insert data");

        // Test querying
        auto results = db.selectQuery("SELECT * FROM test_table;");
        assert(results.size() == 1 && "Query should return exactly 1 row");
        assert(results[0]["name"] == "TestName" && "Inserted data mismatch");
    }

    // Clean up after test
    if (std::filesystem::exists(db_path)) {
        std::filesystem::remove(db_path);
    }
    
    std::cout << "DatabaseManager tests passed." << std::endl;
}
