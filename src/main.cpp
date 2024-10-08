#include <iostream>
#include <filesystem>
#include <vector>
#include <functional>
#include <map>
#include <limits>
#include <string>
#include <algorithm>

#include "lib/feature.hpp"
#include "lib/env.hpp"
#include "lib/utilities.hpp"

void displayHelp() {
    std::cout << "This program is created as an integrated part of the word tokenizer project\n"
                 "to compute the relational distance of each token in a given JSON file.\n"
                 "The relational distance is the Euclidean norm of the vector of token frequencies.\n"
                 "While Python provides a wide range of Natural Language Processing libraries,\n"
                 "C++ offers performance benefits for number crunching and heavy data processing.\n"
                 "This program resolves these issues without using external libraries." << std::endl;
}

void computeRelationalDistance() {
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::json_path, false, ".json");
    std::cout << "Computing relational distance data..." << std::endl;
    FEATURE::computeRelationalDistance(filtered_files, false, true, true);
    std::cout << "Finished: Relational distance data computed." << std::endl;
}

void updateDatabaseInformation() {
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::resource_path, false, ".pdf");
    std::cout << "Updating database information..." << std::endl;
    FEATURE::computeResourceData(filtered_files, false, true, true);
    std::cout << "Finished: Database information updated." << std::endl;
}

void processPrompt() {
    std::cout << "Processing prompt..." << std::endl;
    FEATURE::processPrompt();
    std::cout << "Finished: Prompt processed." << std::endl;
}

int main(int argc, char* argv[]) {
    // Check if any command-line arguments were provided
    if (argc < 2) {
        std::cout << "No command provided. Use --displayHelp for available options." << std::endl;
        return 1;
    }

    // Map to store command-line options
    std::map<std::string, std::function<void()>> actions {
        {"--displayHelp", displayHelp},
        {"--computeRelationalDistance", computeRelationalDistance},
        {"--updateDatabaseInformation", updateDatabaseInformation},
        {"--processPrompt", processPrompt}
    };

    // Iterate through the provided command-line arguments and execute corresponding actions
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        std::transform(arg.begin(), arg.end(), arg.begin(), ::tolower);  // Normalize to lowercase

        if (actions.find(arg) != actions.end()) {
            actions[arg]();  // Execute the corresponding function
        } else {
            std::cout << "Invalid option: " << arg << ". Please try again." << std::endl;
        }
    }

    std::cout << "Finished program." << std::endl;
    return 0;
}
