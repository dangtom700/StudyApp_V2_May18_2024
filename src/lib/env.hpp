#ifndef ENV_HPP
#define ENV_HPP

#include <filesystem>
#include "utilities.hpp"

namespace ENV_HPP {
    std::filesystem::path data_root = std::filesystem::current_path().parent_path() / ("data");

    std::filesystem::path json_path = data_root / ("token_json");
    std::filesystem::path database_path = data_root / ("pdf_text.db");
    std::filesystem::path output_path = data_root / ("processed_data");
    std::filesystem::path logging_path = data_root / ("progress.log");

    const int max_length = 14;
    const int min_value = 3;
}

#endif // ENV_HPP
