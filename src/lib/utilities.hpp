#ifndef UTILITIES_HPP
#define UTILITIES_HPP

#include <string>
#include <filesystem>
#include <fstream>
#include <vector>
#include <iostream>
#include <tuple>
#include "env.hpp" // Include ENV_HPP definition
#include <algorithm>

struct DataEntry
{ // Make sure this struct is defined
    std::string path;
    int sum;
    int num_unique_tokens;
    std::vector<std::tuple<std::string, int, double>> filtered_tokens;
    double relational_distance;
};

struct DataInfo
{
    std::string id;
    std::string file_name;
    std::string file_path;
    int epoch_time;
    int chunk_count;
    int starting_id;
    int ending_id;
};

struct TFIDFRecord
{
    std::string word;
    int freq;
    int doc_count;
    double tf_idf;
};

namespace UTILITIES_HPP
{
    namespace Basic
    {

        // List the files in the given directory and return them in a vector
        std::vector<std::filesystem::path> list_directory(const std::filesystem::path &path, bool show_index = false)
        {
            if (!std::filesystem::exists(path))
            {
                std::cout << "Path does not exist" << std::endl;
                std::cout << "Path: " << path << std::endl;
                return {};
            }

            std::vector<std::filesystem::path> files;
            int count = (show_index) ? 1 : 0;
            for (const auto &entry : std::filesystem::directory_iterator(path))
            {
                files.push_back(entry.path());
                if (show_index)
                {
                    std::cout << count << ": " << entry.path() << std::endl;
                    count++;
                }
            }

            return files; // Return the list of files
        }

        // Filter a vector of file paths by extension
        std::vector<std::filesystem::path> filter_by_extension(const std::vector<std::filesystem::path> &files, const std::string &extension)
        {
            std::vector<std::filesystem::path> filtered_files;
            for (const auto &file : files)
            {
                if (file.extension() == extension)
                {
                    filtered_files.push_back(file);
                }
            }
            return filtered_files;
        }

        // std::ofstream does not create missing parent directories, so a fresh checkout
        // (where data/processed_data does not exist yet) fails every dump silently.
        bool ensure_parent_dir(const std::filesystem::path &path)
        {
            const std::filesystem::path parent = path.parent_path();
            std::error_code ec;
            if (parent.empty() || std::filesystem::exists(parent, ec))
                return true;

            std::filesystem::create_directories(parent, ec);
            if (ec)
            {
                std::cout << "Could not create directory " << parent << ": " << ec.message() << std::endl;
                return false;
            }
            return true;
        }

        // Create the directories the C++ stages write into. sqlite3_open() will not create a
        // missing parent either, so a full restart (deleting data/) needs these in place
        // before any stage runs, not just before the first dump.
        void ensure_data_directories()
        {
            for (const std::filesystem::path &dir : {ENV_HPP::data_root, ENV_HPP::processed_data_path})
            {
                std::error_code ec;
                std::filesystem::create_directories(dir, ec);
                if (ec)
                    std::cout << "Could not create directory " << dir << ": " << ec.message() << std::endl;
            }
        }

        // Reset data dumper
        void reset_data_dumper(const std::filesystem::path &path)
        {
            if (!ensure_parent_dir(path))
                return;

            std::ofstream file(path);
            if (!file.is_open())
            {
                std::cout << "Could not open file " << path << std::endl;
                return;
            }
            file << "Path, Sum, Unique Tokens, Relational Distance" << std::endl;

            if (!ensure_parent_dir(ENV_HPP::filtered_data_path))
                return;

            std::ofstream filtered_file(ENV_HPP::filtered_data_path.string());
            if (!filtered_file.is_open())
            {
                std::cout << "Could not open filtered file " << ENV_HPP::filtered_data_path << std::endl;
                return;
            }

            filtered_file << "Path, Token, Frequency, Relational Distance" << std::endl;
        }

