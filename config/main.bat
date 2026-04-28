@echo off

@REM Clear terminal
cls

rem Record start time
set start_time=%time%

rem Compile C++ code
g++ src/main.cpp -o word_tokenizer -I./src -lm -l sqlite3 -lssl -lcrypto -Wall -Werror
if %errorlevel% neq 0 (
    echo C++ compilation failed.
    goto :eof
)

rem Activate Conda environment
call conda activate StudyAssistant

rem Function to execute tasks based on flags
:execute_tasks

set "showComponents=0"
set "renameFile=0"
set "extractText=1"
set "updateDatabaseInformation=1"
set "processWordFreq=1"
set "computeRelationalDistance=1"
set "computeTFIDF=1"
set "runCutoffAnalysis=0"
set "ideation=0"
set "promptReference=0"
set "fastMappingItemMatrix=1"
set "mappingItemMatrix=1"
set "topicTokenize=1"
set "labelTopics=1"
set "expandTopics=0"
set "topicSimilarity=1"

rem Process flags
:process_flags
for %%A in (%*) do (
    if "%%A"=="--showComponents" set showComponents=1
    if "%%A"=="--renameFile" set renameFile=1
    if "%%A"=="--extractText" set extractText=1
    if "%%A"=="--updateDatabaseInformation" set updateDatabaseInformation=1
    if "%%A"=="--processWordFreq" set processWordFreq=1
    if "%%A"=="--computeRelationalDistance" set computeRelationalDistance=1
    if "%%A"=="--computeTFIDF" set computeTFIDF=1
    if "%%A"=="--runCutoffAnalysis" set runCutoffAnalysis=1
    if "%%A"=="--ideation" set ideation=1
    if "%%A"=="--promptReference" set promptReference=1
    if "%%A"=="--fastMappingItemMatrix" set fastMappingItemMatrix=1
    if "%%A"=="--mappingItemMatrix" set mappingItemMatrix=1
    if "%%A"=="--topicTokenize" set topicTokenize=1
    if "%%A"=="--labelTopics" set labelTopics=1
    if "%%A"=="--expandTopics" set expandTopics=1
    if "%%A"=="--topicSimilarity" set topicSimilarity=1
)

rem Show Components
if %showComponents%==1 (
    python src/main.py --displayHelp
    word_tokenizer --displayHelp
    if %errorlevel% neq 0 (
        echo Error executing Show Components.
        goto end
    )
)

rem Rename File
if %renameFile%==1 (
    python src/main.py --renameFile
    if %errorlevel% neq 0 (
        echo Error executing Rename File.
        goto end
    )
)

rem Extract Text
if %extractText%==1 (
    python src/main.py --extractText
    if %errorlevel% neq 0 (
        echo Error executing Extract Text from PDF files.
        goto end
    )
)

rem Update Database Information
if %updateDatabaseInformation%==1 (
    word_tokenizer --updateDatabaseInformation
    if %errorlevel% neq 0 (
        echo Error executing Update Database Information.
        goto end
    )
)

rem Process Word Frequencies
if %processWordFreq%==1 (
    python src/main.py --processWordFreq
    if %errorlevel% neq 0 (
        echo Error executing Process Word Frequencies.
        goto end
    )
)

rem Compute Relational Distance
if %computeRelationalDistance%==1 (
    word_tokenizer --computeRelationalDistance
    if %errorlevel% neq 0 (
        echo Error executing Compute Relational Distance.
        goto end
    )
)

rem Compute TF-IDF
if %computeTFIDF%==1 (
    word_tokenizer --computeTFIDF
    if %errorlevel% neq 0 (
        echo Error executing Computing TF-IDF.
        goto end
    )
)

rem Run Cutoff Analysis
if %runCutoffAnalysis%==1 (
    word_tokenizer --runCutoffAnalysis
    if %errorlevel% neq 0 (
        echo Error executing Cutoff Analysis.
        goto end
    )
)

rem Ideation
if %ideation%==1 (
    python src/ideation.py
    if %errorlevel% neq 0 (
        echo Error executing Ideation.
    )
)

rem Prompt Reference
if %promptReference%==1 (
    python src/main.py --tokenizePrompt
    word_tokenizer --processPrompt
    if %errorlevel% neq 0 (
        echo Error executing Find References in Database.
    )
)

rem Mapping Item Matrix (fast version)
if %fastMappingItemMatrix%==1 (
    python src/main.py --computeItemMatrix
    if %errorlevel% neq 0 (
        echo Error executing Mapping Item Matrix.
    )
)

rem Mapping Item Matrix
if %mappingItemMatrix%==1 (
    word_tokenizer --mappingItemMatrix
    if %errorlevel% neq 0 (
        echo Error executing Mapping Item Matrix.
    )
)

rem Topic Tokenize
if %topicTokenize%==1 (
    python src/main.py --topicTokenize
    if %errorlevel% neq 0 (
        echo Error executing Topic Tokenization.
    )
)

rem Label Topics
if %labelTopics%==1 (
    word_tokenizer --labelTopics
    if %errorlevel% neq 0 (
        echo Error executing Label Topics.
    )
)

rem Expand Topics
if %expandTopics%==1 (
    word_tokenizer --expandTopics
    if %errorlevel% neq 0 (
        echo Error executing Expand Topics.
    )
)

rem Topic Similarity
if %topicSimilarity%==1 (
    word_tokenizer --topicSimilarity
    if %errorlevel% neq 0 (
        echo Error executing Topic Similarity.
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