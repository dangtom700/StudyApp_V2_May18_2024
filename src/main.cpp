// the main file is a basic C++ program that calls the other modules
#include "lib/env_var.hpp"
#include "lib/interface.hpp"
#include "lib/vec_com.hpp"
#include "lib/wor_frq.hpp"
#include "lib/search.hpp"
// #include "lib/db.hpp"

#include<chrono>
#include<string>
#include<map>

const PATH path = ENV_VAR_HPP::PATH();

int main() {

    INTERFACE_HPP::Greeting();
    std::map <int, std::string> collected_request = INTERFACE_HPP::Get_Request();
    INTERFACE_HPP::Coordinate_Request(collected_request);
    
    return 0;
}