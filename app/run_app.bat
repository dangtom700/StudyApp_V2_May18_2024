@echo off
REM Study App Launcher
REM Create conda environment and launch the PyQt5 app

echo Creating conda environment...
@REM conda env create -f app/env.yml --yes

echo.
echo Activating environment and launching Study App...
call conda activate study_app_env
python app\pdf_app.py

pause