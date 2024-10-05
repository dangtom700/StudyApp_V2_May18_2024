#include <iostream>
#include <filesystem>
#include <vector>
#include <sqlite3.h>

#include "lib/feature.hpp"
#include "lib/env.hpp"
#include "lib/utilities.hpp"
#include "lib/updateDB.hpp"

int main() {

    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::json_path, true, ".json");
    
    std::cout << "Number of files: " << filtered_files.size() << std::endl;

    std::cout << "Computing relational distance data..." << std::endl;
    FEATURE::computeRelationalDistance(filtered_files, false);
    std::cout << "Finished: Relational distance data computed" << std::endl;

    filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::resource_path, true, ".pdf");

    std::cout << "Computing resource data..." << std::endl;
    FEATURE::computeResourceData(filtered_files, false);
    std::cout << "Finished: Resource data computed" << std::endl;

    return 0; // End of program
}
