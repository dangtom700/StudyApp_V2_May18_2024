#pragma once
#include "database_manager.hpp"
#include "book.hpp"
#include "borrower.hpp"
#include <string>
#include <vector>

class LibrarySystem {
public:
    LibrarySystem(const std::string& dbPath);

    bool addBook(const Book& book);
    bool registerBorrower(const Borrower& borrower);
    bool checkoutBook(const std::string& book_code, const std::string& borrower_phone);
    bool returnBook(const std::string& book_code);
    std::vector<Book> searchBooks(const std::string& search_query);
    Borrower getBorrowerInfo(const std::string& phone_number);

private:
    DatabaseManager db;
};
