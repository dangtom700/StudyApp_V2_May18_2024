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
    std::string path;
    int sum;
    int num_unique_tokens;
    std::vector<std::tuple<std::string, int, double>> filtered_tokens;
    double relational_distance;
};

struct DataInfo {
    std::string id;
    std::string file_name;
    std::string file_path;
    int epoch_time;
    int chunk_count;
    int starting_id;
    int ending_id;
};

namespace UTILITIES_HPP {
    namespace Basic {
        std::string decToHexa(int n){
            // ans string to store hexadecimal number
            std::string ans = "";
        
            while (n != 0) {
                // remainder variable to store remainder
                int rem = 0;
                
                // ch variable to store each character
                char ch;
                // storing remainder in rem variable.
                rem = n % 16;

                // check if temp < 10
                if (rem < 10) {
                    ch = rem + 48;
                }
                else {
                    ch = rem + 55;
                }
                
                // updating the ans string with the character variable
                ans += ch;
                n = n / 16;
            }
            
            // reversing the ans string to get the final result
            int i = 0, j = ans.size() - 1;
            while(i <= j)
            {
            std::swap(ans[i], ans[j]);
            i++;
            j--;
            }
            return ans;
        }
        /**
         * @brief Compute the maximum of two integers using bitwise operations
         * @details This function takes two integers as input and returns the maximum of the two using bitwise operations.
         *          This is a more efficient way than using the ternary operator or an if-else statement.
         * @param a an integer
         * @param b an integer
         * @return the maximum of a and b
         */
        int max(int a, int b){
                int c = a - b;
                int flag = (c >> 31) & 1;
                return (a * !flag) + (b * flag);
        }

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

        // reset file info dumper
        void reset_file_info_dumper(const std::filesystem::path& path) {
            std::ofstream file(path);
            if (!file.is_open()) {
                std::cout << "Could not open file" << std::endl;
                return;
            }
            file << "ID, File Name, File Path, Epoch Time, Chunk Count, Starting ID, Ending ID" << std::endl;
        }

        // Dump the contents of a DataEntry to a file
        void data_entry_dump(const DataEntry& entry) {
            std::ofstream main_file(ENV_HPP::data_dumper_path.string(), std::ios::app); // Append to file
            if (!main_file.is_open()) {
                std::cout << "Could not open main file" << std::endl;
                return;
            }
            main_file << entry.path << ", " << entry.sum << ", " << entry.num_unique_tokens << ", " << entry.relational_distance << std::endl;

            // Construct the path for the filtered file
            std::ofstream filtered_file(ENV_HPP::filtered_data_path.string(), std::ios::app);// Append to file
            if (!filtered_file.is_open()) {
                std::cout << "Could not open filtered file" << std::endl;
                return;
            }

            for (const std::tuple<std::string, int, double>& token : entry.filtered_tokens) {
                filtered_file << entry.path << ", " << std::get<0>(token) << ", " << std::get<1>(token) << ", " << std::get<2>(token) << std::endl;
            }
        }

        // Dump the contents of a DataInfo to a file
        void data_info_dump(const DataInfo& info) {
            std::ofstream file(ENV_HPP::data_info_path.string(), std::ios::app); // Append to file
            if (!file.is_open()) {
                std::cout << "Could not open file" << std::endl;
                return;
            }
            file << info.id << ", "
                 << info.file_name << ", "
                 << info.file_path << ", "
                 << info.epoch_time << ", "
                 << info.chunk_count << ", "
                 << info.starting_id << ", "
                 << info.ending_id
                 << std::endl;
        }

        // Extract specific data from given directory with other instructions
        std::vector<std::filesystem::path> extract_data_files(const std::filesystem::path& target_folder, const bool& show_index, const std::string& extension) {
            std::vector<std::filesystem::path> collected_files = UTILITIES_HPP::Basic::list_directory(target_folder, show_index);
            return UTILITIES_HPP::Basic::filter_by_extension(collected_files, extension);
        }

    } // namespace Basic
} // namespace UTILITIES_HPP

#endif // UTILITIES_HPP
