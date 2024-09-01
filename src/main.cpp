// the main file is a basic C++ program that calls the other modules
#include "lib/env_var.hpp"
#include "lib/interface.hpp"
#include "lib/vec_com.hpp"
#include "lib/wor_frq.hpp"
#include "lib/search.hpp"
#include "lib/db.hpp"

#include<chrono>
#include<string>

const PATH path = ENV_VAR_HPP::PATH();

int main() {

    // INTERFACE_HPP::Greeting();
    // INTERFACE_HPP::Get_Request();
    DATABASE_HPP::initialize_database("data/pdf_db.db");
    
    return 0;
}