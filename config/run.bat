@echo off
rem Setting the start time for overall program execution
set start_time=%time%

rem Step 1: Compile the C++ code
echo Compiling C++ code...
g++ src/main.cpp src/lib/*.hpp -o word_tokenizer -I./src -lm -l sqlite3
if %errorlevel% neq 0 (
    echo C++ compilation failed.
    pause
    goto :eof
)
echo Compilation successful.

rem Function for showing the program description
:show_description
    echo.
    echo ==== Program Description ====
    echo This program is part of the study logging and database project.
    echo It has features implemented in both C++ and Python.
    echo.
    echo C++ Features:
    echo     1. Compute Relational Distance: Computes the Euclidean distance between tokens in a JSON file.
    echo     2. Update Database Information: Updates the database with resources such as PDFs.
    echo.
    echo Python Features:
    echo     3. Extract Text from PDF files: Extracts and stores text from PDFs in the database.
    echo     4. Process Word Frequencies: Analyzes word frequencies and creates index tables.
    echo     5. Find References in Database: Searches the database for references based on input prompts.
    echo.
    echo The program allows users to select and execute one or multiple features.
    echo ===============================
    echo.
    pause
    goto menu

rem Step 2: Display the options for the user
:menu
echo.
echo ==== Study Logging and Database Program ====
echo Choose an option to execute:
echo 1. Compute Relational Distance (C++)
echo 2. Update Database Information (C++)
echo 3. Extract Text from PDF files (Python)
echo 4. Process Word Frequencies (Python)
echo 5. Find References in Database (Python)
echo 6. Execute All Features
echo 7. Show Program Description
echo 0. Exit
echo ============================================
set /p choice=Enter your choice: 

rem Step 3: Execute the chosen option
if "%choice%" == "1" (
    echo Starting "Compute Relational Distance" using C++...
    word_tokenizer 2
    if %errorlevel% neq 0 (
        echo Error executing "Compute Relational Distance".
    ) else (
        echo "Compute Relational Distance" completed successfully.
    )
    goto menu
)
if "%choice%" == "2" (
    echo Starting "Update Database Information" using C++...
    word_tokenizer 3
    if %errorlevel% neq 0 (
        echo Error executing "Update Database Information".
    ) else (
        echo "Update Database Information" completed successfully.
    )
    goto menu
)
if "%choice%" == "3" (
    echo Starting "Extract Text from PDF files" using Python...
    python main.py --extractText
    if %errorlevel% neq 0 (
        echo Error executing "Extract Text from PDF files".
    ) else (
        echo "Extract Text from PDF files" completed successfully.
    )
    goto menu
)
if "%choice%" == "4" (
    echo Starting "Process Word Frequencies" using Python...
    python main.py --processWordFreq
    if %errorlevel% neq 0 (
        echo Error executing "Process Word Frequencies".
    ) else (
        echo "Process Word Frequencies" completed successfully.
    )
    goto menu
)
if "%choice%" == "5" (
    set /p prompt=Enter prompt for finding references: 
    echo Finding references using Python with prompt "%prompt%"...
    python main.py --promptFindingReference "%prompt%"
    if %errorlevel% neq 0 (
        echo Error executing "Find References in Database".
    ) else (
        echo "Find References in Database" completed successfully.
    )
    goto menu
)
if "%choice%" == "6" (
    echo Executing all features...
    word_tokenizer 2
    word_tokenizer 3
    python main.py --extractText
    python main.py --processWordFreq
    echo All features executed.
    goto menu
)
if "%choice%" == "7" (
    call :show_description
    goto menu
)
if "%choice%" == "0" (
    goto end
)

echo Invalid option. Please try again.
goto menu

:end
rem Calculate total execution time
call :print_time "Total execution time: " %start_time%
echo Program finished.
pause
goto :eof

rem Function to calculate and print elapsed time
:print_time
    setlocal enabledelayedexpansion
    set end_time=%time%
    rem Extract hours, minutes, and seconds from start and end time
    for /f "tokens=1-3 delims=:. " %%a in ("%2") do (
        set start_h=%%a
        set start_m=%%b
        set start_s=%%c
    )
    for /f "tokens=1-3 delims=:. " %%a in ("%end_time%") do (
        set end_h=%%a
        set end_m=%%b
        set end_s=%%c
    )

    rem Convert to seconds for easier calculation
    set /a start_total_seconds=(1%start_h%*3600 + 1%start_m%*60 + 1%start_s%) %% 86400
    set /a end_total_seconds=(1%end_h%*3600 + 1%end_m%*60 + 1%end_s%) %% 86400
    set /a elapsed_seconds=end_total_seconds - start_total_seconds

    if !elapsed_seconds! lss 0 (
        set /a elapsed_seconds+=86400
    )

    rem Calculate hours, minutes, and seconds from elapsed time
    set /a elapsed_h=elapsed_seconds / 3600
    set /a elapsed_m=(elapsed_seconds %% 3600) / 60
    set /a elapsed_s=elapsed_seconds %% 60

    echo %1 !elapsed_h! hours !elapsed_m! minutes !elapsed_s! seconds
    endlocal
    exit /b
