# Study Tracker

![Favicon](https://th.bing.com/th/id/OIP.JBlEwFEGnOPhnB7JVqyHSwHaH_?pid=ImgDet&w=179&h=193&c=7&dpr=1.5)

## CLI Application for Study Assistant

## Introduction

This project creates a CLI application that can keep track of my study progress through dashboards. The CLI application can be used for generating study dashboard and executing primary functions.

## Project Details

### Project Objectives

The aim of this project is to create:

#### Study Engagement

![Study Engagement](https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdThmNGc2OG84bGpxaDF6Z3A0YnluZzVzNTJ3eHl3bWo5MzhnZ2x6MCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/KZBS6EjcaFB2BxwLVV/giphy.gif)
Improve study habit and time management skills when learning new material. Stay on track with study activities.

#### Document Retrieval

![Document Retrieval](https://media.giphy.com/media/KFH29iIiBK9DlgmZEY/giphy.gif?cid=790b7611u8f4g68o8ljqh1zgp4byng5s52wxywmj938gglz0&ep=v1_gifs_search&rid=giphy.gif&ct=g)
Improve study performance through retrieving old records of learning material. Storing effectively every learning material.

#### Search Engine

![Search Engine](https://media.giphy.com/media/cnFKWocUtPg0EXgWeJ/giphy.gif)
A modern way to look up not just book titles and notes, but also text chunks and reading excerpts.

#### Chat Bot

![Chat Bot](https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExc3Q3ZmduZ3pmanZkaG5pM3doaHBhOXZxdnlwc3d4dGptaDhmd2pzaiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/0lGd2OXXHe4tFhb7Wh/giphy.gif)
Text-based chat bot to perform certain tasks including request data tokens, retrieval of study materials and checking study progress.

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

### Timeline and Milestones

- **Apr 29th, 2024**: Documentation of project planning is created. New Obsidian vault is created for storing study material and study logging. Start learning habit to yield some raw data. BOOKS folder is a list of learning materials.
- **May 3rd, 2024**: The first prototype is done. Start applying project to the current workflow.
- **May 6th, 2024**: Revised the prototype and added more features.
- **May 7th, 2024**: Features are added. Start testing the prototype. Result is not satisfied. Update the terminology and refactor the code.
- **May 10th, 2024**: Restructure the project and start testing Natural Language Processing for keyword clusterizer.
- **May 17th, 2024**: Update on the architecture of the project.
- **May 19th, 2024**: Implement text extraction for keyword clusterizer.
- **May 23rd, 2024**: Update on the architecture of the project. Reset the environment for version 2's development. Manage dependencies issues.
- **May 25th, 2024**: Visioning an application that can search for related documents with a searching prompt with Vector Retrieval. Implement text extraction for keyword clusterizer.
- **May 27th, 2024**: Change in command lines and application structure. Prioritize the static content and searching method to finish the project.
- **May 29th, 2024**: Finish implementing static part of the project. Begin implementing vector retrieval for related keyword search.
- **June 6th, 2024**: Mass delay due to school work overload. A proposal for more managable task list generation is created.

### Current Skill Assessment

- SQL
- Python Programming
- Debugging
- Vector Retrieval
- Application Mapping
- Git Version Control
- Automation
- Web Development with HTML and CSS
- Problem-solving
- Data analysis

### Project Structure

There are 3 parts to this project:

1. The CLI application
2. The Obsidian vault
3. The template folder

#### CLI Application Structure

- **Automated Word Filter**: Collects the raw set of words from a file or a folder from the BOOKS folder that stores reading material in PDF format and the Study Note folder that stores study notes in Markdown format. There are 2 layers for filtering. The first layer is the pre-set rules for filtering. The second layer is the Natural Language Processing (for beta testing). The goal is to reduce the keywords that have to be searched for down to no more than 5. The filter word is then updated itself for readability and for better searching.
- **Note Tagging System**: Starts off by creating a list of words from a chosen note that is fed into the filter. The list is then used to calculate the keywords density and priority. Priority in this case is understood as representing a topic, a subject, a level heading, or a word in a paragraph. After the filter is done, there is a suggestion of 10 different keywords that can be chosen to append to the note. The note is then saved and execution is done. A similar mechanism is used when extracting the context of a book. By first extracting and splitting chunks of text, filtering the text, and then calculating the keywords density and implementing models to find suitable keywords. No limit on the number of keywords that can be extracted.
- **Book Title Tagging**: Starts off by creating a list of words, that were split from a BOOKS folder that feeds into the filter. After the filter is done, there is a suggestion of 10 different keywords that can be chosen to append to the note. The note is then saved and execution is done.

### Interactive Application Mapping

Below is the interactive application mapping of the project. Last updated on **May 22nd, 2024**. Content is not yet up-to-date.

``` html
<iframe style="border: 1px solid rgb(0, 0, 0);" width="100%" height="600" src="https://www.figma.com/embed?embed_host=share&url=https%3A%2F%2Fwww.figma.com%2Fboard%2F2t8iiGnpg0lOEtNSdyTOQr%2FStudy-Assistance%3Fnode-id%3D0%253A1%26t%3D0bfndQhaixxBi9YP-1" allowfullscreen></iframe>
```

## References

- [Obsidian Manager](https://github.com/dangtom700/obsidian_manager)
- [Keyword Ranker](https://github.com/dangtom700/KeywordRanker)
- [Study Log](https://github.com/dangtom700/StudyLog)
- [Tag Studio](https://github.com/dangtom700/TagStudio)
- [CLI File Generator](https://github.com/dangtom700/CLI_File_Generator)
- [Study Assistant (Figma design)](https://www.figma.com/board/2t8iiGnpg0lOEtNSdyTOQr/Study-Assistance?node-id=0%3A1&t=g9lN4sPsgClpwuXx-1)
- [Text Extractor](https://github.com/dangtom700/extract_text)
