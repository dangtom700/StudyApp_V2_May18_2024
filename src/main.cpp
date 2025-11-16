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

const bool reset_table = true;
const bool show_progress = false;
const bool is_dumped = true;

void displayHelp() {
    std::cout << "This program is created as an integrated part of the word tokenizer project "
                 "to compute the relational distance of each token in a given JSON file. "
                 "The relational distance is the Euclidean norm of the vector of token frequencies. "
                 "While Python provides a wide range of Natural Language Processing libraries, "
                 "C++ offers performance benefits for number crunching and heavy data processing. "
                 "This program resolves these issues without using external libraries." << std::endl;
}

void computeRelationalDistance() {
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::json_path, false, ".json");

    if (filtered_files.empty()) {
        std::cout << "No JSON files found in the specified directory." << std::endl;
        return;
    }
    if (!reset_table) filtered_files = FEATURE::skim_files(filtered_files, ".json");

    std::cout << "Computing relational distance data..." << std::endl;
    FEATURE::computeRelationalDistance(filtered_files, show_progress, reset_table, is_dumped);
    std::cout << "Finished: Relational distance data computed." << std::endl;
}

void updateDatabaseInformation() {
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::resource_path, false, ".pdf");

    if (filtered_files.empty()) {
        std::cout << "No PDF files found in the specified directory." << std::endl;
        return;
    }
    if (!reset_table) filtered_files = FEATURE::skim_files(filtered_files, ".pdf");

    std::cout << "Updating database information..." << std::endl;
    FEATURE::computeResourceData(filtered_files, show_progress, reset_table, is_dumped);
    std::cout << "Finished: Database information updated." << std::endl;
}

void processPrompt() {
    std::cout << "Processing prompt..." << std::endl;
    FEATURE::processPrompt(9999);
    std::cout << "Finished: Prompt processed." << std::endl;
}

void computeTFIDF() {
    std::cout << "Computing TF-IDF..." << std::endl;
    FEATURE::computeTFIDF();
    std::cout << "Finished: TF-IDF computed." << std::endl;
}

int main(int argc, char* argv[]) {
    // Check if any command-line arguments were provided
    if (argc < 2) {
        std::cout << "No command provided. Use --displayHelp for available options." << std::endl;
        return 1;
    }

    // Map to store command-line options
    std::map<std::string, std::function<void()>> actions {
        {"--displayhelp", displayHelp},
        {"--computerelationaldistance", computeRelationalDistance},
        {"--updatedatabaseinformation", updateDatabaseInformation},
        {"--processprompt", processPrompt},
        {"--computetfidf", computeTFIDF}
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

    return 0;
}
