#ifndef UTILITIES_HPP
#define UTILITIES_HPP

#include <string>
#include <filesystem>
#include <fstream>
#include <vector>
#include <sqlite3.h>
#include <iostream>

namespace UTILITIES_HPP {
    namespace Basic {


        /**
         * @brief List the files in the given directory and return them in a vector
         * @param path The path to the directory to list
         * @param show_index Whether to print out the index of each file
         * @return A vector of file paths
         */
        std::vector<std::filesystem::path> list_directory(const std::filesystem::path& path, bool show_index = false) {
            if (!std::filesystem::exists(path)) {
                std::cout << "Path does not exist" << std::endl;
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

        /// @brief Move the current working directory one level up
        /// @param path The target path
        /// @return The new current path
        std::filesystem::path move_one_level_up(const std::filesystem::path& path){
            int last_index = path.string().find_last_of("\\");
            std::string new_path = path.string().substr(0, last_index);
            return std::filesystem::path(new_path);
        }

        /**
         * @brief Filter a vector of file paths by extension
         * @param files The vector of file paths to filter
         * @param extension The extension to filter by
         * @return A vector of file paths with the given extension
         */
        std::vector<std::filesystem::path> filter_by_extension(const std::vector<std::filesystem::path>& files, const std::string& extension) {
            std::vector<std::filesystem::path> filtered_files;
            for (const auto& file : files) {
                if (file.extension() == extension) {
                    filtered_files.push_back(file);
                }
            }
            return filtered_files;
        }
    }
}

#endif // UTILITIES_HPP
