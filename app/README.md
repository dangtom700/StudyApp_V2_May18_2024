# Study Assistant & Library Manager

> **Note:** This README contains information about the legacy/standalone app pipeline documentation. For the overarching project documentation, architecture, and complete setup instructions (including Docker and Linux support), please look at the **[Root README](../README.md)**.

## New Updates

In this new iteration, we have made significant architectural improvements and introduced new features:

- **Dynamic Pipeline Execution**: The `config\main.bat` orchestration script now cleanly accepts dynamic command-line arguments (e.g., `--extractText`, `--promptReference`), eliminating the need to manually edit the script to toggle features.
- **Execution Timers & Safeguards**: The pipeline now automatically tracks and logs the execution time of each scheduled checkpoint. We also added execution safeguards (like the `--renameFile` early exit) to streamline performance.
- **Interactive Library Manager**: Introduced a brand new C++ interactive Library Management application (located in `app/`) powered by SQLite3 to seamlessly manage book inventory, borrower registrations, and checkouts/returns.
- Beside extracting and processing raw text from PDF files, the program can tag and categorize different themes and topics of reading entries based on pre-trained data that is yielded from carefully interpretating the table of content and introduction of all reading entries and its associated tags (done manually).
- A new ability to comprehend the prompt based on both the present and the past prompt, applied with adjustable weight.

## Design Structures (Based on Functionalities)

> A sequential design paradigm

A. Preparation for software

1. Extract text from PDF
2. Process basic information about PDF files
3. Tokenize text chunks
4. Interprete token relations
5. Categorize based on preset tags

B. End user functionalities

1. Receive a new number of PDF title recommendation based on input prompt
2. Suggest a number of tags of topics and themes related to the input text
3. View information about reading entries and software training analytics

## Design Considerations

### User Interface

There are 2 options:

- Continuing on the terminal approach with pre-built commands
  - Pro: The commands can easily be implemented or removed
  - Con: The interface might be awkward when there are too many commands
  - Note: Required considerations on building atomic commands

- Support a new GUI for better use of the application
  - Pro: Better comprehension of what the application is about, easier to capture necessary information for users
  - Con: time-consuming to build, visual design elements must be considered when building application
  - Note: Consider about concurency when running different modules in background to provide information to the user in the GUI

Since the applicaiton is built using Python for interface with C++ wrapper for the critical parts. It is easier to add GUI in Python. Considerations for GUI in Python are:
- PyQT5
- Tkinter
- PyGUI
- Kivy
- Streamlit

Note: A migration to an language to improve memory safety and computation speed can be considered if needed.

### PDF Text Extraction

PDF text extraction oftentimes is the most time-consuming task in the software as the application is restricted by a single database storage. Multi-threading and distributed tasks are considered in the previous iteration. One thread processes one reading entry.

**An experiemental approach:** Multi-processing (using multiple CPU cores at the same time) to process each reading entry individually then insert into its own database. When the process is done, combined all information into a master database.

### Natural Language Processing

Trimming, filtering and tokenizing text chunks are the core of this software and must be handled properly.

With new updates, the software needs to be trained on labelled data. Every keyword or word of association with a tag is carafully observed and tested by multiple text mining techniques. This task may add to an overall longer preparation before the software can be used by the end users.

### Other considerations

- The software is computationally intensive, and it is slow for Python to handle the amount of calculation. An approach is to use C++ as a wrapper for these functions.
- Files communication. Find an approach to bind C++ into Python, considering "pybind11".
- Data analysis. Getting analytical information about the process of extracting and training the data in an informatic dashboard.
- Data management. Create a way to add in data instead of re-creating the whole database for every new incoming pdf file.

## Instructions

### Set up project

To set up the environment, this project requires C++ and Python:

- **Python**: Type in the terminal (this Python is run in a Conda environment):
  ```bat
  config\set_up
  ```
  This command will set up the Conda environment and download necessary items for natural language processing.

- **C++ Components**: 
  - Download the JSON library (`<nlohmann/json.hpp>`).
  - To compile the new interactive Library System, navigate to the `build` directory and run:
    ```bat
    cd build
    cmake ..
    cmake --build .
    ```

### Run Pipeline (`config\main.bat`)

The core data processing pipeline is managed by `config\main.bat`. Instead of manually editing the file to activate options like in previous versions, you can now pass flags directly via the command line!

There are 3 main phases of this program:
- **Extraction**: Extract raw text from PDF files in a designated folder. (To change the designated folder, modify `src\modules\path.py`).
  ```bat
  config\main.bat --extractText
  ```
- **Process and Encoding**: Automatically clean, digest, and encode tokens, then save them into the database.
  ```bat
  config\main.bat --updateDatabaseInformation --processWordFreq --computeRelationalDistance
  ```
- **User Queries**: Use the processed data by typing text into `prompt.txt`, then run:
  ```bat
  config\main.bat --promptReference
  ```
  The result can be seen in `outputPrompt.txt`.

*Note: You can chain multiple flags together (e.g., `config\main.bat --extractText --processWordFreq`), and the script will execute them sequentially, providing checkpoint specific runtime performance metrics at the end.*

### Run Library Manager

To interact with the distinct SQLite-powered library tracking system, simply execute the built binary:
```bat
.\build\LibraryManager.exe
```
This presents a CLI menu to add books, register borrowers, and query availability.
