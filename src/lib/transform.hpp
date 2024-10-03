#ifndef TRANSFORMER
#define TRANSFORMER

#include <vector>
#include <map>
#include <filesystem>
#include <fstream>
#include <set>
#include <stdexcept>
#include <cmath>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

namespace TRANSFORMER {

    // Compute the sum of all token frequencies in a given JSON object
    int compute_sum_token_json(const std::map<std::string, int>& tokens) {
        int result = 0;
        for (const auto& [key, value] : tokens) {
            result += value;
        }
        return result;
    }

    // Compute the weight of a token based on its frequency
    double compute_value(int individual, int whole, int sum, const std::string& token) {
        if (token.length() >= 14) {
            return 0;
        }
        double result = 1.0 / individual; // create indices
        result = (result < 0.0001) ? 0 : result * 10; // eliminate very small numbers
        result *= result * whole / sum; // normalize to the excerpt
        result *= std::log(result); // normalize to the whole database
        return result;
    }

    // Filter a set of tokens by maximum length and minimum frequency
    std::map<std::string, int> token_filter(const std::map<std::string, int>& tokens, int max_length, int min_value) {
        std::map<std::string, int> result;
        for (const auto& [key, value] : tokens) {
            if (key.length() <= max_length && value >= min_value) {
                result[key] = value;
            }
        }
        return result;
    }

    // Count the number of unique tokens in a given JSON object
    int count_unique_tokens(const std::map<std::string, int>& tokens) {
        return tokens.size();
    }

    // Parse a given JSON file and return the contents as a map
    std::map<std::string, int> json_to_map(const std::filesystem::path& json_file) {
        std::map<std::string, int> result;
        std::ifstream file(json_file);
        if (!file.is_open()) {
            throw std::runtime_error("Could not open JSON file: " + json_file.string());
        }

        json j;
        file >> j;

        for (auto it = j.begin(); it != j.end(); ++it) {
            result[it.key()] = it.value().get<int>();
        }

        return result;
    }

    // Compute the Euclidean norm of the given map of strings to integers
    double Pythagoras(const std::map<std::string, int>& tokens) {
        double result = 0.0;
        for (const auto& [key, value] : tokens) {
            result += value * value;
        }
        return std::sqrt(result);
    }

} // namespace TRANSFORMER

#endif // TRANSFORMER
