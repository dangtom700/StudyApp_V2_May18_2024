@echo off

rem Delayed expansion is required for the errorlevel checks below: cmd expands
rem %VAR% when it PARSES a parenthesised block, so a guard written as %errorlevel%
rem inside "if ... ( ... )" tests the exit code from before the stage ran.
setlocal enabledelayedexpansion

rem word_tokenizer needs the MSYS2 ucrt64 DLLs (libsqlite3-0, libcrypto-3-x64,
rem libstdc++-6, libgcc_s_seh-1) on PATH; without them it exits 127 silently.
rem Every path on the C++ side resolves against the project root, so run from there
rem no matter where this script was invoked from.
pushd "%~dp0.."

@REM Clear terminal
cls

rem Record start time
set start_time=%time%

rem Compile C++ code
g++ -std=c++17 src/main.cpp -o word_tokenizer -I./src -lm -l sqlite3 -lssl -lcrypto -Wall -Werror
if %errorlevel% neq 0 (
    echo C++ compilation failed.
    popd
    exit /b 1
)

rem Activate Conda environment
call conda activate StudyAssistant

rem Function to execute tasks based on flags
:execute_tasks

rem Every stage is off by default: the arguments decide what runs.
rem Every stage is off by default: the arguments decide what runs. These were
rem previously initialised to 1, which made "main.bat --oneStage" silently run the
rem whole pipeline instead of that one stage. The no-argument block below is what
rem turns the standard end-to-end run back on, so plain "main.bat" is unchanged.
set "showComponents=0"
rem Content-level de-duplication. Off by default: it reads every incoming PDF and
rem can move files. Invoke it deliberately: main.bat --dedupePDF --dedupeDryRun
rem Each modifier gets its own variable rather than one accumulated string --
rem appending inside the flag loop below would need delayed expansion, which the
rem loop does not enable.
set "dedupePDF=0"
set "dedupeSweep="
set "dedupeDryRun="
set "dedupeDelete="
set "dedupePreferIncoming="
set "dedupeStructural="
set "renameFile=0"
rem Compression is slow, needs Ghostscript, and is lossy, so it stays out of the
rem end-to-end run. Invoke it deliberately: main.bat --compressPDF
set "compressPDF=0"
set "compressDryRun="
set "pdfToText=0"
set "extractText=0"
set "updateDatabaseInformation=0"
set "processWordFreq=0"
set "computeRelationalDistance=0"
set "computeTFIDF=0"
set "runCutoffAnalysis=0"
set "ideation=0"
set "promptReference=0"
set "fastMappingItemMatrix=0"
set "mappingItemMatrix=0"
set "topicTokenize=0"
set "labelTopics=0"
set "expandTopics=0"
set "topicSimilarity=0"
set "buildCatalog=0"
rem Read-only health check against config/schema.sql. Never part of the end-to-end run.
set "dbDoctor=0"

rem With no arguments, run the standard end-to-end pipeline.
if "%~1"=="" (
    echo No stage selected - running the standard end-to-end pipeline.
    echo Pass stage flags to run only those stages, e.g. main.bat --extractText --processWordFreq
    echo.
    rem renameFile and promptReference are listed explicitly so the no-argument run
    rem stays exactly what it was before the defaults above were corrected to 0.
    set "renameFile=1"
    set "promptReference=1"
    set "pdfToText=1"
    set "extractText=1"
    set "updateDatabaseInformation=1"
    set "processWordFreq=1"
    set "computeRelationalDistance=1"
    set "computeTFIDF=1"
    set "fastMappingItemMatrix=1"
    set "mappingItemMatrix=1"
    set "topicTokenize=1"
    set "labelTopics=1"
    set "topicSimilarity=1"
    set "buildCatalog=1"
)

rem Process flags
:process_flags
rem An unrecognised flag used to match nothing, run no stage, and still report
rem success - indistinguishable from a stage that had nothing to do.
set "knownFlags= --showComponents --dedupePDF --dedupeSweep --dedupeDryRun --dedupeDelete --dedupePreferIncoming --dedupeStructural --renameFile --compressPDF --compressDryRun --pdfToText --extractText --updateDatabaseInformation --processWordFreq --computeRelationalDistance --computeTFIDF --runCutoffAnalysis --ideation --promptReference --fastMappingItemMatrix --mappingItemMatrix --topicTokenize --labelTopics --expandTopics --topicSimilarity --buildCatalog --dbDoctor "
for %%A in (%*) do (
    echo !knownFlags! | findstr /C:" %%A " >nul
    if errorlevel 1 (
        echo Unknown option: %%A
        echo Use --showComponents to list the available stages.
        popd
        exit /b 1
    )
)

