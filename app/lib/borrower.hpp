#pragma once

#include <string>
#include <map>
#include <time.h>

/* The borrower class has:
- name: the full name of the borrower
- address: where the user lives
- phone_number: a string of number (avoid the leading zero and the country code)
- borrowed_books: user can borrow many books at different time point
*/

class Borrower
{
public:
    std::string name;
    std::string address;
    std::string phone_number;
    std::map<std::string, time_t> borrowed_books;
};
