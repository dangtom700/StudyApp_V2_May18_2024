rem Create a shared library in C++
g++ -shared -o tokenizer.dll src/shared.cpp -I./src -lm -l sqlite3 -std=c++17
if %errorlevel% neq 0 (
    echo Failed to create dll file
    goto :eof
)
echo Create dll file successful.