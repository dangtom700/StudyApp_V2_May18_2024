#ifndef INTERFACE_HPP
#define INTERFACE_HPP
// libraries
#include <iostream>
#include <string>
#include <map>
#include <chrono>
#include <ctime>
#include <sstream>
#include <iomanip>
// constants
const std::map<int, std::string> REQUEST = {{1,"extract text"}, 
                                            {2,"update database"}, 
                                            {3,"process word frequency"}, 
                                            {4,"analyze word frequency"}, 
                                            {5,"precompute vector"}, 
                                            {6,"reorder material"}, 
                                            {7,"search title"}, 
                                            {8,"suggest title"}, 
                                            {9,"get note review"}};
// functions
void Greeting() {
    std::cout << "This is studyLogDB\n";
    std::cout << "Description: This project is to help store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.\n";
    std::cout << "Developed by: Apr 2023 until now\n";
}
void exit_program() {
    std::cout << "Thank you for using studyLogDB\n";
    exit(0);
}
void response(const std::string& message) {
    std:: cout << message << "\n";
}
void print_request_list(const std::map<int, std::string>& REQUEST = REQUEST) {
    std::cout << "Request list:\n";
    for (auto const& x : REQUEST) {
        std::cout << x.first << " - " << x.second << "\n";
    }
}
void Get_Request(const std::map<int, std::string>& REQUEST = REQUEST) {
    char is_request = 'n';
    std::cout << "Do you have any request?\nPress Y for yes and n for no: ";
    std::cin >> is_request;
    is_request == 'Y' or is_request == 'y' ? print_request_list() : exit_program();
    std::cout << "Enter your request: ";
    int request = 0;
    std::cin >> request;
    REQUEST.find(request) != REQUEST.end() ? response("Processing: " + REQUEST.at(request)) : exit_program();
}
void Print_Operating_Time(const std::chrono::time_point<std::chrono::system_clock>& start_time) {
    std::chrono::time_point<std::chrono::system_clock> current_time = std::chrono::system_clock::now();
    std::cout << "Operating time: " << std::chrono::duration_cast<std::chrono::seconds>(current_time - start_time).count() << " seconds\n";
}
std::string get_current_time(){
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&in_time_t), "%Y-%m-%d %X");
    return ss.str();
}
#endif // INTERFACE_HPP