for %%A in (%*) do (
    if "%%A"=="--showComponents" set showComponents=1
    if "%%A"=="--dedupePDF" set dedupePDF=1
    if "%%A"=="--dedupeSweep" set dedupeSweep=--dedupeSweep
    if "%%A"=="--dedupeDryRun" set dedupeDryRun=--dedupeDryRun
    if "%%A"=="--dedupeDelete" set dedupeDelete=--dedupeDelete
    if "%%A"=="--dedupePreferIncoming" set dedupePreferIncoming=--dedupePreferIncoming
    if "%%A"=="--dedupeStructural" set dedupeStructural=--dedupeStructural
    if "%%A"=="--renameFile" set renameFile=1
    if "%%A"=="--compressPDF" set compressPDF=1
    if "%%A"=="--compressDryRun" set compressDryRun=--compressDryRun
    if "%%A"=="--pdfToText" set pdfToText=1
    if "%%A"=="--extractText" set extractText=1
    if "%%A"=="--updateDatabaseInformation" set updateDatabaseInformation=1
    if "%%A"=="--processWordFreq" set processWordFreq=1
    if "%%A"=="--computeRelationalDistance" set computeRelationalDistance=1
    if "%%A"=="--computeTFIDF" set computeTFIDF=1
    if "%%A"=="--runCutoffAnalysis" set runCutoffAnalysis=1
    if "%%A"=="--ideation" set ideation=1
    if "%%A"=="--promptReference" set promptReference=1
    if "%%A"=="--fastMappingItemMatrix" set fastMappingItemMatrix=1
    if "%%A"=="--mappingItemMatrix" set mappingItemMatrix=1
    if "%%A"=="--topicTokenize" set topicTokenize=1
    if "%%A"=="--labelTopics" set labelTopics=1
    if "%%A"=="--expandTopics" set expandTopics=1
    if "%%A"=="--topicSimilarity" set topicSimilarity=1
    if "%%A"=="--buildCatalog" set buildCatalog=1
    if "%%A"=="--dbDoctor" set dbDoctor=1
)

rem Show Components
if %showComponents%==1 (
    python src/main.py --displayHelp
    word_tokenizer --displayHelp
    if !errorlevel! neq 0 (
        echo Error executing Show Components.
        set "pipelineFailed=1"
        goto end
    )
)

rem Deduplicate PDFs by content - before Rename File, while incoming files still
rem carry their download names and so are still distinguishable from the library.
if %dedupePDF%==1 (
    python src/main.py --dedupePDF %dedupeSweep% %dedupeDryRun% %dedupeDelete% %dedupePreferIncoming% %dedupeStructural%
    if !errorlevel! neq 0 (
        echo Error deduplicating PDFs.
        set "pipelineFailed=1"
        goto end
    )
)

rem Rename File
if %renameFile%==1 (
    python src/main.py --renameFile
    if !errorlevel! neq 0 (
        echo Error executing Rename File.
        set "pipelineFailed=1"
        goto end
    )
)

rem Compress PDFs in place - after Rename File so each book keeps the hash name of
rem the file as downloaded, before PDF to TXT so the text comes from the kept files.
if %compressPDF%==1 (
    python src/main.py --compressPDF %compressDryRun%
    if !errorlevel! neq 0 (
        echo Error compressing PDFs.
        set "pipelineFailed=1"
        goto end
    )
)

rem PDF to TXT
if %pdfToText%==1 (
    python src/main.py --pdfToText
    if !errorlevel! neq 0 (
        echo Error converting PDFs to text files.
        set "pipelineFailed=1"
        goto end
    )
)

rem Extract Text
if %extractText%==1 (
    python src/main.py --extractText
    if !errorlevel! neq 0 (
        echo Error executing Extract Text from PDF files.
        set "pipelineFailed=1"
        goto end
    )
)

rem Update Database Information
if %updateDatabaseInformation%==1 (
    word_tokenizer --updateDatabaseInformation
    if !errorlevel! neq 0 (
        echo Error executing Update Database Information.
        set "pipelineFailed=1"
        goto end
    )
)

rem Process Word Frequencies
if %processWordFreq%==1 (
    python src/main.py --processWordFreq
    if !errorlevel! neq 0 (
        echo Error executing Process Word Frequencies.
        set "pipelineFailed=1"
        goto end
    )
)

rem Compute Relational Distance
if %computeRelationalDistance%==1 (
    word_tokenizer --computeRelationalDistance
    if !errorlevel! neq 0 (
        echo Error executing Compute Relational Distance.
        set "pipelineFailed=1"
        goto end
    )
)

