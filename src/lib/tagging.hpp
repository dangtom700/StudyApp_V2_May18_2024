#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <map>
#include <sqlite3.h>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>
#include <tuple>
#include <thread>
#include <mutex>

#include "utilities.hpp"

/* The purposes of this header are to:
    1. Randomly assigned tags to a list of files
    2. User can correctly fix tags to the files
    3. Teach the algorithm to assign tags to the files
    4. Export the tags to a CSV file
    5. Import the tags from a CSV file

*/
namespace Tagging{
    const std::string topics[] = {
    "arts", "culture", "politics", "education", "ethics", "government",
    "health", "history", "religion", "science", "environment", "technology",
    "economics", "law", "media", "philosophy", "psychology", "sociology",
    "business", "management", "marketing", "finance", "accounting", "entrepreneurship",
    "journalism", "communication", "HR", "corporate", "social", "responsibility",
    "leadership", "others", "literature",
    "sports", "literature", "food", "travel", "fashion", "architecture",
    "music", "film", "theater", "linguistics", "anthropology", "geography", 
    "astronomy", "biology", "chemistry", "physics", "engineering", "mathematics",
    "medicine", "ecology", "genetics", "archaeology", "meteorology", "oceanography",
    "botany", "zoology", "robotics", "nanotechnology", "cybersecurity", "AI",
    "guide","introductory","research","computer","programming","software","hardware",
    "IoT","networking","web","mobile","game","development","database","management",
    "security","cloud","computing","big","data","analytics","mechanics", "statistics",
    "electrics", "electronics","modeling","simulation","textbook", "architecture", "design",
    "urban","planning","interior","landscape","graphic","industrial","fashion","product"
    };

    const int topicsSize = sizeof(topics)/sizeof(topics[0]);

    std::string assignTags(const int limit = 10 ){
        std::string tag;
        for(int i = 0; i < limit; i++){
            tag += topics[rand() % topicsSize] + ", ";
        }
        return tag;
    }

    void createTags(std::string sourceDir, bool exportCSV = true, std::string exportPath = "tags.csv"){
        UTILITIES_HPP::Basic::seedRandom();
        int limit = 10;
        std::vector<std::filesystem::path> pdfFiles = UTILITIES_HPP::Basic::filter_by_extension(UTILITIES_HPP::Basic::list_directory(sourceDir), ".pdf");
        std::map<std::string, std::string> File_tags;
        
        for (std::filesystem::path pdfFile : pdfFiles){
            // Remove commas from the filename
            while (pdfFile.filename().string().find(",") != std::string::npos){
                pdfFile.replace_filename(pdfFile.filename().string().replace(pdfFile.filename().string().find(","), 1, ""));
            }
            File_tags[pdfFile.filename().stem().generic_string()] = assignTags(limit);
        }

        if (exportCSV){
            if (!std::filesystem::exists(exportPath)){
                std::filesystem::create_directory(exportPath);
            }
            std::ofstream tagsFile(exportPath);
                std::string headers = "Filename, ";
            for (int i = 0; i < limit; i++){
                headers += "Tag " + std::to_string(i+1) + ", ";
            }
            tagsFile << headers << std::endl;

            for (auto const& [key, val] : File_tags){
                tagsFile << key << ", " << val << std::endl;
            }

            // Close the file
            tagsFile.close();
        }
    }

    //--------------------The functions below are implemented in the main code base. Not the above ones----------------------

    // Fetch unique titles
    std::vector<std::string> fetch_unique_titles(sqlite3* db) {
        std::vector<std::string> unique_titles;
        sqlite3_stmt* stmt;
        const char* query = "SELECT DISTINCT file_name FROM relation_distance";

        if (sqlite3_prepare_v2(db, query, -1, &stmt, nullptr) == SQLITE_OK) {
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                const unsigned char* file_name = sqlite3_column_text(stmt, 0);
                unique_titles.emplace_back(reinterpret_cast<const char*>(file_name));
            }
        } else {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl;
        }

