#ifndef UTILITIES_HPP
#define UTILITIES_HPP

#include <string>
#include <filesystem>
#include <fstream>
#include <vector>
#include <iostream>
#include <map>
#include "env.hpp"  // Include ENV_HPP definition

struct DataEntry {  // Make sure this struct is defined
    std::filesystem::path path;
    int sum;
    int num_unique_tokens;
    std::map<std::string, int> filtered_tokens;
    double relational_distance;
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
            std::ofstream filtered_file(ENV_HPP::processed_data_path / ("filtered") / (entry.path.stem().string() + ".csv"));
            if (!filtered_file.is_open()) {
                std::cout << "Could not open filtered file" << std::endl;
                return;
            }

            for (const auto& [key, value] : entry.filtered_tokens) {
                filtered_file << key << ", " << value << std::endl;
            }
        }

    } // namespace Basic
} // namespace UTILITIES_HPP

#endif // UTILITIES_HPP
