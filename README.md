# Study Tracker

This document is to introduce the project for more detail and update, refer to the interactive documentation in html the doc folder.

## Introduction

This project creates a CLI application that can keep track of my study progress through dashboards.

## Project Objectives

The aim of this project is to create:

- Study habit and time management skills when learning new material
- Improve study performance through retrieving old record of learning material
- A text-based chat bot with pre-built command lines to perform certain tasks such as look up what activities are done in a given date
- A search engine to look up for the keyword in related context

## Scope and Deliverables

The data and record are kept inside this Obsidian vault and used for collecting and retrieving data. Any data that is wanted to executed has to be brought inside this vault.

The intended result is a dashboard that can be used to track my learning progress and a CLI application that can be used for generating study dashboard and execute primary functions.

## Methodology and Approach

- Obsidian vault for creating files and record of learning activities
- Template files are store in template folder in Obsidian vault to create semi-structure files, easier for collecting and retrieving data. Files included are study logging, study report and study note
- CLI tool to perform pre-setted tasks

## Risk assessment

- School work is the top priority, so this project can be delayed due to school work overload
- Learning curve when building the application. The core and functionalities can be handled in Python for prototyping. Lack of understanding and experience in Java and database management
- Testing methodologies and strategies are not clear until the code is planned and built properly

## Timeline and Milestones

- Apr 29th, 2024. Documentation of project planning is created. New Obsidian vault is created for storing study material and study logging. Start learning habit to yield some raw data. BOOKS folder is list of learning material.
- May 3rd, 2024. The first prototype is done. Start applying project for the current workflow
- May 6th, 2024. Revised the prototype and add more features. Start adding more features
- May 7th, 2024. Features are added. Start testing the prototype. Result is not satisfied. Update the terminology and refactor the code
- May 10th, 2024. Restructure thee project and start testing Natural Language Processing for keyword clusterizer.
- May 17th, 2024. Update on the architecture of the project.
- May 19th, 2024. Implement text extraction for keyword clusterizer.

## Structure

The project structure is shown below. There are 3 parts to this project. The first part is the CLI application. The second part is the Obsidian vault. The third part is the template folder.

The CLI application's structure has 3 components. First is the Automated Word Filter. Second is the Note Tagging System. Third is the Book Title Tagging.

The automated word filter collect the raw set of words from a file or a folder from the BOOKS folder that store reading material in PDF format and Study Note folder that store study note in Markdown format. There are 2 layers for filtering.

The first layer is the presetted rules for filtering. The second layer is the Natural Language Processing (for beta testing). The goal is to reduce the keywords that has to search for down to no more than 5. The filter word is then update itself for readablity and for better searching.

The note tagging system also start off with create a list of word of a chosen note that feed into the filter. The list is then used to calculate the keywords density and priority.

Priority in this case is understand as that is representing as a topic, a subject, a level heading or a word in a paragraph.

After the filter is done, there is a suggestion of 10 different keywords that can be chosen to append into the note. The note is then saved and execution is done.

Similar mechanism is used when extracting context of a book. By first extract and split chunks of text, filter the text and then calculate the keywords density and implement models to find suitable keywords. No limit on the number of keywords that can be extracted.

The book title tagging system also start off with create a list of word, that was splitted from a BOOKS folder that feed into the filter. After the filter is done, there is a suggestion of 10 different keywords that can be chosen to append into the note. The note is then saved and execution is done.

## References

- [Obsidian Manager](https://github.com/dangtom700/obsidian_manager)
- [Keyword Ranker](https://github.com/dangtom700/KeywordRanker)
- [Study Log](https://github.com/dangtom700/StudyLog)
- [Tag Studio](https://github.com/dangtom700/TagStudio)
- [CLI File Generator](https://github.com/dangtom700/CLI_File_Generator)
- [Study Assistant](https://www.figma.com/board/2t8iiGnpg0lOEtNSdyTOQr/Study-Assistance?node-id=0%3A1&t=tTyT190h3s1lvM1c-1)
- [Text Extractor](https://github.com/dangtom700/extract_text)
