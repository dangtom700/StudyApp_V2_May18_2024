#!/bin/bash

# Fail fast. Without this every stage ran unconditionally, so a run in which all of
# them failed still ended with "Program finished." and exit status 0.
set -euo pipefail
trap 'echo "Pipeline aborted - see the error above."; exit 1' ERR

# Every path on the C++ side resolves against the project root, so run from there no
# matter where this script was invoked from.
cd "$(dirname "$0")/.."

# Record start time
start_time=$(date +%s)

# Compile C++ code (Linux uses word_tokenizer without .exe)
if ! g++ -std=c++17 src/main.cpp -o word_tokenizer -I./src -lm -lsqlite3 -lssl -lcrypto -Wall -Werror; then
    echo "C++ compilation failed."
    exit 1
fi

# Every stage is off by default: the arguments decide what runs.
showComponents=0
# Content-level de-duplication. Off by default: it reads every incoming PDF and can
# move files. Run it deliberately -- main.sh --dedupePDF --dedupeDryRun -- first.
dedupePDF=0
dedupeArgs=""
renameFile=0
# Off by default: compression is slow, needs Ghostscript, and is lossy. Run it
# deliberately -- main.sh --compressPDF -- then run the pipeline as usual.
compressPDF=0
compressDryRun=""
pdfToText=0
extractText=0
updateDatabaseInformation=0
processWordFreq=0
computeRelationalDistance=0
computeTFIDF=0
runCutoffAnalysis=0
ideation=0
promptReference=0
fastMappingItemMatrix=0
mappingItemMatrix=0
topicTokenize=0
labelTopics=0
expandTopics=0
topicSimilarity=0
buildCatalog=0
# Read-only health check; never part of the end-to-end run.
dbDoctor=0

# With no arguments, run the standard end-to-end pipeline.
if [ $# -eq 0 ]; then
    echo "No stage selected - running the standard end-to-end pipeline."
    echo "Pass stage flags to run only those stages, e.g. main.sh --extractText --processWordFreq"
    echo ""
    pdfToText=1
    extractText=1
    updateDatabaseInformation=1
    processWordFreq=1
    computeRelationalDistance=1
    computeTFIDF=1
    fastMappingItemMatrix=1
    mappingItemMatrix=1
    topicTokenize=1
    labelTopics=1
    topicSimilarity=1
    buildCatalog=1
fi

# Process flags
for arg in "$@"; do
    case $arg in
        --showComponents) showComponents=1 ;;
        --dedupePDF) dedupePDF=1 ;;
        --dedupeSweep|--dedupeDryRun|--dedupeDelete|--dedupePreferIncoming|--dedupeStructural)
            dedupeArgs="$dedupeArgs $arg" ;;
        --renameFile) renameFile=1 ;;
        --compressPDF) compressPDF=1 ;;
        --compressDryRun) compressDryRun="--compressDryRun" ;;
        --pdfToText) pdfToText=1 ;;
        --extractText) extractText=1 ;;
        --updateDatabaseInformation) updateDatabaseInformation=1 ;;
        --processWordFreq) processWordFreq=1 ;;
        --computeRelationalDistance) computeRelationalDistance=1 ;;
        --computeTFIDF) computeTFIDF=1 ;;
        --runCutoffAnalysis) runCutoffAnalysis=1 ;;
        --ideation) ideation=1 ;;
        --promptReference) promptReference=1 ;;
        --fastMappingItemMatrix) fastMappingItemMatrix=1 ;;
        --mappingItemMatrix) mappingItemMatrix=1 ;;
        --topicTokenize) topicTokenize=1 ;;
        --labelTopics) labelTopics=1 ;;
        --expandTopics) expandTopics=1 ;;
        --topicSimilarity) topicSimilarity=1 ;;
        --buildCatalog) buildCatalog=1 ;;
        --dbDoctor) dbDoctor=1 ;;
        *)
            echo "Unknown option: $arg"
            echo "Use --showComponents to list the available stages."
            exit 1 ;;
    esac
done

if [ $showComponents -eq 1 ]; then
    python src/main.py --displayHelp
    ./word_tokenizer --displayHelp
fi

# Before --renameFile, while incoming files still carry their download names and so
# are still distinguishable from the library's <sha256>.pdf ones.
if [ $dedupePDF -eq 1 ]; then python src/main.py --dedupePDF $dedupeArgs; fi

if [ $renameFile -eq 1 ]; then python src/main.py --renameFile; fi

# In place, after --renameFile so each book keeps the hash name of the file as
# downloaded, before --pdfToText so the text comes from the files being kept.
if [ $compressPDF -eq 1 ]; then python src/main.py --compressPDF $compressDryRun; fi

if [ $pdfToText -eq 1 ]; then python src/main.py --pdfToText; fi
if [ $extractText -eq 1 ]; then python src/main.py --extractText; fi
if [ $updateDatabaseInformation -eq 1 ]; then ./word_tokenizer --updateDatabaseInformation; fi
if [ $processWordFreq -eq 1 ]; then python src/main.py --processWordFreq; fi
if [ $computeRelationalDistance -eq 1 ]; then ./word_tokenizer --computeRelationalDistance; fi
if [ $computeTFIDF -eq 1 ]; then ./word_tokenizer --computeTFIDF; fi
if [ $runCutoffAnalysis -eq 1 ]; then ./word_tokenizer --runCutoffAnalysis; fi
if [ $ideation -eq 1 ]; then python src/ideation.py; fi

if [ $promptReference -eq 1 ]; then
    python src/main.py --tokenizePrompt
    ./word_tokenizer --processPrompt
fi

if [ $fastMappingItemMatrix -eq 1 ]; then python src/main.py --computeItemMatrix; fi
if [ $mappingItemMatrix -eq 1 ]; then ./word_tokenizer --mappingItemMatrix; fi
if [ $topicTokenize -eq 1 ]; then python src/main.py --topicTokenize; fi
if [ $labelTopics -eq 1 ]; then ./word_tokenizer --labelTopics; fi
if [ $expandTopics -eq 1 ]; then ./word_tokenizer --expandTopics; fi
if [ $topicSimilarity -eq 1 ]; then ./word_tokenizer --topicSimilarity; fi

# Runs last: the catalog consumes the topic tags produced above.
if [ $buildCatalog -eq 1 ]; then python src/main.py --buildCatalog; fi

# Reports schema drift, orphaned rows and stale ids. Exits non-zero if it finds any.
if [ $dbDoctor -eq 1 ]; then python src/main.py --dbDoctor; fi

# Print elapsed time
end_time=$(date +%s)
elapsed=$(( end_time - start_time ))
echo "Total execution time: $(($elapsed / 3600)) hours $((($elapsed % 3600) / 60)) minutes $(($elapsed % 60)) seconds"
echo "Program finished."
