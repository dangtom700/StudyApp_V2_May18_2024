@echo on
conda env create -f config\requirement.yml
conda activate StudyAssistant
pip install -r config\requirement.txt
python nltk_download.py

pause