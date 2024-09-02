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
std::map<int, std::string> collect_request(const std::string& request, const std::map<int, std::string>& REQUEST = REQUEST) {
    // format string into vector int
    std::vector<int> request_vector;
    std::stringstream ss(request);
    int request_int;
    while (ss >> request_int) {
        request_vector.push_back(request_int);
    }
    // check if request is valid
    for (auto const& x : request_vector) {
        if (REQUEST.find(x) == REQUEST.end()) {
            std::cout << "Invalid request\n";
            exit(0);
        }
    }
    // collect request
    std::map<int, std::string> request_map;
    for (auto const& x : request_vector) {
        request_map[x] = REQUEST.at(x);
    }
    return request_map;
}
std::map<int, std::string> Get_Request(const std::map<int, std::string>& REQUEST = REQUEST, char is_request = 'n') {
    std::cout << "Do you have any request?\nPress Y for yes and n for no: ";
    std::cin >> is_request;
    is_request == 'Y' or is_request == 'y' ? print_request_list() : exit_program();
    std::cout << "Please enter your request in comma separated format (e.g. 1,2): ";
    std::string request;
    std::cin >> request;
    return collect_request(request);
}

std::string get_current_time(){
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&in_time_t), "%Y-%m-%d %X");
    return ss.str();
}

void Coordinate_Request(const std::map<int, std::string>& collected_request){
    std::string base_response = "Processing request: ";
    for (auto const& x : collected_request) {
        switch (x.first) {
        case 1:
            response(base_response + x.second);
            // extract text
            break;
        case 2:
            response(base_response + x.second);
            // update database
            break;
        case 3:
            response(base_response + x.second);
            // process word frequency
            break;
        case 4:
            response(base_response + x.second);
            // analyze word frequency
            break;
        case 5:
            response(base_response + x.second);
            // precompute vector
            break;
        case 6:
            response(base_response + x.second);
            // reorder material
            break;
        }
    }
}
#endif // INTERFACE_HPP