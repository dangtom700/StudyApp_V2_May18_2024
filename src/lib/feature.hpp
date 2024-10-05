#ifndef FEATURE_HPP
#define FEATURE_HPP

#include <filesystem>
#include <vector>
#include <map>
#include <fstream>
#include <memory> // For smart pointers

#include "utilities.hpp"
#include "env.hpp"
#include "transform.hpp"

namespace FEATURE {
    /**
     * Compute the relational distance of each token in the given list of files.
     * The relational distance is the Euclidean norm of the vector of token frequencies.
     * The computed relational distances are stored in the data dumper file.
     *
     * @param filtered_files A vector of file paths to process.
     */
    void computeRelationalDistance(const std::vector<std::filesystem::path>& filtered_files) {
        try {
            bool trigger_once = true;
            for (const std::filesystem::path& file : filtered_files) {
                if (trigger_once) {
                    trigger_once = false;
                    UTILITIES_HPP::Basic::reset_data_dumper(ENV_HPP::data_dumper_path);
                }
                std::map<std::string,int> json_map = TRANSFORMER::json_to_map(file);

                DataEntry row = {
                    .path = file,
                    .sum = TRANSFORMER::compute_sum_token_json(json_map),
                    .num_unique_tokens = TRANSFORMER::count_unique_tokens(json_map),
                    .relational_distance = TRANSFORMER::Pythagoras(json_map),
                };

                row.filtered_tokens = TRANSFORMER::token_filter(json_map, ENV_HPP::max_length, ENV_HPP::min_value, row.relational_distance);
                UTILITIES_HPP::Basic::data_entry_dump(row);
            }
            std::cout << "Computing relational distance data finished" << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "Error: " << e.what() << std::endl;
        }        
    }
}

#endif // FEATURE_HPP