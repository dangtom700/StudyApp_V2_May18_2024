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
        /// @brief List the content of a directory
        /// @param path Path to the directory
        /// @return void
        void list_directory(const std::filesystem::path& path) {
            int count = 1;
            for (const auto& entry : std::filesystem::directory_iterator(path)) {
                std::cout << count << ". " << entry.path().stem() << std::endl;
                count++;
            }
        }

        /// @brief Move the current working directory one level up
        /// @param path The target path
        /// @return The new current path
        std::filesystem::path move_one_level_up(const std::filesystem::path& path){
            int last_index = path.string().find_last_of("\\");
            std::string new_path = path.string().substr(0, last_index);
            return std::filesystem::path(new_path);
        }
    }
}

#endif // UTILITIES_HPP
