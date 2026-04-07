document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const recommendationList = document.getElementById('recommendation-list');
    const pdfFrame = document.getElementById('pdf-frame');
    const emptyState = document.getElementById('empty-state');
    const currentDocTitle = document.getElementById('current-doc-title');

    // Debounce helper
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Fetch Recommendations on Load
    fetch('/api/recommend')
        .then(response => response.json())
        .then(data => {
            recommendationList.innerHTML = '';
            if (data.error) {
                recommendationList.innerHTML = `<div class="loading">Error loading recommendations: ${data.error}</div>`;
                return;
            }
            if (data.length === 0) {
                recommendationList.innerHTML = `<div class="loading">No recommendations found.</div>`;
                return;
            }

            data.forEach(item => {
                const card = createDocCard(item);
                recommendationList.appendChild(card);
            });
        })
        .catch(err => {
            recommendationList.innerHTML = `<div class="loading">Failed to load API. Ensure server is running.</div>`;
        });

    // Handle Search
    const performSearch = async (query) => {
        if (!query.trim()) {
            searchResults.classList.add('hidden');
            return;
        }

        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            searchResults.innerHTML = '';
            
            if (data.error) {
                searchResults.innerHTML = `<div class="loading">Error: ${data.error}</div>`;
            } else if (data.length === 0) {
                searchResults.innerHTML = `<div class="loading">No results found for "${query}"</div>`;
            } else {
                data.forEach(item => {
                    const card = createDocCard(item, true);
                    searchResults.appendChild(card);
                });
            }
            
            searchResults.classList.remove('hidden');
        } catch (error) {
            console.error('Search error:', error);
            searchResults.innerHTML = `<div class="loading">Network Error: Failed to reach server.</div>`;
            searchResults.classList.remove('hidden');
        }
    };

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.add('hidden');
        }
    });

    searchInput.addEventListener('input', debounce((e) => performSearch(e.target.value), 300));
    
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim() && searchResults.innerHTML) {
            searchResults.classList.remove('hidden');
        }
    });

    // Helper to create card UI
    function createDocCard(item, isSearchResult = false) {
        const div = document.createElement('div');
        div.className = 'doc-card';
        if (isSearchResult) {
            div.style.borderRadius = '0';
            div.style.borderLeft = 'none';
            div.style.borderRight = 'none';
            div.style.borderTop = 'none';
            div.style.backdropFilter = 'none';
            div.style.background = 'transparent';
        }

        div.innerHTML = `
            <div class="doc-title" title="${item.file_name}">${item.file_name}</div>
            <div class="doc-meta">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Chunks: ${item.chunk_count}
            </div>
        `;

        div.addEventListener('click', () => {
            loadPdf(item.file_name);
            if (isSearchResult) {
                searchResults.classList.add('hidden');
                searchInput.value = item.file_name;
            }
        });

        return div;
    }

    // Load PDF Document
    function loadPdf(filename) {
        currentDocTitle.textContent = filename;
        emptyState.classList.add('hidden');
        pdfFrame.classList.remove('hidden');
        
        // Add #toolbar=0&navpanes=0 for cleaner embedding
        pdfFrame.src = `/api/pdf?filename=${encodeURIComponent(filename)}#toolbar=1&navpanes=0&scrollbar=1`;
    }
});
