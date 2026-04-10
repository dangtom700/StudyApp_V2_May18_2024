@echo on
conda env create -f src\env.yml
python config\nltk_download.py

pause