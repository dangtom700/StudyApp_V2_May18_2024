#ifndef ENV_HPP
#define ENV_HPP

#include <filesystem>
#include <cstdlib>
#include <fstream>
#include <string>
#include <sstream>
#include <map>

namespace ENV_HPP
{
    // Helper function to read .env file with fallback
    inline std::map<std::string, std::string> load_env_file(const std::filesystem::path &env_file_path)
    {
        std::map<std::string, std::string> env_vars;
        std::ifstream env_file(env_file_path);

        if (!env_file.is_open())
        {
            return env_vars;
        }

        std::string line;
        while (std::getline(env_file, line))
        {
            // Skip empty lines and comments
            if (line.empty() || line[0] == '#')
                continue;

            // Find the '=' separator
            size_t pos = line.find('=');
            if (pos != std::string::npos)
            {
                std::string key = line.substr(0, pos);
                std::string value = line.substr(pos + 1);

                // Trim whitespace
                key.erase(0, key.find_first_not_of(" \t"));
                key.erase(key.find_last_not_of(" \t") + 1);
                value.erase(0, value.find_first_not_of(" \t"));
                value.erase(value.find_last_not_of(" \t") + 1);

                env_vars[key] = value;
            }
        }

        return env_vars;
    }

    // Helper function to safely read environment variables or .env file with fallback
    inline std::filesystem::path get_env_path(const char *var_name, const char *fallback, const std::map<std::string, std::string> &env_vars = {})
    {
        // First, check system environment variables
        if (const char *env_p = std::getenv(var_name))
        {
            return std::filesystem::path(env_p);
        }

        // Then, check loaded .env variables
        auto it = env_vars.find(var_name);
        if (it != env_vars.end())
        {
            return std::filesystem::path(it->second);
        }

        // Fall back to default
        return std::filesystem::path(fallback);
    }

    // Load .env variables once at the start of the program
    inline const std::map<std::string, std::string> env_vars = load_env_file(std::filesystem::current_path() / ".env");

    // Use inline const to prevent Multiple Definition Linker Errors
    inline const std::filesystem::path resource_path = get_env_path("READING_LIST_PATH", "pdfs", env_vars);

    // Ideally, pass the executable path via argv[0] in main(), but current_path can work
    // IF you strictly guarantee you'll always run the terminal command from the project root.
    inline const std::filesystem::path data_root = std::filesystem::current_path() / "data";

    inline const std::filesystem::path raw_data_path     = get_env_path("RAW_DATA_PATH",     (data_root / "raw_text").string().c_str(),     env_vars);
    inline const std::filesystem::path refined_data_path = get_env_path("REFINED_DATA_PATH",  (data_root / "refined_text").string().c_str(), env_vars);

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
    inline const std::filesystem::path processed_topics_buffer = data_root / "processed_topics.txt";

    inline const int max_length = 18;
    inline const int min_value = 1;
}

#endif // ENV_HPP
