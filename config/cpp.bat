REM compile the C++ program including the main.cpp and headers in lib folder
@echo on 
g++ src/main.cpp src/lib/*.hpp -o word_tokenizer -I./src -lm -l sqlite3
word_tokenizer