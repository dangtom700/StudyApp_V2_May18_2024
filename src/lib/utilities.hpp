#ifndef UTILITIES_HPP
#define UTILITIES_HPP

#include <string>
#include <filesystem>
#include <fstream>
#include <vector>
#include <iostream>
#include <tuple>
#include "env.hpp"  // Include ENV_HPP definition

struct DataEntry {  // Make sure this struct is defined
    std::filesystem::path path;
    int sum;
    int num_unique_tokens;
    std::vector<std::tuple<std::string, int, double>> filtered_tokens;
    double relational_distance;
};

struct DataInfo {
    std::string id;
    std::string file_name;
    std::string file_path;
    std::string last_write_time;
    int epoch_time;
    int chunk_count;
    int starting_id;
    int ending_id;
};

namespace UTILITIES_HPP {
    namespace Basic {

        // List the files in the given directory and return them in a vector
        std::vector<std::filesystem::path> list_directory(const std::filesystem::path& path, bool show_index = false) {
            if (!std::filesystem::exists(path)) {
                std::cout << "Path does not exist" << std::endl;
                std::cout << "Path: " << path << std::endl;
                return {};
            }

            std::vector<std::filesystem::path> files;
            int count = (show_index) ? 1 : 0;
            for (const auto& entry : std::filesystem::directory_iterator(path)) {
                files.push_back(entry.path());
                if (show_index) {
                    std::cout << count << ": " << entry.path() << std::endl;
                    count++;
                }
            }

            return files; // Return the list of files
        }

        // Filter a vector of file paths by extension
        std::vector<std::filesystem::path> filter_by_extension(const std::vector<std::filesystem::path>& files, const std::string& extension) {
            std::vector<std::filesystem::path> filtered_files;
            for (const auto& file : files) {
                if (file.extension() == extension) {
                    filtered_files.push_back(file);
                }
            }
            return filtered_files;
        }

        // Reset data dumper
        void reset_data_dumper(const std::filesystem::path& path) {
            std::ofstream file(path);
            if (!file.is_open()) {
                std::cout << "Could not open file" << std::endl;
                return;
            }
            file << "Path, Sum, Unique Tokens, Relational Distance" << std::endl;

            std::ofstream filtered_file(ENV_HPP::filtered_data_path.string());
            if (!filtered_file.is_open()) {
                std::cout << "Could not open filtered file" << std::endl;
                return;
            }

            filtered_file << "Path, Token, Frequency, Relational Distance" << std::endl;
        }

        // Dump the contents of a DataEntry to a file
        void data_entry_dump(const DataEntry& entry) {
            std::ofstream main_file(ENV_HPP::data_dumper_path.string(), std::ios::app); // Append to file
            if (!main_file.is_open()) {
                std::cout << "Could not open main file" << std::endl;
                return;
            }
            main_file << entry.path.stem() << ", " << entry.sum << ", " << entry.num_unique_tokens << ", " << entry.relational_distance << std::endl;

            // Construct the path for the filtered file
            std::ofstream filtered_file(ENV_HPP::filtered_data_path.string(), std::ios::app);// Append to file
            if (!filtered_file.is_open()) {
                std::cout << "Could not open filtered file" << std::endl;
                return;
            }

            for (const std::tuple<std::string, int, double>& token : entry.filtered_tokens) {
                filtered_file << entry.path.stem() << ", " << std::get<0>(token) << ", " << std::get<1>(token) << ", " << std::get<2>(token) << std::endl;
            }
        }

        // Extract specific data from given directory with other instructions
        std::vector<std::filesystem::path> extract_data_files(const std::filesystem::path& target_folder, const bool& show_index = false, const std::string& extension) {
            std::vector<std::filesystem::path> collected_files = UTILITIES_HPP::Basic::list_directory(target_folder, show_index);
            return UTILITIES_HPP::Basic::filter_by_extension(collected_files, extension);
        }

    } // namespace Basic
} // namespace UTILITIES_HPP

#endif // UTILITIES_HPP
