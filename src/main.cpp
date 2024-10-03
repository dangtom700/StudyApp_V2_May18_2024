#include <iostream>
#include <filesystem>
#include <vector>
#include <map>
#include <memory> // For smart pointers

#include "lib/utilities.hpp"
#include "lib/env.hpp"
#include "lib/transform.hpp"

int main() {
    try {
        std::filesystem::path target_folder = ENV_HPP::json_path;
        auto json_files = UTILITIES_HPP::Basic::list_directory(target_folder, false);
        auto filtered_files = UTILITIES_HPP::Basic::filter_by_extension(json_files, ".json");

        bool trigger_once = true;
        for (const auto& file : filtered_files) {
            if (trigger_once) {
                trigger_once = false;
                UTILITIES_HPP::Basic::reset_data_dumper(ENV_HPP::data_dumper_path);
            }
            auto json_map = TRANSFORMER::json_to_map(file);

            DataEntry row = {
                file,
                TRANSFORMER::compute_sum_token_json(json_map),
                TRANSFORMER::count_unique_tokens(json_map),
                TRANSFORMER::token_filter(json_map, ENV_HPP::max_length, ENV_HPP::min_value),
                TRANSFORMER::Pythagoras(row.filtered_tokens)
            };

            UTILITIES_HPP::Basic::data_entry_dump(row);
        }

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    return 0; // End of program
}