        sqlite3_finalize(stmt);
        return unique_titles;
    }

    // Fetch all data in chunks for memory efficiency
    void fetch_all_data(sqlite3* db, std::unordered_map<std::string, std::unordered_map<std::string, double>>& data) {
        sqlite3_stmt* stmt;
        const char* query = "SELECT file_name, token, relational_distance FROM relation_distance";

        if (sqlite3_prepare_v2(db, query, -1, &stmt, nullptr) == SQLITE_OK) {
            while (sqlite3_step(stmt) == SQLITE_ROW) {
                const unsigned char* file_name = sqlite3_column_text(stmt, 0);
                const unsigned char* token = sqlite3_column_text(stmt, 1);
                double distance = static_cast<double>(sqlite3_column_double(stmt, 2)); // Correctly fetch as double

                std::string file_name_str(reinterpret_cast<const char*>(file_name));
                std::string token_str(reinterpret_cast<const char*>(token));

                data[file_name_str][token_str] = distance;
            }
        } else {
            std::cerr << "Error preparing statement: " << sqlite3_errmsg(db) << std::endl;
        }

        sqlite3_finalize(stmt);
    }

    // Compute distances in parallel
    void compute_distances(const std::vector<std::string>& unique_titles,
                        const std::unordered_map<std::string, std::unordered_map<std::string, double>>& data,
                        std::vector<std::vector<double>>& item_matrix, int start, int end,
                        std::mutex& matrix_mutex, std::mutex& log_mutex) {
        for (int i = start; i < end; ++i) {
            const auto& title = unique_titles[i];
            const auto& token_distance_pairs = data.at(title);

            for (uint16_t j = 0; j < unique_titles.size(); ++j) {
                if (i == j) continue;

                const auto& target_title = unique_titles[j];
                const auto& target_token_distance_pairs = data.at(target_title);

                double total_distance = 0.0;

                // Compute total distance
                for (const auto& [token, distance] : token_distance_pairs) {
                    auto it = target_token_distance_pairs.find(token);
                    double target_distance = (it != target_token_distance_pairs.end()) ? it->second : 0.0;

                    total_distance += distance + target_distance; // Accumulate distance
                }

                // Update the matrix safely
                {
                    std::lock_guard<std::mutex> lock(matrix_mutex);
                    item_matrix[i][j] = total_distance;
                }
            }
        }
    }

    void export_to_csv(const std::vector<std::string>& unique_titles,
                    const std::vector<std::vector<double>>& item_matrix,
                    const std::string& output_filename) {
        std::ofstream csv_file(output_filename);

        if (!csv_file.is_open()) {
            std::cerr << "Error: Could not open file " << output_filename << " for writing." << std::endl;
            return;
        }

        // Write the header row
        csv_file << "Source";
        for (const auto& title : unique_titles) {
            csv_file << "," << title;
        }
        csv_file << "\n";

        // Write the matrix rows
        int count = 0;
        for (std::vector<double> row: item_matrix) {
            csv_file << unique_titles[count];
            count++;
            for (double value : row) {
                csv_file << "," << value;
            }
            csv_file << "\n";
        }

        csv_file.close();
        std::cout << "CSV file written to: " << output_filename << std::endl;
    }

    void insert_item_matrix(const std::vector<std::vector<double>>& item_matrix, const std::vector<std::string>& unique_titles) {
        // Record the data into data as "from, to, distance"
        std::vector<std::tuple<std::string, std::string, double>> data;
        for (uint16_t i = 0; i < item_matrix.size(); i++) {
            for (uint16_t j = 0; j < item_matrix[i].size(); j++) {
                data.push_back({unique_titles[i], unique_titles[j], item_matrix[i][j]});
            }
        }

        // Open the database connection
        sqlite3* db;
        if (sqlite3_open(ENV_HPP::database_path.string().c_str(), &db) != SQLITE_OK) {
            std::cerr << "Error opening database: " << sqlite3_errmsg(db) << std::endl;
            return;
        }

        // Create the table if it does not exist
        std::string create_table_sql = R"(
            DROP TABLE IF EXISTS item_matrix;
            CREATE TABLE IF NOT EXISTS item_matrix (
                source TEXT,
                target TEXT,
                distance REAL,
                PRIMARY KEY (source, target)
            );
        )";

        char* error_msg = nullptr;
        if (sqlite3_exec(db, create_table_sql.c_str(), nullptr, nullptr, &error_msg) != SQLITE_OK) {
            std::cerr << "Error creating table: " << error_msg << std::endl;
            sqlite3_free(error_msg);
            sqlite3_close(db);
            return;
        }

        // Begin a transaction to optimize insertion speed
        if (sqlite3_exec(db, "BEGIN TRANSACTION;", nullptr, nullptr, &error_msg) != SQLITE_OK) {
            std::cerr << "Error starting transaction: " << error_msg << std::endl;
            sqlite3_free(error_msg);
            sqlite3_close(db);
            return;
        }

        // Prepare the SQL statement for insertion
        std::string insert_sql = "INSERT INTO item_matrix (source, target, distance) VALUES (?, ?, ?);";
        sqlite3_stmt* stmt;
        if (sqlite3_prepare_v2(db, insert_sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "Error preparing insert statement: " << sqlite3_errmsg(db) << std::endl;
            sqlite3_close(db);
            return;
        }

        // Bind and execute the insert statement for each record
        for (const auto& [source, target, distance] : data) {
            sqlite3_bind_text(stmt, 1, source.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(stmt, 2, target.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_double(stmt, 3, distance);

            if (sqlite3_step(stmt) != SQLITE_DONE) {
                std::cerr << "Error inserting record: " << sqlite3_errmsg(db) << std::endl;
                sqlite3_finalize(stmt);
                sqlite3_close(db);
                return;
            }

            // Reset the statement for the next record
            sqlite3_reset(stmt);
        }

        // Finalize the statement and commit the transaction
        sqlite3_finalize(stmt);
        if (sqlite3_exec(db, "COMMIT;", nullptr, nullptr, &error_msg) != SQLITE_OK) {
            std::cerr << "Error committing transaction: " << error_msg << std::endl;
            sqlite3_free(error_msg);
            sqlite3_close(db);
            return;
        }

        // Close the database connection
        sqlite3_close(db);
    }

}
