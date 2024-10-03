#include <iostream>
#include <filesystem>
#include <vector>
#include <map>

#include "lib\utilities.hpp"
#include "lib\env.hpp"
#include "lib\transform.hpp"

struct DataEntry {
    std::filesystem::path path;
    int sum;
    int num_unique_tokens;
    std::map<std::string, int> filtered_tokens;
    double relational_distance;
};

int main() {
    std::filesystem::path target_folder = ENV_HPP::json_path;
    std::vector<std::filesystem::path> json_files = UTILITIES_HPP::Basic::list_directory(target_folder, false);
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::filter_by_extension(json_files, ".json");

    for (const std::filesystem::path& file : filtered_files) {
        std::map<std::string, int> json_map = TRANSFORMER::json_to_map(file);

        DataEntry row = {
            .path = file,
            .sum = TRANSFORMER::compute_sum_token_json(json_map),
            .num_unique_tokens = TRANSFORMER::count_unique_tokens(json_map),
            .filtered_tokens = TRANSFORMER::token_filter(json_map, ENV_HPP::max_length, ENV_HPP::min_value),
            .relational_distance = TRANSFORMER::Pythagoras(row.filtered_tokens)};
    }

    return 0; // End of program
}
