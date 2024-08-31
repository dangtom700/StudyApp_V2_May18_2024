// the main file is a basic C++ program that calls the other modules
#include "lib/env_var.hpp"
#include "lib/interface.hpp"
#include "lib/vec_com.hpp"
#include "lib/wor_frq.hpp"


#include<chrono>
#include<filesystem>
#include<string>

const std::string StudyApp_root_path = std::filesystem::current_path().string(); // get current working directory
const PATH path = ENV_VAR_HPP::PATH(StudyApp_root_path);

void fun_test(){
    int first = 1;
    int num_list[] = {1,2,3,4,5,6,7,8,9,10};
    for (int num : num_list) {
        std::cout << num << "\n";
        first += num;
        std::cout << first << "\n";
    }
}
int main() {
    std::chrono::time_point<std::chrono::system_clock> start_time = std::chrono::system_clock::now();

    // INTERFACE_HPP::Greeting();
    // INTERFACE_HPP::Get_Request();
    fun_test();

    INTERFACE_HPP::Print_Operating_Time(start_time);
    return 0;
}