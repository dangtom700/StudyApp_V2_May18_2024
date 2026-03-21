#include <iostream>

extern void test_database_manager();
extern void test_library_system();

int main() {
    std::cout << "Starting LibraryManager Tests..." << std::endl;

    std::cout << "\n--- Running DatabaseManager Tests ---" << std::endl;
    test_database_manager();

    std::cout << "\n--- Running LibrarySystem Tests ---" << std::endl;
    test_library_system();

    std::cout << "\nAll tests passed successfully!" << std::endl;
    return 0;
}