        // reset file info dumper
        void reset_file_info_dumper(const std::filesystem::path &path)
        {
            if (!ensure_parent_dir(path))
                return;

            std::ofstream file(path);
            if (!file.is_open())
            {
                std::cout << "Could not open file " << path << std::endl;
                return;
            }
            file << "ID, File Name, File Path, Epoch Time, Chunk Count" << std::endl;
        }

        // Dump the contents of a DataEntry to a file
        void data_entry_dump(const DataEntry &entry)
        {
            if (!ensure_parent_dir(ENV_HPP::data_dumper_path))
                return;

            std::ofstream main_file(ENV_HPP::data_dumper_path.string(), std::ios::app); // Append to file
            if (!main_file.is_open())
            {
                std::cout << "Could not open main file " << ENV_HPP::data_dumper_path << std::endl;
                return;
            }
            main_file << entry.path << ", " << entry.sum << ", " << entry.num_unique_tokens << ", " << entry.relational_distance << std::endl;

            // Construct the path for the filtered file
            if (!ensure_parent_dir(ENV_HPP::filtered_data_path))
                return;

            std::ofstream filtered_file(ENV_HPP::filtered_data_path.string(), std::ios::app); // Append to file
            if (!filtered_file.is_open())
            {
                std::cout << "Could not open filtered file " << ENV_HPP::filtered_data_path << std::endl;
                return;
            }

            for (const std::tuple<std::string, int, double> &token : entry.filtered_tokens)
            {
                filtered_file << entry.path << ", "
                              << std::get<0>(token) << ", "
                              << std::get<1>(token) << ", "
                              << std::get<2>(token)
                              << std::endl;
            }
        }

        // Dump the contents of a DataInfo to a file
        void data_info_dump(const DataInfo &info)
        {
            if (!ensure_parent_dir(ENV_HPP::data_info_path))
                return;

            std::ofstream file(ENV_HPP::data_info_path.string(), std::ios::app | std::ios::binary);
            if (!file.is_open())
            {
                std::cout << "Could not open file " << ENV_HPP::data_info_path << std::endl;
                return;
            }
            file << info.id << ", "
                 << info.file_name << ", "
                 << info.file_path << ", "
                 << info.epoch_time << ", "
                 << info.chunk_count
                 << std::endl;
        }

        // Extract specific data from given directory with other instructions
        std::vector<std::filesystem::path> extract_data_files(const std::filesystem::path &target_folder, const bool &show_index, const std::string &extension)
        {
            std::vector<std::filesystem::path> collected_files = UTILITIES_HPP::Basic::list_directory(target_folder, show_index);
            return UTILITIES_HPP::Basic::filter_by_extension(collected_files, extension);
        }
    } // namespace Basic
    namespace Timer
    {
        std::chrono::high_resolution_clock::time_point show_update(const uint16_t &i, const uint16_t &size, const std::chrono::high_resolution_clock::time_point &start_time, const uint16_t &update_freq, const std::string &item_name = "items")
        {
            std::cout << "Processed: (" << i << "/" << size << ") " << item_name << "\n";
            if (i % update_freq == 0 && i != 0)
            {
                std::chrono::high_resolution_clock::time_point end_time = std::chrono::high_resolution_clock::now();
                double elapsed_sec = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count() / 1000.0;
                double avg_sec_per_item = elapsed_sec / static_cast<double>(update_freq);
                int estimated_time_left = static_cast<int>((size - (i)) * avg_sec_per_item);
                int seconds = estimated_time_left % 60;
                int minutes = (estimated_time_left / 60) % 60;
                int hours = estimated_time_left / 3600;
                std::printf("Estimated time left: %02dHR %02dMin %02dSec (%d samples left)\n",
                            hours, minutes, seconds, static_cast<int>(size - (i)));
                return end_time;
            }

            return start_time;
        }
    }
} // namespace UTILITIES_HPP

#endif // UTILITIES_HPP
