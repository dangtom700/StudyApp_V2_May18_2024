@echo off

REM ========================================
REM Program Description
REM This program is part of the study logging and database project.
REM It has features implemented in both C++ and Python.
REM 
REM C++ Features:
REM     1. --computeRelationalDistance
REM     2. --updateDatabaseInformation
REM     3. --mappingItemMatrix
REM 
REM Python Features:
REM     1. --extractText
REM     2. --processWordFreq
REM     3. --getDataset
REM 
REM Merged Feature:
REM     1. --promptReference
REM 
REM Run with command-line flags to select features.
REM ========================================

@REM rem Clear terminal
@REM cls

rem Record start time
set start_time=%time%

rem Compile C++ code
@REM g++ src/main.cpp -o word_tokenizer -I./src -lm -l sqlite3 -lssl -lcrypto -Wall -Werror
if %errorlevel% neq 0 (
    echo C++ compilation failed.
    goto :eof
)

rem Activate Conda environment
call conda activate StudyAssistant

rem Function to execute tasks based on flags
:execute_tasks

set "showComponents=0"
set "extractText=0"
set "updateDatabaseInformation=0"
set "processWordFreq=0"
set "computeTFIDF=0"
set "computeRelationalDistance=0"
set "ideation=0"
set "promptReference=1"

rem Process flags
:process_flags
for %%A in (%*) do (
    if "%%A"=="--showComponents" set showComponents=1
    if "%%A"=="--extractText" set extractText=1
    if "%%A"=="--updateDatabaseInformation" set updateDatabaseInformation=1
    if "%%A"=="--processWordFreq" set processWordFreq=1
    if "%%A"=="--computeTFIDF" set computeTFIDF=1
    if "%%A"=="--computeRelationalDistance" set computeRelationalDistance=1
    if "%%A"=="--ideation" set ideation=1
    if "%%A"=="--promptReference" set promptReference=1
)

rem Show Components
if %showComponents%==1 (
    python src/main.py --displayHelp
    word_tokenizer --displayHelp
    if %errorlevel% neq 0 (
        echo Error executing Show Components.
        goto end
    ) else (
        echo Show Components completed successfully.
    )
)

rem Extract Text
if %extractText%==1 (
    python src/main.py --extractText
    if %errorlevel% neq 0 (
        echo Error executing Extract Text from PDF files.
        goto end
    ) else (
        echo Extract Text from PDF files completed successfully.
    )
)

rem Update Database Information
if %updateDatabaseInformation%==1 (
    word_tokenizer --updateDatabaseInformation
    if %errorlevel% neq 0 (
        echo Error executing Update Database Information.
        goto end
    ) else (
        echo Update Database Information completed successfully.
    )
)

rem Process Word Frequencies
if %processWordFreq%==1 (
    python src/main.py --processWordFreq
    if %errorlevel% neq 0 (
        echo Error executing Process Word Frequencies.
        goto end
    ) else (
        echo Process Word Frequencies completed successfully.
    )
)

rem Compute TF-IDF
if %computeTFIDF%==1 (
    word_tokenizer --computeTFIDF
    if %errorlevel% neq 0 (
        echo Error executing Computing TF-IDF.
        goto end
    ) else (
        echo Computing TF-IDF completed successfully.
    )
)

rem Compute Relational Distance
if %computeRelationalDistance%==1 (
    word_tokenizer --computeRelationalDistance
    if %errorlevel% neq 0 (
        echo Error executing Compute Relational Distance.
        goto end
    ) else (
        echo Compute Relational Distance completed successfully.
    )
)

rem Ideation
if %ideation%==1 (
    python src/ideation.py
    if %errorlevel% neq 0 (
        echo Error executing Ideation.
    ) else (
        echo Ideation completed successfully.
    )
)

rem Prompt Reference
if %promptReference%==1 (
    python src/main.py --tokenizePrompt
    word_tokenizer --processPrompt
    if %errorlevel% neq 0 (
        echo Error executing Find References in Database.
    ) else (
        echo Find References in Database completed successfully.
    )
)

:end

rem Print elapsed time
call :print_time "Total execution time: " %start_time%
echo Program finished.
goto :eof

rem Function to calculate and print elapsed time
:print_time
    setlocal enabledelayedexpansion
    set end_time=%time%
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
    set /a start_total_seconds=(1%start_h%*3600 + 1%start_m%*60 + 1%start_s%) %% 86400
    set /a end_total_seconds=(1%end_h%*3600 + 1%end_m%*60 + 1%end_s%) %% 86400
    set /a elapsed_seconds=end_total_seconds - start_total_seconds
    if !elapsed_seconds! lss 0 (
        set /a elapsed_seconds+=86400
    )
    set /a elapsed_h=elapsed_seconds / 3600
    set /a elapsed_m=(elapsed_seconds %% 3600) / 60
    set /a elapsed_s=elapsed_seconds %% 60
    echo %1 !elapsed_h! hours !elapsed_m! minutes !elapsed_s! seconds
    endlocal
    exit /b
