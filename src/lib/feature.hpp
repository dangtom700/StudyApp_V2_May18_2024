#ifndef FEATURE_HPP
#define FEATURE_HPP

#include <filesystem>
#include <vector>
#include <map>
#include <fstream>
#include <memory> // For smart pointers
#include <sqlite3.h>

#include "utilities.hpp"
#include "env.hpp"
#include "transform.hpp"
#include "updateDB.hpp"

namespace FEATURE {
    /**
     * Compute the relational distance of each token in the given list of files.
     * The relational distance is the Euclidean norm of the vector of token frequencies.
     * The computed relational distances are stored in the data dumper file.
     *
     * @param filtered_files A vector of file paths to process.
     */
    void computeRelationalDistance(const std::vector<std::filesystem::path>& filtered_files,
                                    const bool show_progress = true) {
        try {
            bool trigger_once = true;
            for (const std::filesystem::path& file : filtered_files) {
                if (trigger_once) {
                    trigger_once = false;
                    UTILITIES_HPP::Basic::reset_data_dumper(ENV_HPP::data_dumper_path);
                }
                std::map<std::string,int> json_map = TRANSFORMER::json_to_map(file);

                DataEntry row = {
                    .path = file,
                    .sum = TRANSFORMER::compute_sum_token_json(json_map),
                    .num_unique_tokens = TRANSFORMER::count_unique_tokens(json_map),
                    .relational_distance = TRANSFORMER::Pythagoras(json_map),
                };

                row.filtered_tokens = TRANSFORMER::token_filter(json_map, ENV_HPP::max_length, ENV_HPP::min_value, row.relational_distance);
                UTILITIES_HPP::Basic::data_entry_dump(row);

                if (show_progress) {
                    std::cout << "Processed: " << file << std::endl;
                }
            }
            std::cout << "Computing relational distance data finished" << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "Error: " << e.what() << std::endl;
        }        
    }

    void computeResourceData(const std::vector<std::filesystem::path>& filtered_files,
                             const bool& show_progress = true,
                             const bool& reset_table = true) {
        try {
            // Open database
            sqlite3* db = nullptr;
            if (sqlite3_open(ENV_HPP::data_dumper_path.string().c_str(), &db) != SQLITE_OK) {
                std::cerr << "Could not open database" << std::endl;
                return;
            }

            if (reset_table) {
                // Drop the table if it already exists (table name: data_info)
                sqlite3_exec(db, "DROP TABLE IF EXISTS data_info;", nullptr, nullptr, nullptr);

                // Create the table (table name: data_info)
                std::string command = "CREATE TABLE data_info()" \
                                    "id TEXT PRIMARY KEY," \
                                    "file_name TEXT," \
                                    "file_path TEXT," \
                                    "last_write_time TEXT," \
                                    "epoch_time INTEGER," \
                                    "chunk_count INTEGER," \
                                    "starting_id INTEGER," \
                                    "ending_id INTEGER);";
                sqlite3_exec(db,command.c_str(), nullptr, nullptr, nullptr);
            }

            for (const std::filesystem::path& file : filtered_files) {
                DataInfo info = {
                    .file_name = file.filename().string(),
                    .file_path = file.string(),
                    .last_write_time = get_last_write_time(file),
                    .epoch_time = std::chrono::duration_cast<std::chrono::milliseconds>(std::filesystem::last_write_time(file).time_since_epoch()).count(),
                    .chunk_count = UPDATE_INFO::count_chunk_for_each_title(db, file.string()),
                    .starting_id = UPDATE_INFO::get_starting_id(db, file.string()),
                    .ending_id = UPDATE_INFO::get_ending_id(db, file.string()),
                };

                info.id = UPDATE_INFO::create_unique_id(file, info.epoch_time, info.chunk_count, info.starting_id);
                std::cout << "Processed: " << file << " with id: " << info.id << std::endl;
                UPDATE_INFO::insert_data_info(db, info);
            }
            sqlite3_close(db);
            if (show_progress) {
                std::cout << "Computing resource data finished" << std::endl;
            }
        } catch (const std::exception& e) {
            std::cerr << "Error: " << e.what() << std::endl;
        }
    }
}

#endif // FEATURE_HPP