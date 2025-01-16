@echo on
conda env create -f requirement.yml
conda activate StudyAssistant
pip install -r requirement.txt
python -m nltk.downloader punkt stopwords punkt_tab

pause