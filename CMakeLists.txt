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
