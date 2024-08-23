"""
Title suggestion system

Phase 1: Precompute the vector length after processing the counting part of popular words
1. Process word frequency analysis, text chunking, and store information in database
2. Create a table with columns: word (from word frequency analysis), title1, title2, ...
3. A map of title and term_count iterate through very word provided by word frequency analysis
4. Store information in database
5. For each title column, compute the vector length of each title

Phase 2: Process prompt for the search
1. Split word and process root word
2. Compute vector length
3. Search for the closest title from the database
"""
