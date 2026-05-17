@echo on

rem Create gitignored output directories required by the pipeline
if not exist data\processed_data mkdir data\processed_data
if not exist data\token_json     mkdir data\token_json
if not exist data\raw_text       mkdir data\raw_text
if not exist data\refined_text   mkdir data\refined_text
if not exist wiki_topics         mkdir wiki_topics
if not exist vector_db           mkdir vector_db

conda env create -f src\env.yml
python config\nltk_download.py

pause