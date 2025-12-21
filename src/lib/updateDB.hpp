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
#include <openssl/evp.h>

#include "env.hpp"
#include "utilities.hpp"

namespace UPDATE_INFO {
    
    /**
     * @brief Get the last write time of a file in epoch time format (seconds since January 1, 1970, 00:00:00 UTC)
     * 
     * @param path The path to the file
     * @return The last write time of the file in epoch time format
     */
    int get_epoch_time(const std::filesystem::path& path) {
        try {
            // Get the last write time of the file
            auto ftime = std::filesystem::last_write_time(path);

            // Convert file time to system time
            auto sctp = std::chrono::time_point_cast<std::chrono::system_clock::duration>(
                ftime - decltype(ftime)::clock::now() + std::chrono::system_clock::now()
            );

            // Get the epoch time in seconds
            auto epoch_time = std::chrono::system_clock::to_time_t(sctp);

            return static_cast<int>(epoch_time);
        } catch (const std::filesystem::filesystem_error& e) {
            std::cerr << "Error getting last write time for file: " << e.what() << std::endl;
            return -1; // Return -1 to indicate an error occurred
        }
    }

    std::string md5_hash(const std::string& input) {
        unsigned char digest[EVP_MAX_MD_SIZE]; // MD5 hash size (max digest size for all algorithms)
        unsigned int digest_length = 0;
    
        EVP_MD_CTX* ctx = EVP_MD_CTX_new();  // Create digest context
        if (!ctx) {
            throw std::runtime_error("Failed to create OpenSSL EVP_MD_CTX");
        }
    
        if (EVP_DigestInit_ex(ctx, EVP_md5(), nullptr) != 1 ||
            EVP_DigestUpdate(ctx, input.c_str(), input.size()) != 1 ||
            EVP_DigestFinal_ex(ctx, digest, &digest_length) != 1) {
            EVP_MD_CTX_free(ctx);
            throw std::runtime_error("OpenSSL MD5 hashing failed");
        }
    
        EVP_MD_CTX_free(ctx); // Free context
    
        // Convert to hexadecimal string
        std::ostringstream oss;
        for (unsigned int i = 0; i < digest_length; ++i) {
            oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(digest[i]);
        }
    
        return oss.str();
    }
    
    std::string create_unique_id(const std::filesystem::path& path) {
        if (!std::filesystem::exists(path)) {
            throw std::runtime_error("File does not exist: " + path.string());
        }
        
        std::ostringstream input_stream;
        input_stream << "XOX - Path Name: " << path.u8string() << " End of File Path.";
    
        return md5_hash(input_stream.str());
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
        sqlite3_prepare_v2(db, "SELECT COUNT(chunk_id) FROM pdf_chunks WHERE file_name = ?;", -1, &stmt, NULL);
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