#ifndef UPDATE_INFO
#define UPDATE_INFO

#include <sqlite3.h>
#include <string>
#include <filesystem>
#include <iostream>
#include <ctime>
#include <iomanip>
#include <chrono>
#include <sstream>

#include "env.hpp"

namespace UPDATE_INFO {
    
    /**
     * @brief Get the last write time of a file in epoch time format (seconds since January 1, 1970, 00:00:00 UTC)
     * 
     * @param path The path to the file
     * @return The last write time of the file in epoch time format
     */
    int get_epoch_time(const std::filesystem::path& path) {
        return (int)std::filesystem::last_write_time(path).time_since_epoch().count();
    }

    /**
     * @brief Get the last write time of a file in a human-readable string format
     * 
     * @param path The path to the file
     * @return The last write time of the file as a string in the format "YYYY-MM-DD HH:MM:SS"
     * 
     * If an error occurs while retrieving the last write time (e.g., the file does not exist),
     * an error message is returned instead.
     */
    std::string get_last_write_time(const std::filesystem::path& path) {
        try {
            // Get the last write time of the file
            auto ftime = std::filesystem::last_write_time(path).time_since_epoch().count();

            // Convert to a system clock time point
            auto sctp = std::chrono::system_clock::from_time_t(ftime);
            std::time_t time = std::chrono::system_clock::to_time_t(sctp);

            // Convert to local time
            std::tm* localTime = std::localtime(&time);

            // Format the time into a string
            std::ostringstream oss;
            oss << std::put_time(localTime, "%Y-%m-%d %H:%M:%S");

            return oss.str();
        } catch (const std::filesystem::filesystem_error& e) {
            // Handle any errors that may occur, e.g., file does not exist
            return "Error: " + std::string(e.what());
        }
    }

    /**
     * @brief Create a unique identifier for a given file based on its path, epoch time, chunk count, and starting ID
     * 
     * @param path The path to the file
     * @param epoch_time The epoch time of the file
     * @param chunk_count The number of chunks in the file
     * @param starting_id The starting ID of the file
     * @return A unique identifier for the file as a string
     * 
     * The unique identifier is generated by encoding the file path, epoch time, chunk count, and starting ID, and then
     * combining them with a redundancy bit. The resulting string is in the format "XXXXXXXXXXXXXXXYYYYZZZZWWWRRRR" where
     * XXXXXXXXXXXXXX is the encoded file path, YYYY is the encoded epoch time, ZZZZ is the encoded chunk count, WWW is the
     * encoded starting ID, and RRRR is the redundancy bit.
     */
    std::string create_unique_id(const std::filesystem::path& path, const int& epoch_time, const int& chunk_count, const int& starting_id) {
        unsigned int encoded_file_name = 0;
        unsigned int chunk_factor = 1 << (chunk_count - 1);
        for (char c : path.string()) {
            encoded_file_name += int(c);
        }
        encoded_file_name &= 0xFFFFFFFFFF;
        
        encoded_file_name *= chunk_factor;
        encoded_file_name >>= 2;

        unsigned int encoded_time = (epoch_time & 0xFFFFFF) >> 2;
        unsigned int encoded_chunk_count = (chunk_count & 0x7) << 4;
        unsigned int encoded_starting_id = (starting_id & 0x7F) << 9;
        int redundancy = encoded_file_name ^ encoded_time ^ encoded_chunk_count ^ encoded_starting_id;
        return std::to_string(encoded_file_name) + std::to_string(encoded_time) + std::to_string(encoded_chunk_count) + std::to_string(encoded_starting_id) + std::to_string(redundancy);
    }

    /**
     * @brief Count the number of chunks for a given file name in the pdf_chunks table
     * 
     * @param db The database connection
     * @param file_name The file name to search for
     * @return The number of chunks if found, otherwise 0
     * 
     * This function executes a SELECT query on the pdf_chunks table, binding the given file_name to the ? placeholder.
     * If a row is returned, the chunk_count column is retrieved and returned as an int. Otherwise, 0 is returned.
     */
    int count_chunk_for_each_title(sqlite3* db, const std::string& file_name) {
        sqlite3_stmt* stmt;
        sqlite3_prepare_v2(db, "SELECT COUNT(chunk_index) FROM pdf_chunks WHERE file_name = ?;", -1, &stmt, NULL);
        sqlite3_bind_text(stmt, 1, file_name.c_str(), -1, SQLITE_STATIC);
        int chunk_count = 0;
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            chunk_count = sqlite3_column_int(stmt, 0);
        }
        sqlite3_finalize(stmt);
        return chunk_count;
    }

    /**
     * @brief Get the starting ID for a given file name from the pdf_chunks table
     * 
     * @param db The database connection
     * @param file_name The file name to search for
     * @return The starting ID if found, otherwise 0
     * 
     * This function executes a SELECT query on the pdf_chunks table, binding the given file_name to the ? placeholder.
     * If a row is returned, the starting_id column is retrieved and returned as an int. Otherwise, 0 is returned.
     */
    int get_starting_id(sqlite3* db, const std::string& file_name) {
        sqlite3_stmt* stmt;
        sqlite3_prepare_v2(db, "SELECT starting_id FROM pdf_chunks WHERE file_name = ?;", -1, &stmt, NULL);
        sqlite3_bind_text(stmt, 1, file_name.c_str(), -1, SQLITE_STATIC);
        int starting_id = 0;
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            starting_id = sqlite3_column_int(stmt, 0);
        }
        sqlite3_finalize(stmt);
        return starting_id;
    }

    /**
     * @brief Get the number of chunks for a given file name from the pdf_chunks table
     * 
     * @param db The database connection
     * @param file_name The file name to search for
     * @return The number of chunks if found, otherwise 0
     * 
     * This function executes a SELECT query on the pdf_chunks table, binding the given file_name to the ? placeholder.
     * If a row is returned, the chunk_count column is retrieved and returned as an int. Otherwise, 0 is returned.
     */
    int get_chunk_count(sqlite3* db, const std::string& file_name) {
        sqlite3_stmt* stmt;
        sqlite3_prepare_v2(db, "SELECT chunk_count FROM pdf_chunks WHERE file_name = ?;", -1, &stmt, NULL);
        sqlite3_bind_text(stmt, 1, file_name.c_str(), -1, SQLITE_STATIC);
        int chunk_count = 0;
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            chunk_count = sqlite3_column_int(stmt, 0);
        }
        sqlite3_finalize(stmt);
        return chunk_count;
    }
    
}

#endif // UPDATE_INFO