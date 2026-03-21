#include "library_system.hpp"
#include "book.hpp"
#include "borrower.hpp"
#include <cassert>
#include <iostream>
#include <filesystem>

void test_library_system() {
    std::string db_path = "test_library.sqlite";
    
    // Clean up before test
    if (std::filesystem::exists(db_path)) {
        std::filesystem::remove(db_path);
    }

    {
        LibrarySystem lib(db_path);

        // Test Add Book
        Book book;
        book.title = "The C++ Programming Language";
        book.code = "ISBN-12345";
        book.reader = "";
        book.available_date = 0; // Available immediately
        
        bool added = lib.addBook(book);
        assert(added && "Failed to add book");

        // Search the book
        auto found_books = lib.searchBooks("C++");
        assert(found_books.size() >= 1 && "Should find the added book");
        assert(found_books[0].title == "The C++ Programming Language" && "Book title mismatch");

        // Test Register Borrower
        Borrower b;
        b.name = "John Doe";
        b.address = "123 Main St";
        b.phone_number = "5551234567";
        
        bool registered = lib.registerBorrower(b);
        assert(registered && "Failed to register borrower");

        // Test Checkout Book
        bool checked_out = lib.checkoutBook("ISBN-12345", "5551234567");
        assert(checked_out && "Failed to checkout book");

        // Verify book status changed
        found_books = lib.searchBooks("C++");
        assert(found_books.size() >= 1 && "Should find the book by title");
        assert(found_books[0].reader == "5551234567" && "Book reader should be updated");

        // Find Borrower info
        Borrower info = lib.getBorrowerInfo("5551234567");
        assert(info.name == "John Doe" && "Borrower name mismatch");
        // Depending on implementation, borrower might have borrowed_books map populated.

        // Test Return Book
        bool returned = lib.returnBook("ISBN-12345");
        assert(returned && "Failed to return book");
        
        found_books = lib.searchBooks("C++");
        assert(found_books.size() >= 1 && "Should find the book by title");
        assert(found_books[0].reader == "" && "Book reader should be empty after return");
    }

    // Clean up after test
    if (std::filesystem::exists(db_path)) {
        std::filesystem::remove(db_path);
    }

    std::cout << "LibrarySystem tests passed." << std::endl;
}
