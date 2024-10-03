#ifndef TRANSFORMER
#define TRANSFORMER

#include <math.h>
#include <vector>
#include <math.h>
#include <map>
#include <filesystem>
#include <fstream>
#include <set>

#include "json.hpp"

using json = nlohmann::json;

namespace TRANSFORMER {

    /**
     * @brief Compute the sum of all token frequencies in a given JSON
     *        object
     * @param tokens The JSON object containing the token frequencies
     * @return The sum of all token frequencies
     */
    int compute_sum_token_json(const std::map<std::string, int>& tokens) {
        int result = 0;

        for (const auto& [key, value] : tokens) {
            result += value;
        }

        return result;
    }
    
    /**
     * @brief Compute the weight of a token based on its frequency in
     *        an excerpt and the whole database
     * @param individual The frequency of the token in the excerpt
     * @param whole The frequency of the token in the whole database
     * @param sum The total frequency of all tokens in the excerpt
     * @return The weight of the token
     */
    double compute_value(int& individual, int& whole, int& sum, std::string& token) {
        if (token.length() >= 14) {
            return 0;
        }
        double result = 1.0 / individual; // create indices
        result = (result < 0.0001) ? 0 : result*10; // elimiate very small numbers
        result *= result * whole/sum; // normalize to the excerpt
        result *= log(result); // normalize to the whole database
        return result;
    }

    /**
     * @brief Filter a set of tokens by maximum length and minimum frequency
     * @param tokens The set of tokens to filter
     * @param max_length The maximum length of tokens to include
     * @param min_value The minimum frequency of tokens to include
     * @return A set of tokens that meet the length and frequency criteria
     */
    std::map<std::string, int> token_filter(std::map<std::string, int>& tokens, const int& max_length, const int& min_value) {
        std::map<std::string, int> result;
        for (const auto& [key, value] : tokens) {
            if (key.length() <= max_length && value >= min_value) {
                result[key] = value;
            }
        }

        return result;
    }

    /**
     * @brief Get all unique tokens from a given JSON object
     * @param tokens The JSON object containing the token frequencies
     * @return A set of all unique tokens
     */
    std::set<std::string> unique_tokens(const std::map<std::string, int>& tokens) {
        std::set<std::string> result;

        for (const auto& [key, value] : tokens) {
            result.insert(key);
        }

        return result;
    }

    /**
     * @brief Count the number of unique tokens in a given JSON object
     * @param tokens The JSON object containing the token frequencies
     * @return The number of unique tokens
     */
    int count_unique_tokens(const std::map<std::string, int>& tokens) {
        return tokens.size();
    }

    /**
     * @brief Parse a given JSON file and return the contents as a map of strings to integers
     * @param json_file The path to the JSON file to parse
     * @return A map where the keys are the strings from the JSON file, and the values are the corresponding integers
     * @throws std::runtime_error If the JSON file could not be opened
     */
    std::map<std::string, int> json_to_map(const std::filesystem::path& json_file) {
        std::map<std::string, int> result;

        // Open the file
        std::ifstream file(json_file);
        if (!file.is_open()) {
            throw std::runtime_error("Could not open JSON file.");
        }

        // Parse the JSON
        json j;
        file >> j;

        // Iterate through the JSON and fill the map
        for (json::iterator it = j.begin(); it != j.end(); ++it) {
            result[it.key()] = it.value().get<int>();
        }

        return result;
    }

    /**
     * @brief Compute the Euclidean norm of the given map of strings to integers
     * @param tokens The map of strings to integers
     * @return The Euclidean norm of the given map
     */
    double Pythagoras(const std::map<std::string, int>& tokens) {
        double result = 0.0;
        for (const auto& [key, value] : tokens) {
            result += value*value;
        }
        return sqrt(result);
    }

}


#endif // TRANSFORMER