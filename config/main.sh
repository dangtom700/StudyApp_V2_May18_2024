#!/bin/bash

# Record start time
start_time=$(date +%s)

# Compile C++ code (Linux uses word_tokenizer without .exe)
g++ src/main.cpp -o word_tokenizer -I./src -lm -lsqlite3 -lssl -lcrypto -Wall -Werror
if [ $? -ne 0 ]; then
    echo "C++ compilation failed."
    exit 1
fi

# Function to execute tasks based on flags
showComponents=0
renameFile=0
extractText=1
updateDatabaseInformation=1
processWordFreq=1
computeRelationalDistance=1
computeTFIDF=1
runCutoffAnalysis=0
ideation=0
promptReference=0
fastMappingItemMatrix=1
mappingItemMatrix=1
topicTokenize=1
labelTopics=1
expandTopics=0

# Process flags
for arg in "$@"; do
    case $arg in
        --showComponents) showComponents=1 ;;
        --renameFile) renameFile=1 ;;
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
    esac
done

if [ $showComponents -eq 1 ]; then
    python src/main.py --displayHelp
    ./word_tokenizer --displayHelp
fi

if [ $renameFile -eq 1 ]; then python src/main.py --renameFile; fi
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

# Print elapsed time
end_time=$(date +%s)
elapsed=$(( end_time - start_time ))
echo "Total execution time: $(($elapsed / 3600)) hours $((($elapsed % 3600) / 60)) minutes $(($elapsed % 60)) seconds"
echo "Program finished."
