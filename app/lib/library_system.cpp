#include "library_system.hpp"
#include <iostream>
#include <ctime>

LibrarySystem::LibrarySystem(const std::string& dbPath) : db(dbPath) {}

bool LibrarySystem::addBook(const Book& book) {
    std::string sql = "INSERT INTO Books (code, title, reader, available_date) VALUES ('" +
                      book.code + "', '" + book.title + "', '', " + std::to_string(book.available_date) + ");";
    return db.execute(sql);
}

bool LibrarySystem::registerBorrower(const Borrower& borrower) {
    std::string sql = "INSERT INTO Borrowers (phone_number, name, address) VALUES ('" +
                      borrower.phone_number + "', '" + borrower.name + "', '" + borrower.address + "');";
    return db.execute(sql);
}

bool LibrarySystem::checkoutBook(const std::string& book_code, const std::string& borrower_phone) {
    auto books = db.selectQuery("SELECT reader FROM Books WHERE code = '" + book_code + "';");
    if (books.empty()) {
        std::cerr << "Book not found.\n";
        return false;
    }
    if (!books[0]["reader"].empty()) {
        std::cerr << "Book is already checked out to " << books[0]["reader"] << ".\n";
        return false;
    }

    auto borrowers = db.selectQuery("SELECT name FROM Borrowers WHERE phone_number = '" + borrower_phone + "';");
    if (borrowers.empty()) {
        std::cerr << "Borrower not found.\n";
        return false;
    }

    time_t now = std::time(nullptr);
    std::string updateBook = "UPDATE Books SET reader = '" + borrower_phone + "' WHERE code = '" + book_code + "';";
    std::string insertTrans = "INSERT INTO Transactions (book_code, borrower_phone, borrow_date) VALUES ('" +
                              book_code + "', '" + borrower_phone + "', " + std::to_string(now) + ");";
    
    return db.execute(updateBook) && db.execute(insertTrans);
}

bool LibrarySystem::returnBook(const std::string& book_code) {
    auto books = db.selectQuery("SELECT reader FROM Books WHERE code = '" + book_code + "';");
    if (books.empty() || books[0]["reader"].empty()) {
        std::cerr << "Book not checked out or not found.\n";
        return false;
    }
    std::string borrowerPhone = books[0]["reader"];
    time_t now = std::time(nullptr);

    std::string updateBook = "UPDATE Books SET reader = '' WHERE code = '" + book_code + "';";
    std::string updateTrans = "UPDATE Transactions SET return_date = " + std::to_string(now) + 
                              " WHERE book_code = '" + book_code + "' AND return_date IS NULL;";

    return db.execute(updateBook) && db.execute(updateTrans);
}

std::vector<Book> LibrarySystem::searchBooks(const std::string& search_query) {
    std::vector<Book> res;
    std::string sql = "SELECT * FROM Books WHERE title LIKE '%" + search_query + "%';";
    auto results = db.selectQuery(sql);
    for (const auto& row : results) {
        Book b;
        b.code = row.at("code");
        b.title = row.at("title");
        b.reader = row.at("reader");
        b.available_date = row.at("available_date").empty() ? 0 : std::stoll(row.at("available_date"));
        res.push_back(b);
    }
    return res;
}

Borrower LibrarySystem::getBorrowerInfo(const std::string& phone_number) {
    Borrower b;
    std::string sql = "SELECT * FROM Borrowers WHERE phone_number = '" + phone_number + "';";
    auto results = db.selectQuery(sql);
    if (!results.empty()) {
        b.phone_number = results[0].at("phone_number");
        b.name = results[0].at("name");
        b.address = results[0].at("address");
    }
    
    std::string borrowedSql = "SELECT book_code, borrow_date FROM Transactions WHERE borrower_phone = '" + 
                              phone_number + "' AND return_date IS NULL;";
    auto borrowed = db.selectQuery(borrowedSql);
    for (const auto& row : borrowed) {
        b.borrowed_books[row.at("book_code")] = std::stoll(row.at("borrow_date"));
    }
    return b;
}
