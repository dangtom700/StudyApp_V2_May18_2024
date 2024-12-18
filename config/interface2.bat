rem Booting up the program
echo Compiling C++ code...
g++ src/interface1.cpp -o word_tokenizer -I./src -lm -l sqlite3
if %errorlevel% neq 0 (
    echo C++ compilation failed.
    goto :eof
)
echo Compilation successful.

rem Create a shared library in C++
g++ -shared -o tokenizer.dll src/shared.cpp -I./src -lm -l sqlite3 -std=c++17
if %errorlevel% neq 0 (
    echo Failed to create dll file
    goto :eof
)
echo Create dll file successful.