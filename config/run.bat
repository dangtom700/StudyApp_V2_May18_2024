@echo off
setlocal enabledelayedexpansion

REM Menu options
echo Choose options (e.g., 2,3,4,6):
echo 1. --help
echo 2. --extractText
echo 3. --updateDatabase
echo 4. --analyzeWordFreq
echo 5. --processWordFreq
echo 6. Run full command
set /p choices=Enter your choices (comma-separated): 

REM Initialize the command string and valid flag
set cmd=python src/main.py
set valid=true

REM Loop through the selected choices and build the command
for %%i in (%choices%) do (
    if "%%i"=="1" (
        set cmd=!cmd! --help
    ) else if "%%i"=="2" (
        set cmd=!cmd! --extractText
    ) else if "%%i"=="3" (
        set cmd=!cmd! --updateDatabase
    ) else if "%%i"=="4" (
        set cmd=!cmd! --analyzeWordFreq
    ) else if "%%i"=="5" (
        set cmd=!cmd! --processWordFreq
    ) else if "%%i"=="6" (
        set cmd=!cmd! --extractText --updateDatabase --processWordFreq --analyzeWordFreq
    ) else (
        echo Invalid choice: %%i
        set valid=false
    )
)

REM If there is an invalid choice, exit
if "%valid%"=="false" (
    echo One or more invalid choices were made. Exiting.
    pause
    endlocal
    exit /b 1
)

REM Confirm the command to be executed
echo Running: %cmd%

REM Get the start time
for /F "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /A startTimeInSeconds=1%%a*3600 + 1%%b*60 + 1%%c - 110000
    set startMilliseconds=%%d
)

REM Run the constructed command
%cmd%

REM Get the end time
for /F "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /A endTimeInSeconds=1%%a*3600 + 1%%b*60 + 1%%c - 110000
    set endMilliseconds=%%d
)

REM Calculate the elapsed time
set /A elapsedTime=endTimeInSeconds-startTimeInSeconds
set /A elapsedMilliseconds=endMilliseconds-startMilliseconds

REM Adjust milliseconds if necessary
if %elapsedMilliseconds% lss 0 (
    set /A elapsedMilliseconds+=1000
    set /A elapsedTime-=1
)

set /A elapsedSeconds=elapsedTime %% 60
set /A elapsedTime=elapsedTime / 60
set /A elapsedMinutes=elapsedTime %% 60
set /A elapsedHours=elapsedTime / 60

REM Display the elapsed time
echo Elapsed Time: %elapsedHours% hours, %elapsedMinutes% minutes, %elapsedSeconds% seconds, %elapsedMilliseconds% milliseconds

pause
endlocal
