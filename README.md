# Study Assistant & PDF Library Manager

A comprehensive suite for managing, searching, and discovering insights from your PDF library. This project bridges a powerful Natural Language Processing (NLP) text-extraction pipeline (built in Python and C++) with an interactive Desktop Application (built in PyQt5) to facilitate advanced study tracking and semantic document recommendations.

## 🌟 Key Features

- **Advanced NLP Pipeline (C++ & Python)**: Heavy computation such as document text extraction, NLP tokenization, TF-IDF calculation, and relational distance computation is executed in an optimized C++ and Python pipeline. 
- **Docker-Ready Pipeline**: Full Linux support via Docker and Docker Compose, natively mapping Windows/Linux directories to containerized volumes.
- **Interactive Desktop App**: A comprehensive PyQt5 GUI (located in `app/`) for visually reading actual PDF pages, semantic content discovery, and performing full-text searches.
- **Semantic Search Engine**: Incorporates LangChain, LangGraph, Ollama, and a Chroma Vector Store for advanced semantic querying.
- **Smart Recommendations**: Uses Item Matrix calculations to provide serendipitous document discovery based on content dissimilarity.

## 🆕 Recent Updates (April 2026)

- **Semantic Vector Storage**: Direct database-to-vector-store ingestion in Python using ChromaDB, bypassing legacy text-splitting.
- **Local AI Integration**: Semantic queries powered by LangChain, LangGraph, and Ollama.
- **True PDF Rendering**: The GUI now renders actual PDF pages instead of raw text chunks, complete with an auto-fit split view.
- **Resilient NLP Pipelines**: The C++ topic modeling (`feature.hpp`) now supports robust resumption mechanisms to prevent redundant calculations during long batches.
- **Bidirectional Relational Queries**: Advanced SQL queries perfectly handle the "shrinking pool" item matrix logic for hyper-accurate document recommendations.

## 📂 Project Structure

- **`app/`**: Contains the PyQt5 desktop GUI application, dedicated setup scripts (`env.yml`, `run_app.bat`/`run_app.sh`), and App-specific documentation.
- **`src/`**: Houses the core C++ (`main.cpp`) and Python (`main.py`, `ideation.py`) scripts that extract text, tokenize, and train models.
- **`config/`**: Configuration scripts and execution orchestrators (`main.bat`, `main.sh`, `set_up.bat`).
- **`data/`, `wiki_topics/`, `docs/`**: Storage directories for sqlite3 files, processed chunks, topic mapping data, and documentation.

## 🛠️ Prerequisites

- **Python 3.7+**
- **Conda** (Anaconda or Miniconda)
- **C++ Compiler** (g++ via MinGW for Windows, standard `build-essential` for Linux)
- System Libraries: `sqlite3`, `openssl` (Linux requires `libsqlite3-dev` and `libssl-dev`)

## 🚀 Installation & Setup

### Windows

**1. Setup the Core NLP Pipeline**
Open your terminal and run the setup script to create the main Conda environment (`StudyAssistant`) and fetch dependencies:
```cmd
config\set_up.bat
```

**2. Setup the Desktop Application**
Change directories to the `app/` folder, create the UI-specific environment (`study_app_env`), and verify everything:
```cmd
cd app
conda env create -f env.yml
conda activate study_app_env
python verify_install.py
```

### Linux / Mac

**Option A: Deployment via Docker (Recommended for Pipeline)**
The project includes a robust Docker configuration to abstract system-level C++ & SQLite dependencies:
```bash
docker-compose up backend-processing -d
```
*(By default, this maps local directories defined in your `.env` or standard `D:\` drives directly into the container).*

**Option B: Native Setup**
1. Install OS build dependencies:
```bash
sudo apt-get update && sudo apt-get install -y g++ libsqlite3-dev libssl-dev
```
2. Setup and build the Pipeline environments:
```bash
conda env create -f src/env.yml
conda activate StudyAssistant
```
3. Setup the Desktop Application:
```bash
cd app
conda env create -f env.yml
conda activate study_app_env
```

## 🎮 Usage

The project functionalities are divided into two main components: running the background data pipeline, and interacting with the desktop viewer.

### 1. Running the Core Pipeline
Use the orchestrator scripts to process new PDFs, calculate word frequencies, or execute cutoff analyses. You can chain arguments easily!

**On Windows:**
```cmd
config\main.bat --extractText --processWordFreq --computeRelationalDistance
```

**On Linux:**
```bash
bash config/main.sh --extractText --processWordFreq --computeRelationalDistance
```

*Popular Flags:* 
- `--extractText`
- `--updateDatabaseInformation` 
- `--processWordFreq`
- `--computeTFIDF`
- `--promptReference`
*(Refer to `config/main.bat` or `main.sh` for the full list of supported flags).*

### 2. Using the Interactive Desktop App
Once your PDFs are extracted and processed, utilize the PyQt5 interface to browse your database.

**On Windows:**
```cmd
cd app
run_app.bat
```

**On Linux / Mac:**
```bash
cd app
bash run_app.sh
```

## 📚 Further Information

- **GUI App Operations**: Check out [app/APP_GUIDE.md](app/APP_GUIDE.md) and [app/QUICK_START.md](app/QUICK_START.md) to master the GUI's recommendation and full-text search tabs.
- **Archival Notes**: Check out `docs/README_archived.md` for previous legacy milestones.
