#include <iostream>
#include <filesystem>
#include <vector>

#include "lib/feature.hpp"
#include "lib/env.hpp"
#include "lib/utilities.hpp"

int main() {
    std::filesystem::path target_folder = ENV_HPP::json_path;
    std::vector<std::filesystem::path> json_files = UTILITIES_HPP::Basic::list_directory(target_folder, false);
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::filter_by_extension(json_files, ".json");
    
    std::cout << "Number of files: " << filtered_files.size() << std::endl;

    std::cout << "Computing relational distance data..." << std::endl;
    FEATURE::computeRelationalDistance(filtered_files, false);
    std::cout << "Finished: Relational distance data computed" << std::endl;

    return 0; // End of program
}
