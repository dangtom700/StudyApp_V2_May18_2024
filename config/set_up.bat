@echo on
conda env create -f requirement.yml
conda activate StudyAssistant
pip install -r requirement.txt
python nltk_download.py

pause