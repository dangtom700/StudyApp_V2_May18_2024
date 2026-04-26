# Recent Codebase Updates (April 2026)

This document summarizes the significant features and workflow improvements integrated into the codebase over the current iteration cycle.

## 1. Semantic Search Engine & Vector Database Integration
* **Local Semantic Search Engine**: Deployed a robust Semantic Search engine utilizing LangChain, LangGraph, and Ollama. This pipeline processes PDF documents and supports sophisticated semantic searches across chunks.
* **Vector Store Ingestion**: Upgraded `src/embed.py` to handle direct database-to-vector-store processing. This entirely bypasses the intermediate text-splitting previously handled by python scripts, writing directly into the Chroma vector database. 
* **Performance Enhancements**: Introduced efficiency improvements to the ingestion mechanism, capitalizing on parallel processing and batched inserts to significantly speed up database population metrics.

## 2. Topic Labeling and Tokenization Refinements
* **Resumption Mechanisms**: Engineered a bullet-proof resumption mechanism for the `label_topics` and `mappingItemMatrix` pipeline logic in `src/lib/feature.hpp`. This ensures processes gracefully recover from interruptions without causing duplicate computations, drastically increasing resilience for long-running batch jobs.
* **Topic-to-Topic Similarity**: Introduced an experimental `--TopicSimilarity` feature that automatically compares topic pairs, computing and storing their relational distances in the database using efficient, bidirectionally inserted scores.
* **Refined Topic Tokenization**: Adjusted `src/modules/word_freq.py`'s `tokenize_topics` function to reliably process wiki topic files locally from the `wiki_topics` directory, standardizing topic extraction without over-relying on external APIs like `wikipedia_api`. The distance metrics have also been calibrated to compute based on the sum of squared frequencies.
* **Bidirectional Recommendation Queries**: Advanced SQL queries have been introduced to retrieve distinct related IDs from both sides of the `comparison` table, perfectly managing the "shrinking pool" relational storage pattern and guaranteeing top-100 unique recommendations.

## 3. PDF Viewer and Graphical Interface Enhancements
* **Integrated PDF Rendering**: Fulfilled one of the major roadmap goals by embedding actual PDF rendering within the PyQt5 application. Instead of only reading text chunks, users can view true PDF pages side-by-side with document controls.
* **Split-View Layout & Auto-Fit**: Implemented a responsive split-view between the visual document pane and navigation controls. Added auto-fit width configurations so rendered PDF pages automatically size themselves optimally on various monitor layouts.
* **In-Tab Recommendation Sidebar**: Added a sophisticated contextual sidebar directly inside the PDF reading view, allowing users to rapidly pivot between related topics or dissimilar reading materials based on calculated distances.
* **PDF Tags Retrieval**: Integrated metadata tags retrieval directly into `app/database_manager.py` to display relevant document topic tags within the viewer.

## System Summary
The codebase has evolved from a robust text-extraction application to a comprehensive, semantic search-enabled PDF manager. The transition to vector databases, local model integrations, advanced bidirectional queries, and proper UI visual rendering makes the application a significantly more powerful tool for researching cross-disciplinary studies and tracking localized document relationships.
