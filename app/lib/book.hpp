#pragma once

#include <string>
#include <map>
#include <time.h>
#include <sqlite3.h>

/* Book class contains
- title: the name of the book
- code: hash value of the book (primary key and goto reference value for querying database)
- reader: name of user that borrow the book
- available date: the earliest date can be borrowed
*/

class Book
{
public:
    std::string title;
    std::string code;
    std::string reader;
    time_t available_date;
};
