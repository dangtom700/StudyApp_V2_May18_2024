cmake_minimum_required(VERSION 3.10)
project(ContentRecommendation)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# -----------------------------
# ONLY build app/
# -----------------------------
add_executable(LibraryManager
    app/main.cpp
)

target_include_directories(LibraryManager PUBLIC
    app/lib
)

# JSON library
find_package(nlohmann_json REQUIRED)
target_link_libraries(LibraryManager PRIVATE nlohmann_json::nlohmann_json)
