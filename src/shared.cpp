#include <iostream>
#include <vector>
#include <string>
#include <filesystem>
#include "lib/feature.hpp"
#include "lib/env.hpp"
#include "lib/utilities.hpp"

extern "C" {
    void compute_relational_distance() {
        std::cout << "Computing relational distance...\n";
        std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::json_path, false, ".json");
        FEATURE::computeRelationalDistance(filtered_files, false, true, false);
        std::cout << "Finished computing relational distance.\n";
    }

    void update_database_information() {
        std::cout << "Updating database information...\n";
        std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::resource_path, false, ".pdf");
        FEATURE::computeResourceData(filtered_files, false, true, false);
        std::cout << "Finished updating database information.\n";
    }

    void process_prompt(int top_n) {
        std::cout << "Processing prompt...\n";
        FEATURE::processPrompt(top_n);
        std::cout << "Finished processing prompt.\n";
    }
}
