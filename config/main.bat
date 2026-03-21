@echo off
setlocal EnableDelayedExpansion

REM ========================================
REM Program Description
REM This program is part of the study logging and database project.
REM Run with command-line flags to select features.
REM ========================================

rem Record start time
set start_time=%time%

rem Compile C++ code
echo Compiling C++ code...
g++ src/main.cpp -o word_tokenizer -I./src -lm -lsqlite3 -lssl -lcrypto -Wall -Werror
if %errorlevel% neq 0 (
    echo [ERROR] C++ compilation failed.
    goto :eof
)

rem Activate Conda environment
call conda activate StudyAssistant

rem --- 1. SET DEFAULT CHECKPOINTS ---
set "run_showComponents=0"
set "run_renameFile=1"
set "run_extractText=1"
set "run_updateDatabaseInformation=1"
set "run_processWordFreq=1"
set "run_computeRelationalDistance=1"
set "run_computeTFIDF=1"
set "run_ideation=0"
set "run_promptReference=0"
set "run_mappingItemMatrix=1"
set "run_topicTokenize=1"
set "run_labelTopics=1"
set "run_expandTopics=0"

rem --- 2. DYNAMIC COMMAND LINE PARSER ---
:parse_args
if "%~1"=="" goto :execute_pipeline
set "arg=%~1"
if "%arg:~0,2%"=="--" (
    rem Extract string after -- and dynamically set flag to 1
    set "flag=%arg:~2%"
    set "run_!flag!=1"
)
shift
goto :parse_args

rem --- 3. PIPELINE EXECUTION ---
:execute_pipeline
echo.
echo ========================================
echo Starting Pipeline Execution
echo ========================================

if "!run_renameFile!"=="1" (
    echo [INFO] renameFile flag detected. Disabling all other tasks.
    call :run_step run_renameFile "Rename File" "python src/main.py --renameFile" || goto :end
    goto :end
)

rem Dual Command Checkpoints
if "!run_showComponents!"=="1" (
    echo [RUN] Show Components
    set "step_start=!time!"
    python src/main.py --displayHelp
    if !errorlevel! neq 0 goto :error_handler
    word_tokenizer --displayHelp
    if !errorlevel! neq 0 ( set "failed_step=Show Components" & goto :error_handler )
    call :print_time "[TIME] Show Components took:" "!step_start!"
)

if "!run_promptReference!"=="1" (
    echo [RUN] Finding Prompt References...
    set "step_start=!time!"
    python src/main.py --tokenizePrompt
    if !errorlevel! neq 0 ( set "failed_step=Prompt Reference" & goto :error_handler )
    word_tokenizer --processPrompt
    if !errorlevel! neq 0 ( set "failed_step=Prompt Reference" & goto :error_handler )
    call :print_time "[TIME] Finding Prompt References took:" "!step_start!"
)

rem Single Command Checkpoints via Subroutine
call :run_step run_extractText "Extract Text" "python src/main.py --extractText" || goto :end
call :run_step run_updateDatabaseInformation "Update Database Info" "word_tokenizer --updateDatabaseInformation" || goto :end
call :run_step run_processWordFreq "Process Word Freq" "python src/main.py --processWordFreq" || goto :end
call :run_step run_computeRelationalDistance "Compute Relational Dist" "word_tokenizer --computeRelationalDistance" || goto :end
call :run_step run_computeTFIDF "Compute TF-IDF" "word_tokenizer --computeTFIDF" || goto :end
call :run_step run_ideation "Ideation" "python src/ideation.py" || goto :end
call :run_step run_mappingItemMatrix "Mapping Item Matrix" "word_tokenizer --mappingItemMatrix" || goto :end
call :run_step run_topicTokenize "Topic Tokenize" "python src/main.py --topicTokenize" || goto :end
call :run_step run_labelTopics "Label Topics" "word_tokenizer --labelTopics" || goto :end
call :run_step run_expandTopics "Expand Topics" "word_tokenizer --expandTopics" || goto :end

:end
echo.
call :print_time "Total execution time: " "%start_time%"
echo Program finished.
endlocal
goto :eof

:error_handler
echo [ERROR] Pipeline failed at step: %failed_step%.
goto :end

REM ==============================================================================
REM Subroutines
REM ==============================================================================

:run_step
set "flag_var=%~1"
set "step_name=%~2"
set "command=%~3"

if "!%flag_var%!"=="1" (
    echo [RUN] %step_name%
    set "step_start=!time!"
    %command%
    if !errorlevel! neq 0 (
        echo [ERROR] Error executing %step_name%.
        exit /b 1
    )
    call :print_time "[TIME] %step_name% took:" "!step_start!"
)
exit /b 0

:print_time
    setlocal enabledelayedexpansion
    set end_time=%time%
    for /f "tokens=1-3 delims=:. " %%a in ("%~2") do (
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
    echo %~1 !elapsed_h! hours !elapsed_m! minutes !elapsed_s! seconds
    endlocal
    exit /b
