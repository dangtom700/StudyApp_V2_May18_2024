#include <iostream>
#include <filesystem>

#include "lib\utilities.hpp"
#include "lib\env.hpp"

int main() {
    // Use json_path from ENV_HPP
    std::filesystem::path target_folder = ENV_HPP::json_path;

    for (int i = 0; i < 3; i++) {

        // Move up one level and list again
        target_folder = UTILITIES_HPP::Basic::move_one_level_up(target_folder);

        // Print the new target folder
        std::cout << target_folder << std::endl;

    }
    
    return 0; // End of program
}
