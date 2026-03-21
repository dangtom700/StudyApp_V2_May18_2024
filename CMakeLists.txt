cmake_minimum_required(VERSION 3.10)
project(ContentRecommendation)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# -----------------------------
# ONLY build app/
# -----------------------------
add_executable(LibraryManager
    app/main.cpp
    app/lib/database_manager.cpp
    app/lib/library_system.cpp
)

target_include_directories(LibraryManager PUBLIC
    app/lib
)

# Dependencies
find_package(nlohmann_json REQUIRED)
find_package(SQLite3 REQUIRED)

target_link_libraries(LibraryManager PRIVATE 
    nlohmann_json::nlohmann_json
    SQLite::SQLite3
)

# -----------------------------
# Tests
# -----------------------------
enable_testing()

add_executable(test_library
    test/test_main.cpp
    test/test_database_manager.cpp
    test/test_library_system.cpp
    app/lib/database_manager.cpp
    app/lib/library_system.cpp
)

target_include_directories(test_library PUBLIC
    app/lib
)

target_link_libraries(test_library PRIVATE 
    nlohmann_json::nlohmann_json
    SQLite::SQLite3
)

add_test(NAME LibraryTests COMMAND test_library)
