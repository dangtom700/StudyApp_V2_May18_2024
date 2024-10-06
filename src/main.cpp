#include <iostream>
#include <filesystem>
#include <vector>

#include "lib/feature.hpp"
#include "lib/env.hpp"
#include "lib/utilities.hpp"


void option0(void){ // Up and running, memory saved, optimized
    std::cout << "This program is created as an integrated part of the word tokenizer project\n" \
    "to compute the relational distance of each token in a given JSON file.\n" \
    "The relational distance is the Euclidean norm of the vector of token frequencies.\n" \
    "While Python provides a wide range of Natural Language Processing libraries,\n" \
    "Python is not so fast at number crunching and heavy data processing.\n" \
    "The C++ program is written to resolve this issue without using external libraries." << std::endl;
}

void option1(void){// Up and running, memory saved, optimized for data insertion speed and efficiency
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::json_path, false, ".json");

    std::cout << "Computing relational distance data..." << std::endl;
    FEATURE::computeRelationalDistance(filtered_files, false, true, true);
    std::cout << "Finished: Relational distance data computed" << std::endl;
}

void option2(void){// Not yet optimized
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::resource_path, false, ".pdf");

    std::cout << "Updating database information..." << std::endl;
    FEATURE::computeResourceData(filtered_files, true, true, true);
    std::cout << "Finished: Database information updated" << std::endl;
}

int main() {

    /*
    Starting the program with showing the functionality of the program
    Then show the options of the program with configurable choices
    */
    std::cout << "Starting program..." << std::endl;
    std::cout << "Options: " << std::endl;
    std::cout << "0. Help" << std::endl;
    std::cout << "1. Compute relational distance" << std::endl;
    std::cout << "2. Update database information" << std::endl;

    int option = 0;
    std::cout << "Please select an option: ";
    std::cin >> option;

    switch (option) {
        case 0:
            option0();
            break;
        case 1:
            option1();
            break;
        case 2:
            option2();
            break;
        default:
            std::cout << "Invalid option" << std::endl;
            break;
    }

    std::cout << "Finished program" << std::endl;

    return 0; // End of program
}
