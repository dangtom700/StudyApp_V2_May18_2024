#!/bin/bash
# Study App Launcher for Linux/Mac
# Create conda environment and launch the PyQt5 app
echo "Creating conda environment..."
conda env create -f app/env.yml --yes

echo ""
echo "Activating environment and launching Study App..."
conda activate study_app_env
python app/pdf_app.py