rem Compute TF-IDF
if %computeTFIDF%==1 (
    word_tokenizer --computeTFIDF
    if !errorlevel! neq 0 (
        echo Error executing Computing TF-IDF.
        set "pipelineFailed=1"
        goto end
    )
)

rem Run Cutoff Analysis
if %runCutoffAnalysis%==1 (
    word_tokenizer --runCutoffAnalysis
    if !errorlevel! neq 0 (
        echo Error executing Cutoff Analysis.
        set "pipelineFailed=1"
        goto end
    )
)

rem Ideation
if %ideation%==1 (
    python src/ideation.py
    if !errorlevel! neq 0 (
        echo Error executing Ideation.
        set "pipelineFailed=1"
    )
)

rem Prompt Reference
if %promptReference%==1 (
    python src/main.py --tokenizePrompt
    word_tokenizer --processPrompt
    if !errorlevel! neq 0 (
        echo Error executing Find References in Database.
        set "pipelineFailed=1"
    )
)

rem Mapping Item Matrix (fast version)
if %fastMappingItemMatrix%==1 (
    python src/main.py --computeItemMatrix
    if !errorlevel! neq 0 (
        echo Error executing Mapping Item Matrix.
        set "pipelineFailed=1"
    )
)

rem Mapping Item Matrix
if %mappingItemMatrix%==1 (
    word_tokenizer --mappingItemMatrix
    if !errorlevel! neq 0 (
        echo Error executing Mapping Item Matrix.
        set "pipelineFailed=1"
    )
)

rem Topic Tokenize
if %topicTokenize%==1 (
    python src/main.py --topicTokenize
    if !errorlevel! neq 0 (
        echo Error executing Topic Tokenization.
        set "pipelineFailed=1"
    )
)

rem Label Topics
if %labelTopics%==1 (
    word_tokenizer --labelTopics
    if !errorlevel! neq 0 (
        echo Error executing Label Topics.
        set "pipelineFailed=1"
    )
)

rem Expand Topics
if %expandTopics%==1 (
    word_tokenizer --expandTopics
    if !errorlevel! neq 0 (
        echo Error executing Expand Topics.
        set "pipelineFailed=1"
    )
)

rem Topic Similarity
if %topicSimilarity%==1 (
    word_tokenizer --topicSimilarity
    if !errorlevel! neq 0 (
        echo Error executing Topic Similarity.
        set "pipelineFailed=1"
    )
)

rem Build Catalog - runs last, it consumes the topic tags produced above
if %buildCatalog%==1 (
    python src/main.py --buildCatalog
    if !errorlevel! neq 0 (
        echo Error executing Build Catalog.
        set "pipelineFailed=1"
    )
)

rem Database doctor - schema drift, orphaned rows, stale ids. Read-only; exits
rem non-zero when it finds something, so it reports rather than echoes.
if %dbDoctor%==1 (
    python src/main.py --dbDoctor
    if !errorlevel! neq 0 (
        echo Database check reported problems - see above.
        set "pipelineFailed=1"
    )
)

:end

popd

rem Print elapsed time
call :print_time "Total execution time: " %start_time%
if defined pipelineFailed (
    echo Pipeline finished with errors - see above.
    exit /b 1
)
echo Program finished.
goto :eof

rem Function to calculate and print elapsed time
:print_time
    setlocal enabledelayedexpansion
    set end_time=%time%
    for /f "tokens=1-3 delims=:. " %%a in ("%2") do (
        set start_h=%%a
        set start_m=%%b
        set start_s=%%c
    )
    for /f "tokens=1-3 delims=:. " %%a in ("%end_time%") do (
        set end_h=%%a
        set end_m=%%b
        set end_s=%%c
    )
    set /a start_total_seconds=(1%start_h%*3600 + 1%start_m%*60 + 1%start_s%) %% 86400
    set /a end_total_seconds=(1%end_h%*3600 + 1%end_m%*60 + 1%end_s%) %% 86400
    set /a elapsed_seconds=end_total_seconds - start_total_seconds
    if !elapsed_seconds! lss 0 (
        set /a elapsed_seconds+=86400
    )
    set /a elapsed_h=elapsed_seconds / 3600
    set /a elapsed_m=(elapsed_seconds %% 3600) / 60
    set /a elapsed_s=elapsed_seconds %% 60
    echo %1 !elapsed_h! hours !elapsed_m! minutes !elapsed_s! seconds
    endlocal
    exit /b