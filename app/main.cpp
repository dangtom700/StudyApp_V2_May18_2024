#include <iostream>
#include <string>
#include <ctime>
#include "library_system.hpp"

void printMenu() {
    std::cout << "\n=== Library Management System ===\n";
    std::cout << "1. Add a Book\n";
    std::cout << "2. Register a Borrower\n";
    std::cout << "3. Checkout a Book\n";
    std::cout << "4. Return a Book\n";
    std::cout << "5. Search Books\n";
    std::cout << "6. View Borrower Info\n";
    std::cout << "0. Exit\n";
    std::cout << "=================================\n";
    std::cout << "Enter your choice: ";
}

int main() {
    LibrarySystem lib("library.db");
    int choice;

    do {
        printMenu();
        if (!(std::cin >> choice)) {
            std::cin.clear();
            std::cin.ignore(10000, '\n');
            continue;
        }
        std::cin.ignore(10000, '\n'); // clear newline

        switch (choice) {
            case 1: {
                Book b;
                std::cout << "Enter Book Code: ";
                std::getline(std::cin, b.code);
                std::cout << "Enter Book Title: ";
                std::getline(std::cin, b.title);
                b.available_date = std::time(nullptr);
                if (lib.addBook(b)) std::cout << "Book added successfully!\n";
                break;
            }
            case 2: {
                Borrower b;
                std::cout << "Enter Phone Number: ";
                std::getline(std::cin, b.phone_number);
                std::cout << "Enter Name: ";
                std::getline(std::cin, b.name);
                std::cout << "Enter Address: ";
                std::getline(std::cin, b.address);
                if (lib.registerBorrower(b)) std::cout << "Borrower registered successfully!\n";
                break;
            }
            case 3: {
                std::string bookCode, phone;
                std::cout << "Enter Book Code: ";
                std::getline(std::cin, bookCode);
                std::cout << "Enter Borrower Phone: ";
                std::getline(std::cin, phone);
                if (lib.checkoutBook(bookCode, phone)) std::cout << "Checkout successful!\n";
                break;
            }
            case 4: {
                std::string bookCode;
                std::cout << "Enter Book Code to Return: ";
                std::getline(std::cin, bookCode);
                if (lib.returnBook(bookCode)) std::cout << "Return successful!\n";
                break;
            }
            case 5: {
                std::string query;
                std::cout << "Enter Search Query (Title): ";
                std::getline(std::cin, query);
                auto results = lib.searchBooks(query);
                std::cout << "Found " << results.size() << " books:\n";
                for (const auto& book : results) {
                    std::cout << "- [" << book.code << "] " << book.title 
                              << (book.reader.empty() ? " (Available)" : " (Checked out to " + book.reader + ")") << "\n";
                }
                break;
            }
            case 6: {
                std::string phone;
                std::cout << "Enter Borrower Phone: ";
                std::getline(std::cin, phone);
                Borrower b = lib.getBorrowerInfo(phone);
                if (b.name.empty()) {
                    std::cout << "Borrower not found.\n";
                } else {
                    std::cout << "Name: " << b.name << "\nAddress: " << b.address << "\n";
                    std::cout << "Borrowed Books:\n";
                    for (const auto& pair : b.borrowed_books) {
                        std::cout << "  - Book Code: " << pair.first << "\n";
                    }
                }
                break;
            }
            case 0:
                std::cout << "Exiting...\n";
                break;
            default:
                std::cout << "Invalid choice!\n";
        }
    } while (choice != 0);

    return 0;
}