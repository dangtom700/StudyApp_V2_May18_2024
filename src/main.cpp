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

const bool reset_table = false;
const bool show_progress = true;
const bool is_dumped = true;

void displayHelp()
{
    std::cout << "This program is created as an integrated part of the word tokenizer project "
                 "to compute the relational distance of each token in a given JSON file. "
                 "The relational distance is the Euclidean norm of the vector of token frequencies. "
                 "While Python provides a wide range of Natural Language Processing libraries, "
                 "C++ offers performance benefits for number crunching and heavy data processing. "
                 "This program resolves these issues without using external libraries."
              << std::endl;
}

void computeRelationalDistance()
{
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::json_path, false, ".json");

    if (filtered_files.empty())
    {
        std::cout << "No JSON files found in the specified directory." << std::endl;
        return;
    }
    if (!reset_table)
        filtered_files = FEATURE::skim_files(filtered_files, ".json");

    std::cout << "Computing relational distance data..." << std::endl;
    FEATURE::computeRelationalDistance(filtered_files, show_progress, reset_table, is_dumped);
    std::cout << "Finished: Relational distance data computed." << std::endl;
}

void updateDatabaseInformation()
{
    std::vector<std::filesystem::path> filtered_files = UTILITIES_HPP::Basic::extract_data_files(ENV_HPP::resource_path, false, ".pdf");

    if (filtered_files.empty())
    {
        std::cout << "No PDF files found in the specified directory." << std::endl;
        return;
    }

    // Deliberately not skimmed against file_info. Updating what is already recorded is
    // this stage's job: file_path, epoch_time and chunk_count are facts about the file as
    // it is now, and computeResourceData upserts them. Skipping known files is what let a
    // row keep chunk_count = 0 forever. Re-reading all of them costs one stat and one
    // indexed COUNT per file.
    std::cout << "Updating database information..." << std::endl;
    FEATURE::computeResourceData(filtered_files, show_progress, reset_table, is_dumped);
    std::cout << "Finished: Database information updated." << std::endl;
}

void processPrompt()
{
    std::cout << "Processing prompt..." << std::endl;
    FEATURE::processPrompt();
    std::cout << "Finished: Prompt processed." << std::endl;
}

void computeTFIDF()
{
    std::cout << "Computing TF-IDF..." << std::endl;
    FEATURE::computeTFIDF();
    std::cout << "Finished: TF-IDF computed." << std::endl;
}

void runCutoffAnalysis()
{
    std::cout << "Running cutoff analysis..." << std::endl;
    FEATURE::run_cutoff_analysis();
    std::cout << "Finished: Cutoff analysis completed." << std::endl;
}

void mappingItemMatrix()
{
    std::cout << "Mapping item matrix..." << std::endl;
    FEATURE::mappingItemMatrix(true, reset_table);
    std::cout << "Finished: Item matrix mapped." << std::endl;
}

void labelTopics()
{
    std::cout << "Labeling topics..." << std::endl;
    FEATURE::label_topics(true, reset_table);
    std::cout << "Finished: Topics labeled." << std::endl;
}

void expandTopics()
{
    std::cout << "Expanding topics..." << std::endl;
    FEATURE::iterative_topic_expansion(3, 0.5, 0.5, reset_table);
    std::cout << "Finished: Topics expanded." << std::endl;
}

void topicSimilarity()
{
    std::cout << "Computing topic similarity..." << std::endl;
    FEATURE::topicSimilarity(true, reset_table);
    std::cout << "Finished: Topic similarity computed." << std::endl;
}

int main(int argc, char *argv[])
{
    // Check if any command-line arguments were provided
    if (argc < 2)
    {
        std::cout << "No command provided. Use --displayHelp for available options." << std::endl;
        return 1;
    }

    UTILITIES_HPP::Basic::ensure_data_directories();

    // Map to store command-line options
    std::map<std::string, std::function<void()>> actions{
        {"--displayhelp", displayHelp},
        {"--computerelationaldistance", computeRelationalDistance},
        {"--updatedatabaseinformation", updateDatabaseInformation},
        {"--processprompt", processPrompt},
        {"--computetfidf", computeTFIDF},
        {"--runcutoffanalysis", runCutoffAnalysis},
        {"--mappingitemmatrix", mappingItemMatrix},
        {"--labeltopics", labelTopics},
        {"--expandtopics", expandTopics},
        {"--topicsimilarity", topicSimilarity}};

    // Iterate through the provided command-line arguments and execute corresponding actions
    for (int i = 1; i < argc; ++i)
    {
        std::string arg(argv[i]);
        std::transform(arg.begin(), arg.end(), arg.begin(), ::tolower); // Normalize to lowercase

        if (actions.find(arg) != actions.end())
        {
            // A stage that throws reports what failed and stops the run with a non-zero
            // status, which config/main.bat already checks. Letting the exception escape
            // main() instead aborts the process -- "terminate called after throwing an
            // instance of 'std::runtime_error'" with no indication of which stage died.
            try
            {
                actions[arg]();
            }
            catch (const std::exception &e)
            {
                std::cerr << "Stage " << arg << " failed: " << e.what() << std::endl;
                return 1;
            }
        }
        else
        {
            // Exit non-zero: a typo'd flag used to run no stage and still report success,
            // which reads exactly like a stage that had nothing to do.
            std::cerr << "Invalid option: " << arg << ". Use --displayHelp for available options." << std::endl;
            return 1;
        }
    }

    return 0;
}
