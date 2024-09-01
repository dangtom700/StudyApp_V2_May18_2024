@echo off
conda activate StudyAssistant

if %ERRORLEVEL% neq 0 (
    echo activate shell successful
)else(
    echo activate shell failed
)
pause