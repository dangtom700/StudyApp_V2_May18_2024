#ifndef ENV_HPP
#define ENV_HPP

#include <filesystem>
#include <cstdlib>

namespace ENV_HPP
{
    // Helper function to safely read environment variables with a fallback
    inline std::filesystem::path get_env_path(const char *var_name, const char *fallback)
    {
        if (const char *env_p = std::getenv(var_name))
        {
            return std::filesystem::path(env_p);
        }
        return std::filesystem::path(fallback);
    }

    // Use inline const to prevent Multiple Definition Linker Errors
    inline const std::filesystem::path resource_path = get_env_path("READING_LIST_PATH", "D:\\READING LIST");

    // Ideally, pass the executable path via argv[0] in main(), but current_path can work
    // IF you strictly guarantee you'll always run the terminal command from the project root.
    inline const std::filesystem::path data_root = std::filesystem::current_path() / "data";

    inline const std::filesystem::path json_path = data_root / "token_json";
    inline const std::filesystem::path database_path = data_root / "pdf_text.db";
    inline const std::filesystem::path output_path = data_root / "processed_data";
    inline const std::filesystem::path logging_path = data_root / "progress.log";
    inline const std::filesystem::path processed_data_path = data_root / "processed_data";
    inline const std::filesystem::path data_dumper_path = processed_data_path / "data_dumper.csv";
    inline const std::filesystem::path filtered_data_path = processed_data_path / "token_filter.csv";
    inline const std::filesystem::path data_info_path = processed_data_path / "data_info.csv";
    inline const std::filesystem::path buffer_json_path = data_root / "buffer.json";
    inline const std::filesystem::path global_terms_path = data_root / "global_word_freq.json";
    inline const std::filesystem::path outputPrompt = std::filesystem::current_path() / "outputPrompt.txt";
    inline const std::filesystem::path item_matrix = data_root / "item_matrix.csv";
    inline const std::filesystem::path route_list = data_root / "route_list.csv";
    inline const std::filesystem::path low_similarity_files = data_root / "low_similarity.txt";

    inline const int max_length = 18;
    inline const int min_value = 1;
}

#endif // ENV_HPP
