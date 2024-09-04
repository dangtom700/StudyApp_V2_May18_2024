@echo on
conda env create -f requirements.yml
conda activate StudyAssistant
pip install -r requirements.txt

pause