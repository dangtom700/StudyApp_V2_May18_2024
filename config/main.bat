@echo off

REM.
REM ==== Program Description ====
REM This program is part of the study logging and database project.
REM It has features implemented in both C++ and Python.
REM.
REM C++ Features:
REM     1. Compute Relational Distance: Computes the Euclidean distance between tokens in a JSON file.
REM     (Command: --computeRelationalDistance)
REM     2. Update Database Information: Updates the database with resources such as PDFs.
REM     (Command: --updateDatabaseInformation)
REM     3. Mapping item matrix of all items' relational distance
REM     (Command: --mappingItemMatrix)
REM.
REM Python Features:
REM     1. Extract Text from PDF files: Extracts and stores text from PDFs in the database.
REM     (Command: --extractText)
REM     2. Process Word Frequencies: Analyzes word frequencies and creates index tables.
REM     (Command: --processWordFreq)
REM.
REM Merged Features:
REM     1. Enter a paragraph styled prompt to search for references in the database.
REM     (Command: --promptReference) Note: --tokenizePrompt (Python) --processPrompt (C++)
REM.
REM The program allows users to select and execute one or multiple features.
REM ===============================
REM.

rem Clear terminal
cls

rem Setting the start time for overall program execution
set start_time=%time%

rem Booting up the program
echo Compiling C++ code...
g++ src/main.cpp -o word_tokenizer -I./src -lm -l sqlite3 -Wall -Werror
if %errorlevel% neq 0 (
    echo C++ compilation failed.
    goto :eof
)
echo Compilation successful.

rem Function to execute tasks based on input flags
:execute_tasks
echo Starting task execution...

set "showComponents=1"
set "extractText=0"
set "updateDatabaseInformation=0"
set "processWordFreq=0"
set "computeRelationalDistance=0"
set "mappingItemMatrix=0"
set "promptReference=0"

rem Process flags
:process_flags
for %%A in (%*) do (
    if "%%A"=="--showComponents" set showComponents=1
    if "%%A"=="--extractText" set extractText=1
    if "%%A"=="--updateDatabaseInformation" set updateDatabaseInformation=1
    if "%%A"=="--processWordFreq" set processWordFreq=1
    if "%%A"=="--computeRelationalDistance" set computeRelationalDistance=1
    if "%%A"=="--mappingItemMatrix" set mappingItemMatrix=1
    if "%%A"=="--promptReference" set promptReference=1
)

rem Show Components
if %showComponents%==1 (
    echo Showing Components...
    python src/main.py --displayHelp
    word_tokenizer --displayHelp
    if %errorlevel% neq 0 (
        echo Error executing "Show Components".
        goto end
    ) else (
        echo "Show Components" completed successfully.
    )
)

rem Extract Text
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

rem Update Database Information
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

rem Process Word Frequencies
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

rem Compute Relational Distance
if %computeRelationalDistance%==1 (
    echo Starting "Compute Relational Distance" using C++...
    word_tokenizer --computeRelationalDistance
    if %errorlevel% neq 0 (
        echo Error executing "Compute Relational Distance".
        goto end
    ) else (
        echo "Compute Relational Distance" completed successfully.
    )
)

rem Mapping Item Matrix of Relational Distance
if %mappingItemMatrix%==1 (
    echo Starting "Mapping Item Matrix" using C++...
    word_tokenizer --mappingItemMatrix
    if %errorlevel% neq 0 (
        echo Error executing "Mapping Item Matrix".
        goto end
    ) else (
        echo "Mapping Item Matrix" completed successfully.
    )
)

rem Prompting for references
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
