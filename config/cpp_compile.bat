@echo off
setlocal

REM Compile the program
g++ -o StudyLogDB src\main.cpp -l sqlite3

REM Get the start time
for /F "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /A startTimeInSeconds=%%a*3600 + %%b*60 + %%c
    set startMilliseconds=%%d
)

REM Run the constructed command
%cmd%

REM Get the end time
for /F "tokens=1-4 delims=:.," %%a in ("%time%") do (
    set /A endTimeInSeconds=%%a*3600 + %%b*60 + %%c
    set endMilliseconds=%%d
)

REM Calculate the elapsed time
set /A elapsedTime=endTimeInSeconds-startTimeInSeconds
set /A elapsedMilliseconds=endMilliseconds-startMilliseconds

REM Adjust milliseconds if necessary
if %elapsedMilliseconds% lss 0 (
    set /A elapsedMilliseconds+=100
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