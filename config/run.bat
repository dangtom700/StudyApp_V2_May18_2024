@echo off
rem Setting the start time for overall program execution
set start_time=%time%

rem Booting up the program
echo Compiling C++ code...
g++ src/main.cpp -o word_tokenizer -I./src -lm -l sqlite3
if %errorlevel% neq 0 (
    echo C++ compilation failed.
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
    echo     (Command: --computeRelationalDistance)
    echo     2. Update Database Information: Updates the database with resources such as PDFs.
    echo     (Command: --updateDatabaseInformation)
    echo.
    echo Python Features:
    echo     3. Extract Text from PDF files: Extracts and stores text from PDFs in the database.
    echo     (Command: --extractText)
    echo     4. Process Word Frequencies: Analyzes word frequencies and creates index tables.
    echo     (Command: --processWordFreq)
    echo.
    echo Merged Features:
    echo     5. Enter a paragraph styled prompt to search for references in the database.
    echo     (Command: --promptReference) Note: --tokenizePrompt (Python) --processPrompt (C++)
    echo.
    echo The program allows users to select and execute one or multiple features.
    echo ===============================
    echo.

rem Function to execute tasks based on input flags
:execute_tasks
echo Starting task execution...

set "extractText=0"
set "updateDatabaseInformation=0"
set "processWordFreq=0"
set "computeRelationalDistance=0"
set "promptReference=1"

rem Process flags
:process_flags
for %%A in (%*) do (
    if "%%A"=="--extractText" set extractText=1
    if "%%A"=="--updateDatabaseInformation" set updateDatabaseInformation=1
    if "%%A"=="--processWordFreq" set processWordFreq=1
    if "%%A"=="--computeRelationalDistance" set computeRelationalDistance=1
    if "%%A"=="--promptReference" set promptReference=1
    if "%%A"=="--showDescription" call :show_description
)

rem 1. Extract Text
if %extractText%==1 (
    echo Starting "Extract Text from PDF files" using Python...
    python src/main.py --extractText
    if %errorlevel% neq 0 (
        echo Error executing "Extract Text from PDF files".
        goto end
    ) else (
        echo "Extract Text from PDF files" completed successfully.
    )
)

rem 2. Update Database Information
if %updateDatabaseInformation%==1 (
    echo Starting "Update Database Information" using C++...
    word_tokenizer --updateDatabaseInformation
    if %errorlevel% neq 0 (
        echo Error executing "Update Database Information".
        goto end
    ) else (
        echo "Update Database Information" completed successfully.
    )
)

rem 3. Process Word Frequencies
if %processWordFreq%==1 (
    echo Starting "Process Word Frequencies" using Python...
    python src/main.py --processWordFreq
    if %errorlevel% neq 0 (
        echo Error executing "Process Word Frequencies".
        goto end
    ) else (
        echo "Process Word Frequencies" completed successfully.
    )
)

rem 4. Compute Relational Distance
if %computeRelationalDistance%==1 (
    echo Starting "Compute Relational Distance" using C++...
    word_tokenizer --computeRelationalDistance --createGlobalTerm
    if %errorlevel% neq 0 (
        echo Error executing "Compute Relational Distance".
        goto end
    ) else (
        echo "Compute Relational Distance" completed successfully.
    )
)

rem 5. Prompting for references
if %promptReference%==1 (
    echo Please Prompt Appropriately for Finding References
    python src/main.py --tokenizePrompt
    word_tokenizer --processPrompt
    if %errorlevel% neq 0 (
        echo Error executing "Find References in Database".
    ) else (
        echo "Find References in Database" completed successfully.
    )
)

:end

rem Calculate total execution time
call :print_time "Total execution time: " %start_time%
echo Program finished.

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
