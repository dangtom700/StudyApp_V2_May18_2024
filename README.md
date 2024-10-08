# Study Tracker

## CLI Application for Study Assistant

## Introduction

This project creates a CLI application that can keep track of my study progress through dashboards. The CLI application can be used for generating study dashboard and executing primary functions.

Note: This project has been re-purposed to prepare for data preparation for future intense number computation projects using different languages, such as C++ and Java

## Project Details

### Project Objectives

The aim of this project is to create:

- Study Engagement: Improve study habit and time management skills when learning new material. Stay on track with study activities.
- Document Retrieval: Improve study performance through retrieving old records of learning material. Storing effectively every learning material.
- Search Engine: A modern way to look up not just book titles and notes, but also text chunks and reading excerpts.
- Chat Bot: Text-based chat bot to perform certain tasks including request data tokens, retrieval of study materials and checking study progress.

### Scope and Deliverables

- The data and records are kept inside an Obsidian vault and used for collecting and retrieving data. Any data that is wanted to be executed has to be brought inside this vault.
- The intended result is a dashboard that can be used to track my learning progress and also a CLI application that can be used for generating study dashboards and executing primary functions.

### Methodology and Approach

- Obsidian vault for creating files and recording learning activities.
- Template files are stored in a template folder in the Obsidian vault to create semi-structured files, easier for collecting and retrieving data. Files included are study logging, study report, and study notes.
- CLI tool to perform pre-set tasks.

### Risk Assessment

- School work is the top priority, so this project can be delayed due to school work overload.
- Learning curve when building the application. The core functionalities can be handled in Python for prototyping. Lack of understanding and experience in Java and database management.
- Testing methodologies and strategies are not clear until the code is planned and built properly.

### Project Structure

There are 3 parts to this project:

1. The CLI application
2. The Obsidian vault
3. The template folder

## Further updates

For further updates, please prefer to the [interactive web page](doc\interactive.html) of this repository.

## References

- [Obsidian Manager](https://github.com/dangtom700/obsidian_manager)
- [Keyword Ranker](https://github.com/dangtom700/KeywordRanker)
- [Study Log](https://github.com/dangtom700/StudyLog)
- [Tag Studio](https://github.com/dangtom700/TagStudio)
- [CLI File Generator](https://github.com/dangtom700/CLI_File_Generator)
- [Study Assistant (Figma design)](https://www.figma.com/board/2t8iiGnpg0lOEtNSdyTOQr/Study-Assistance?node-id=0%3A1&t=g9lN4sPsgClpwuXx-1)
- [Text Extractor](https://github.com/dangtom700/extract_text)

## Instructions

Before starting the program, type into the terminal to install all necessary conda packages and external packages for Natural Language Processing. Also install C++ onto Windows computer through Mingw (MSYS2) as well as the nlohmann/json library for this project. There are numerous online tutorials to install C++ on Windows computers.

Navigate to both src/lib/env.hpp and src/modules/path.py. Paste the full address of the resource folder that will contains all the PDF files executed in this program to resource_path variable in env.hpp and pdf_path variable in path.py.

After installing all the packages and libraries, type into the terminal to set up the program.

```bash
config/set_up
```

After installtion, type into the terminal to start the program.

```bash
config/run
```

There are options to config in this program. Please change the number to 1 to enable the option.

```bash
set "extractText=0"
set "updateDatabaseInformation=0"
set "processWordFreq=0"
set "computeRelationalDistance=0"
set "promptReference=1"
```

As a result, the program will start to extract text from PDF files, update the database information, process word frequencies, and compute relational distance. There are constraints for the prompting, including
- The limit of the result is 25 entries or fewer depending on how many PDF files in a target resource folder
- Prompt is only accepted in the form of a paragraph
- This program is highly tailored to the resource folder that contains all PDF files and the English language for Natural Language Processing.
- This program is not intended to be used for other languages than English.
