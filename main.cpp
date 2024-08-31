// the main file is a basic C++ program that calls the other modules
#include "lib/env_var.hpp"
#include "lib/interface.hpp"
#include "lib/vec_com.hpp"
#include "lib/wor_frq.hpp"

#include<chrono>

int main() {
    std::chrono::time_point<std::chrono::system_clock> start_time = std::chrono::system_clock::now();
    INTERFACE_HPP::Greeting();
    INTERFACE_HPP::Get_Request();
    INTERFACE_HPP::Print_Operating_Time(start_time);
    return 0;
}