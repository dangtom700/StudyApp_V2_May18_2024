@echo off
setlocal enabledelayedexpansion

REM Menu options
echo Choose options (e.g., 2,3,4,6):
echo 1. --help
echo 2. --extractText
echo 3. --updateDatabase
echo 4. --searchTitle
echo 5. --getNoteReview
echo 6. --analyzeWordFreq
echo 7. --reorderMaterial
echo 8. --processWordFreq
echo 9. --precompVector
echo 10. --suggestTitle
echo 11. Run full command
set /p choices=Enter your choices (comma-separated): 

REM Initialize the command string
set cmd=python source/main.py

REM Loop through the selected choices and build the command
for %%i in (%choices%) do (
    if "%%i"=="1" set cmd=!cmd! --help
    if "%%i"=="2" set cmd=!cmd! --extractText
    if "%%i"=="3" set cmd=!cmd! --updateDatabase
    if "%%i"=="4" set cmd=!cmd! --searchTitle
    if "%%i"=="5" set cmd=!cmd! --getNoteReview
    if "%%i"=="6" set cmd=!cmd! --analyzeWordFreq
    if "%%i"=="7" set cmd=!cmd! --reorderMaterial
    if "%%i"=="8" set cmd=!cmd! --processWordFreq
    if "%%i"=="9" set cmd=!cmd! --precompVector
    if "%%i"=="10" set cmd=!cmd! --suggestTitle
    if "%%i"=="11" set cmd=!cmd! --extractText --updateDatabase --processWordFreq --analyzeWordFreq --precompVector --reorderMaterial
)

REM Confirm the command to be executed
echo Running: %cmd%

REM Get the start time
for /F "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /A startTimeInSeconds=(((%%a*3600) + (%%b*60) + %%c)*100 + %%d)
)

REM Run the constructed command
%cmd%

REM Get the end time
for /F "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /A endTimeInSeconds=(((%%a*3600) + (%%b*60) + %%c)*100 + %%d)
)

REM Calculate the elapsed time in milliseconds
set /A elapsedTime=endTimeInSeconds-startTimeInSeconds
set /A elapsedMilliseconds=elapsedTime %% 100
set /A elapsedTime=elapsedTime / 100
set /A elapsedSeconds=elapsedTime %% 60
set /A elapsedTime=elapsedTime / 60
set /A elapsedMinutes=elapsedTime %% 60
set /A elapsedHours=elapsedTime / 60

REM Display the elapsed time
echo Elapsed Time: %elapsedHours% hours, %elapsedMinutes% minutes, %elapsedSeconds% seconds, %elapsedMilliseconds% milliseconds

pause
endlocal
