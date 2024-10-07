#include <iostream>
#include <filesystem>
#include <vector>
#include <functional>
#include <map>
#include <limits>

#include "lib/feature.hpp"
#include "lib/env.hpp"
#include "lib/utilities.hpp"

void displayHelp() {
    std::cout << "This program is created as an integrated part of the word tokenizer project\n"
                 "to compute the relational distance of each token in a given JSON file.\n"
                 "The relational distance is the Euclidean norm of the vector of token frequencies.\n"
                 "While Python provides a wide range of Natural Language Processing libraries,\n"
                 "Python is not so fast at number crunching and heavy data processing.\n"
                 "The C++ program is written to resolve this issue without using external libraries." << std::endl;
}

void exitProgram() {
    std::cout << "Exiting program..." << std::endl;
}

void computeRelationalDistance() {
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::json_path, false, ".json");
    std::cout << "Computing relational distance data..." << std::endl;
    FEATURE::computeRelationalDistance(filtered_files, false, true, true);
    std::cout << "Finished: Relational distance data computed" << std::endl;
}

void updateDatabaseInformation() {
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::resource_path, false, ".pdf");
    std::cout << "Updating database information..." << std::endl;
    FEATURE::computeResourceData(filtered_files, false, true, true);
    std::cout << "Finished: Database information updated" << std::endl;
}

void showOptions() {
    std::cout << "0. Display help" << std::endl;
    std::cout << "1. Exit program" << std::endl;
    std::cout << "2. Compute relational distance" << std::endl;
    std::cout << "3. Update database information" << std::endl;
}

int main() {
    std::map<int, std::function<void()>> actions {
        {0, displayHelp},
        {1, exitProgram},
        {2, computeRelationalDistance},
        {3, updateDatabaseInformation}
    };

    std::cout << "Starting program..." << std::endl;

    int option = -1;

    showOptions();
    std::cout << "Please select an option: ";

    if (!(std::cin >> option)) {
        std::cin.clear();
        std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
        std::cout << "Invalid input. Please enter a number." << std::endl;
    }

    if (actions.find(option) != actions.end()) {
        if (option == 1) {
            actions[option]();
        } else {
            actions[option]();
        }
    } else {
        std::cout << "Invalid option. Please try again." << std::endl;
    }

    std::cout << "Finished program" << std::endl;
    return 0;
}
