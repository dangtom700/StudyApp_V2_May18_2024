"""
PDF Study App - Main PyQt5 Application
Provides PDF preview, file lookup, and recommendation features
"""

import sys
import os
import sqlite3
from collections import Counter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QSplitter, QComboBox, QSpinBox, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QImage, QPixmap
from PyQt5.QtPrintSupport import QPrinter
import fitz  # PyMuPDF for PDF rendering

chunk_database_path = os.getcwd() + "\\" + "data\\pdf_text.db"
from database_manager import DatabaseManager


def disambiguate(labelled):
    """
    Make dropdown labels unique.

    Different editions, re-scans and re-typesets of a book share a title but have
    different content hashes, so the catalog legitimately holds several rows under one
    name. Two identical entries in a dropdown are indistinguishable, so repeats get a
    short hash suffix; unique titles are left clean.
    """
    counts = Counter(label for _, label in labelled)
    return [(hash_id, f"{label}  [{hash_id[:8]}]" if counts[label] > 1 else label)
            for hash_id, label in labelled]


class PDFViewerTab(QWidget):
    """Tab for viewing PDFs and their contents"""
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.current_pdf = None
        self.current_doc = None
        self.current_page = 0
        
        # Timer for debouncing resize events
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self.show_page(self.current_page))
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Splitter to separate controls/info (left) from PDF preview (right)
        splitter = QSplitter(Qt.Horizontal)
        
        # Left Side: Controls and Info
        left_container = QWidget()
        left_v_layout = QVBoxLayout(left_container)
        
        # Controls
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("PDF File:"))
        
        self.pdf_combo = QComboBox()
        # The combo shows book titles but carries the hash as item data, so selection
        # has to go through the index rather than the visible text.
        self.pdf_combo.currentIndexChanged.connect(self.on_pdf_index_changed)
        top_layout.addWidget(self.pdf_combo)
        
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self.refresh_pdf_list)
        top_layout.addWidget(refresh_btn)

        self.prev_pdf_btn = QPushButton("⬆ Back")
        self.prev_pdf_btn.clicked.connect(self.prev_pdf)
        top_layout.addWidget(self.prev_pdf_btn)

        self.next_pdf_btn = QPushButton("Next ⬇")
        self.next_pdf_btn.clicked.connect(self.next_pdf_file)
        top_layout.addWidget(self.next_pdf_btn)
        
        self.export_btn = QPushButton("Export Note")
        self.export_btn.clicked.connect(self.export_note)
        top_layout.addWidget(self.export_btn)
        
        left_v_layout.addLayout(top_layout)
        
        # Info panel
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 4px;")
        self.info_label.setWordWrap(True)
        left_v_layout.addWidget(self.info_label)
        
        left_v_layout.addWidget(QLabel("Content Preview (text):"))
        self.content_label = QLabel("")
        self.content_label.setWordWrap(True)
        self.content_label.setStyleSheet("background-color: white; padding: 10px; border: 1px solid #ccc; max-height: 150px;")
        left_v_layout.addWidget(self.content_label)
        
        # Tags section (inside the viewer tab)
        left_v_layout.addSpacing(10)
        left_v_layout.addWidget(QLabel("🏷️ Topics / Tags:"))
        self.tag_list = QListWidget()
        self.tag_list.setStyleSheet("background-color: #f9f9f9; border: 1px solid #ddd; max-height: 200px;")
        left_v_layout.addWidget(self.tag_list)
        
        # Add stretch to keep controls at top
        left_v_layout.addStretch()
        
        splitter.addWidget(left_container)
        
        # Right Side: PDF Visual Preview
        right_container = QWidget()
        right_v_layout = QVBoxLayout(right_container)
        
        # Navigation controls
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_page)
        self.page_label = QLabel("Page 0 of 0")
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addStretch()
        
        right_v_layout.addLayout(nav_layout)
        
        # Scroll area for PDF image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        
        self.pdf_render_label = QLabel()
        self.pdf_render_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.pdf_render_label)
        
        right_v_layout.addWidget(self.scroll_area)
        
        splitter.addWidget(right_container)
        splitter.setStretchFactor(1, 2) # Give more space to the PDF preview
        
        layout.addWidget(splitter)
        self.setLayout(layout)
        self.refresh_pdf_list()
    
    def refresh_pdf_list(self):
        """Load list of PDFs from database, labelled by title where the catalog has one"""
        self.pdf_combo.blockSignals(True)
        self.pdf_combo.clear()

        pdfs = self.db_manager.get_all_pdfs()
        for hash_id, label in disambiguate(pdfs):
            self.pdf_combo.addItem(label, hash_id)

        self.pdf_combo.blockSignals(False)
        if pdfs:
            self.pdf_combo.setCurrentIndex(0)
            self.on_pdf_selected(pdfs[0][0])
        else:
            self.update_pdf_nav_buttons()

    def select_pdf_by_hash(self, hash_id):
        """Select a book by hash, whatever label the combo is displaying for it"""
        index = self.pdf_combo.findData(hash_id)
        if index >= 0:
            self.pdf_combo.setCurrentIndex(index)

    def on_pdf_index_changed(self, index):
        """Combo selection changed -- resolve the visible title back to its hash"""
        if index >= 0:
            self.on_pdf_selected(self.pdf_combo.itemData(index))

    def update_pdf_nav_buttons(self):
        """Enable or disable PDF list navigation buttons"""
        current_index = self.pdf_combo.currentIndex()
        total = self.pdf_combo.count()
        self.prev_pdf_btn.setEnabled(current_index > 0)
        self.next_pdf_btn.setEnabled(current_index >= 0 and current_index < total - 1)
    
    def on_pdf_selected(self, pdf_name):
        """Display selected PDF info and preview"""
        if not pdf_name:
            return
        
        self.current_pdf = pdf_name
        
        # Get file info from database
        info = self.db_manager.get_pdf_info(pdf_name)
        
        if info:
            file_path, chunk_count = info
            book = self.db_manager.get_catalog_row(pdf_name)

            if book:
                pages = book.get('page_count') or '?'
                info_text = f"""
                <b>{book.get('title') or pdf_name}</b><br>
                <b>Domain:</b> {book.get('domain') or '-'}
                &nbsp;&nbsp;<b>Pages:</b> {pages}
                &nbsp;&nbsp;<b>Chunks:</b> {chunk_count}<br>
                <b>Author:</b> {book.get('pdf_author') or '-'}<br>
                <b>Hash:</b> <span style="color:#888">{pdf_name}</span><br>
                <b>Path:</b> {file_path}
                """
            else:
                info_text = f"""
                <b>File Name:</b> {pdf_name}<br>
                <b>Path:</b> {file_path}<br>
                <b>Total Chunks:</b> {chunk_count}
                """
            self.info_label.setText(info_text)
            
            # Get first chunk as preview
            preview = self.db_manager.get_pdf_preview(pdf_name, chars=1000)
            self.content_label.setText(preview if preview else "No content available")
            
            # Load PDF for visual preview
            self.load_pdf(file_path)
            
            # Load tags
            self.update_tags(pdf_name)
            
            # Update navigation controls for the PDF list
            self.update_pdf_nav_buttons()
        else:
            self.info_label.setText("File not found in database")
            self.content_label.setText("")
            self.pdf_render_label.clear()
            self.page_label.setText("Page 0 of 0")
            self.tag_list.clear()

    def update_tags(self, pdf_name):
        """Update the topics/tags list in the viewer tab"""
        self.tag_list.clear()
        tags = self.db_manager.get_pdf_tags(pdf_name)
        
        for topic, score in tags:
            item = QListWidgetItem(f"🏷️ {topic}")
            item.setToolTip(f"Relevance: {score:.4f}")
            self.tag_list.addItem(item)

    def export_note(self):
        """Export the current PDF note as Markdown"""
        if not self.current_pdf:
            QMessageBox.warning(self, "Export Error", "No PDF selected to export.")
            return

        pdf_name = self.current_pdf
        title = pdf_name
        source_filename = f"{pdf_name}.pdf"

        # Get tags
        tags = self.db_manager.get_pdf_tags(pdf_name)
        labels = [tag[0] for tag in tags]

        # Get recommendations
        recommendations = self.db_manager.get_recommendations(pdf_name, 20)
        rec_list = [f"{rec[0]}.pdf" for rec in recommendations]

        # Get save path from user
        default_name = f"{title}.md"
        save_path, _ = QFileDialog.getSaveFileName(self, "Export Note", default_name, "Markdown Files (*.md);;All Files (*)")

        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"Source: [[{source_filename}]]\n\n")
                
                f.write("> This is an auto-generated note based on content extracted from the PDF. It may contain errors or omissions. Please verify with the original source.\n\n")

                if labels:
                    f.write(f"Labels: #{', #'.join(labels)}\n\n")
                else:
                    f.write("Labels: #untagged\n\n")
                    
                f.write("### Recommended for further reading:\n\n")

                if rec_list:
                    for rec_index, rec in enumerate(rec_list, start=1):
                        f.write(f"{rec_index}. [[{rec}]]\n")
                else:
                    f.write("No recommendations found.\n")

            QMessageBox.information(self, "Export Successful", f"Note exported successfully to\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export note:\n{e}")

    def load_pdf(self, file_path):
        """Open PDF file and show first page"""
        if self.current_doc:
            self.current_doc.close()
            self.current_doc = None
            
        try:
            if os.path.exists(file_path):
                self.current_doc = fitz.open(file_path)
                self.current_page = 0
                self.show_page(0)
            else:
                self.pdf_render_label.setText(f"File not found at: {file_path}")
                self.page_label.setText("Page 0 of 0")
        except Exception as e:
            self.pdf_render_label.setText(f"Error loading PDF: {e}")
            self.page_label.setText("Page 0 of 0")

    def show_page(self, page_num):
        """Render and display a specific PDF page with auto-fit width"""
        if not self.current_doc:
            return
            
        if 0 <= page_num < len(self.current_doc):
            self.current_page = page_num
            page = self.current_doc.load_page(page_num)
            
            # Calculate zoom to fit width
            # Use viewport width to account for scrollbars
            available_width = self.scroll_area.viewport().width()
            
            # Fallback if UI is not yet fully laid out
            if available_width <= 0:
                available_width = self.scroll_area.width()
            if available_width <= 0:
                available_width = 800 # Default fallback
                
            page_rect = page.rect
            # Add a small margin (20px)
            zoom = (available_width - 20) / page_rect.width
            
            # Clamp zoom to reasonable levels
            zoom = max(0.1, min(zoom, 3.0))
            
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to QImage
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            self.pdf_render_label.setPixmap(pixmap)
            self.page_label.setText(f"Page {page_num + 1} of {len(self.current_doc)}")
            
            # Update button states
            self.prev_btn.setEnabled(page_num > 0)
            self.next_btn.setEnabled(page_num < len(self.current_doc) - 1)

    def resizeEvent(self, event):
        """Handle resize to maintain auto-fit width"""
        super().resizeEvent(event)
        if self.current_doc:
            self.resize_timer.start(150) # Debounce for 150ms
        
    def prev_page(self):
        """Show previous page"""
        if self.current_page > 0:
            self.show_page(self.current_page - 1)
            
    def next_page(self):
        """Show next page"""
        if self.current_doc and self.current_page < len(self.current_doc) - 1:
            self.show_page(self.current_page + 1)

    def prev_pdf(self):
        """Select the previous PDF in the list"""
        current_index = self.pdf_combo.currentIndex()
        if current_index > 0:
            self.pdf_combo.setCurrentIndex(current_index - 1)
            self.update_pdf_nav_buttons()

    def next_pdf_file(self):
        """Select the next PDF in the list"""
        current_index = self.pdf_combo.currentIndex()
        if current_index < self.pdf_combo.count() - 1:
            self.pdf_combo.setCurrentIndex(current_index + 1)
            self.update_pdf_nav_buttons()


class FileSearchTab(QWidget):
    """Tab for searching and looking up files"""
    view_requested = pyqtSignal(str)
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.selected_pdf = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Search mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Search Mode:"))
        
        self.search_mode = QComboBox()
        self.search_mode.addItems(["Content Search", "Tag Search", "Book Search"])
        self.search_mode.currentTextChanged.connect(self.on_search_mode_changed)
        mode_layout.addWidget(self.search_mode)
        mode_layout.addStretch()
        
        layout.addLayout(mode_layout)
        
        # Content Search Controls
        self.content_search_widget = QWidget()
        content_layout = QVBoxLayout(self.content_search_widget)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter keywords to search...")
        search_layout.addWidget(self.search_input)
        
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(search_btn)
        
        content_layout.addLayout(search_layout)
        layout.addWidget(self.content_search_widget)
        
        # Tag Search Controls
        self.tag_search_widget = QWidget()
        tag_layout = QVBoxLayout(self.tag_search_widget)
        
        tag_select_layout = QHBoxLayout()
        tag_select_layout.addWidget(QLabel("Select Tag:"))
        
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("-- Load tags --")
        self.load_tags()
        tag_select_layout.addWidget(self.tag_combo)
        
        search_tag_btn = QPushButton("Search by Tag")
        search_tag_btn.clicked.connect(self.perform_tag_search)
        tag_select_layout.addWidget(search_tag_btn)
        
        tag_layout.addLayout(tag_select_layout)
        self.tag_search_widget.setVisible(False)
        layout.addWidget(self.tag_search_widget)

        # Book Search Controls -- title/topic + subject domain, straight off the catalog.
        # Unlike Content Search this reads metadata only, so it answers "what do I own
        # about X" instantly instead of scanning every chunk of text.
        self.book_search_widget = QWidget()
        book_layout = QHBoxLayout(self.book_search_widget)

        book_layout.addWidget(QLabel("Title / topic:"))
        self.book_input = QLineEdit()
        self.book_input.setPlaceholderText("Leave blank to list a whole domain...")
        self.book_input.returnPressed.connect(self.perform_book_search)
        book_layout.addWidget(self.book_input)

        book_layout.addWidget(QLabel("Domain:"))
        self.domain_combo = QComboBox()
        self.load_domains()
        book_layout.addWidget(self.domain_combo)

        book_btn = QPushButton("Find Books")
        book_btn.clicked.connect(self.perform_book_search)
        book_layout.addWidget(book_btn)

        self.book_search_widget.setVisible(False)
        layout.addWidget(self.book_search_widget)
        
        # Search filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Max Results:"))
        
        self.max_results = QSpinBox()
        self.max_results.setMinimum(1)
        self.max_results.setMaximum(1000)
        self.max_results.setValue(20)
        filter_layout.addWidget(self.max_results)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Results list
        layout.addWidget(QLabel("Search Results:"))
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.on_result_selected)
        layout.addWidget(self.results_list)
        
        # Result details
        layout.addWidget(QLabel("Content Preview:"))
        self.result_detail = QLabel("")
        self.result_detail.setWordWrap(True)
        self.result_detail.setStyleSheet("background-color: #f9f9f9; padding: 10px; border: 1px solid #ccc; min-height: 100px;")
        layout.addWidget(self.result_detail)
        
        # Action buttons
        self.view_pdf_btn = QPushButton("📄 View Full PDF")
        self.view_pdf_btn.setEnabled(False)
        self.view_pdf_btn.clicked.connect(self.on_view_full_pdf)
        self.view_pdf_btn.setStyleSheet("background-color: #2196F3; font-size: 14px; padding: 10px;")
        layout.addWidget(self.view_pdf_btn)
        
        self.setLayout(layout)
    
    def perform_search(self):
        """Search for files/chunks matching keywords"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Input Error", "Please enter search keywords")
            return
        
        max_results = self.max_results.value()
        results = self.db_manager.search_files(query, max_results)
        
        # pdf_chunks keys carry a .txt suffix that file_info's do not -- strip it once,
        # here, so everything downstream deals in plain hashes.
        hits = [(f.removesuffix('.txt'), text, cid) for f, text, cid in results]
        labels = self.db_manager.display_names([h for h, _, _ in hits])

        self.results_list.clear()
        for pdf_name, chunk_text, chunk_id in hits:
            item = QListWidgetItem(f"📄 {labels[pdf_name]}")
            item.setToolTip(pdf_name)
            item.setData(Qt.UserRole, (pdf_name, chunk_text, chunk_id))
            self.results_list.addItem(item)

        self.result_detail.setText(f"Found {len(results)} results")
    
    def on_search_mode_changed(self, mode):
        """Handle search mode selection"""
        self.content_search_widget.setVisible(mode == "Content Search")
        self.tag_search_widget.setVisible(mode == "Tag Search")
        self.book_search_widget.setVisible(mode == "Book Search")
        self.results_list.clear()
        self.result_detail.setText("")

    def load_tags(self):
        """Load available tags from database"""
        tags = self.db_manager.get_all_tags()
        self.tag_combo.clear()
        self.tag_combo.addItems(tags)
        if not tags:
            self.tag_combo.addItem("-- No tags available --")

    def load_domains(self):
        """Load subject domains from the book catalog"""
        self.domain_combo.clear()
        self.domain_combo.addItem("All domains", None)
        for domain in self.db_manager.get_domains():
            self.domain_combo.addItem(domain, domain)

    def perform_book_search(self):
        """Search the catalog by title/topic and subject domain"""
        if not self.db_manager.has_catalog():
            QMessageBox.information(
                self, "Catalog not built",
                "Run  python src/main.py --buildCatalog  to build the book catalog first.")
            return

        results = self.db_manager.search_catalog(
            text=self.book_input.text().strip(),
            domain=self.domain_combo.currentData(),
            max_results=self.max_results.value())

        self.results_list.clear()
        for hash_id, title in results:
            item = QListWidgetItem(f"📕 {title}")
            item.setToolTip(hash_id)
            item.setData(Qt.UserRole, (hash_id, None, None))
            self.results_list.addItem(item)

        self.result_detail.setText(f"Found {len(results)} books")
    
    def perform_tag_search(self):
        """Search for files by selected tag"""
        tag = self.tag_combo.currentText()
        if not tag or tag.startswith("--"):
            QMessageBox.warning(self, "Input Error", "Please select a valid tag")
            return
        
        max_results = self.max_results.value()
        results = self.db_manager.search_files_by_tag(tag, max_results)
        
        labels = self.db_manager.display_names([r[0] for r in results])

        self.results_list.clear()
        for file_name, relevance_score in results:
            item = QListWidgetItem(f"📄 {labels[file_name]} (relevance: {relevance_score:.4f})")
            item.setToolTip(file_name)
            # Store just file_name for tag search
            item.setData(Qt.UserRole, (file_name, relevance_score, None))
            self.results_list.addItem(item)

        self.result_detail.setText(f"Found {len(results)} results for tag: {tag}")
    
    def on_result_selected(self, item):
        """Display selected search result"""
        data = item.data(Qt.UserRole)
        if data:
            file_name, info_b, info_c = data
            self.selected_pdf = file_name
            self.view_pdf_btn.setEnabled(True)
            
            # For content search results
            if info_c is not None:
                chunk_text = info_b
                chunk_id = info_c
                preview = chunk_text[:1000] if chunk_text else "No content"
                self.result_detail.setText(f"<b>File:</b> {file_name}<br><b>Chunk ID:</b> {chunk_id}<br><br><b>Content:</b><br>{preview}")
            # For tag search results (relevance_score) and book search results (None)
            else:
                relevance_score = info_b
                file_info = self.db_manager.get_pdf_info(file_name)
                tags = self.db_manager.get_pdf_tags(file_name)
                book = self.db_manager.get_catalog_row(file_name)

                tag_str = ", ".join([f"#{tag}" for tag, _ in tags[:5]]) if tags else "No tags"
                heading = (book.get('title') or file_name) if book else file_name
                relevance = (f"<b>Tag Relevance:</b> {relevance_score:.6f}<br>"
                             if relevance_score is not None else "")
                subject = (f"<b>Domain:</b> {book.get('domain') or '-'} "
                           f"&nbsp;&nbsp;<b>Pages:</b> {book.get('page_count') or '?'}<br>"
                           if book else "")

                if file_info:
                    file_path, chunk_count = file_info
                    detail_text = f"""
                    <b>{heading}</b><br>
                    {subject}{relevance}
                    <b>Total Chunks:</b> {chunk_count}<br>
                    <b>Tags:</b> {tag_str}<br>
                    <b>Path:</b> {file_path}
                    """
                else:
                    detail_text = (f"<b>{heading}</b><br>{subject}{relevance}"
                                   f"<i>Not text-extracted yet.</i>")

                self.result_detail.setText(detail_text)

    def on_view_full_pdf(self):
        """Emit signal to view the selected PDF"""
        if self.selected_pdf:
            self.view_requested.emit(self.selected_pdf)


class RecommendationTab(QWidget):
    """Tab for showing file recommendations based on similarity"""
    view_requested = pyqtSignal(str)
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.current_file = None
        self.selected_rec = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # File selection
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Select Base File:"))
        
        self.file_combo = QComboBox()
        # Shows titles, carries hashes -- select by index, not by visible text.
        self.file_combo.currentIndexChanged.connect(self.on_file_index_changed)
        select_layout.addWidget(self.file_combo)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_file_list)
        select_layout.addWidget(refresh_btn)
        
        layout.addLayout(select_layout)
        
        # Recommendation settings
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Recommendation Count:"))
        
        self.rec_count = QSpinBox()
        self.rec_count.setMinimum(1)
        self.rec_count.setMaximum(50)
        self.rec_count.setValue(10)
        settings_layout.addWidget(self.rec_count)
        
        generate_btn = QPushButton("Generate Recommendations")
        generate_btn.clicked.connect(self.generate_recommendations)
        settings_layout.addWidget(generate_btn)
        settings_layout.addStretch()
        
        layout.addLayout(settings_layout)
        
        # Recommendations details
        layout.addWidget(QLabel("Recommended Files (by greatest distance):"))
        
        self.rec_list = QListWidget()
        self.rec_list.itemClicked.connect(self.on_rec_selected)
        layout.addWidget(self.rec_list)
        
        # Details panel
        layout.addWidget(QLabel("File Details:"))
        self.rec_detail = QLabel("")
        self.rec_detail.setWordWrap(True)
        self.rec_detail.setStyleSheet("background-color: #f9f9f9; padding: 10px; border: 1px solid #ccc; min-height: 100px;")
        layout.addWidget(self.rec_detail)
        
        # Action buttons
        self.view_pdf_btn = QPushButton("📄 View Recommended PDF")
        self.view_pdf_btn.setEnabled(False)
        self.view_pdf_btn.clicked.connect(self.on_view_full_pdf)
        self.view_pdf_btn.setStyleSheet("background-color: #2196F3; font-size: 14px; padding: 10px;")
        layout.addWidget(self.view_pdf_btn)
        
        self.setLayout(layout)
        self.refresh_file_list()
    
    def refresh_file_list(self):
        """Load available files"""
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        
        files = self.db_manager.get_all_pdfs()
        for hash_id, label in disambiguate(files):
            self.file_combo.addItem(label, hash_id)

        self.file_combo.blockSignals(False)
        if files:
            self.on_file_selected(files[0][0])

    def on_file_index_changed(self, index):
        """Combo selection changed -- resolve the visible title back to its hash"""
        if index >= 0:
            self.on_file_selected(self.file_combo.itemData(index))

    def on_file_selected(self, file_name):
        """Store selected file"""
        self.current_file = file_name if file_name else None

    def generate_recommendations(self):
        """Generate recommendations for selected file"""
        if not self.current_file:
            QMessageBox.warning(self, "No File", "Please select a file first")
            return

        count = self.rec_count.value()
        recommendations = self.db_manager.get_recommendations(self.current_file, count)

        labels = self.db_manager.display_names([r[0] for r in recommendations])

        self.rec_list.clear()
        for file_name, distance in recommendations:
            item = QListWidgetItem(f"📄 {labels[file_name]} (score: {distance:.4f})")
            item.setToolTip(file_name)
            item.setData(Qt.UserRole, (file_name, distance))
            self.rec_list.addItem(item)

        self.rec_detail.setText(f"Showing {len(recommendations)} recommendations")
    
    def on_rec_selected(self, item):
        """Display recommendation details"""
        data = item.data(Qt.UserRole)
        if data:
            file_name, distance = data
            self.selected_rec = file_name
            self.view_pdf_btn.setEnabled(True)
            info = self.db_manager.get_pdf_info(file_name)
            if info:
                file_path, chunk_count = info
                detail_text = f"""
                <b>File Name:</b> {file_name}<br>
                <b>Distance Score:</b> {distance:.6f}<br>
                <b>Total Chunks:</b> {chunk_count}<br>
                <b>Path:</b> {file_path}<br>
                <i>Higher distance indicates more similar content</i>
                """
                self.rec_detail.setText(detail_text)

    def on_view_full_pdf(self):
        """Emit signal to view the recommended PDF"""
        if self.selected_rec:
            self.view_requested.emit(self.selected_rec)


class StudyAppWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager(chunk_database_path)
        self.init_ui()
    
    def init_ui(self):
        """Initialize main UI"""
        self.setWindowTitle("📚 Study App - PDF Manager")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Add tabs
        self.pdf_viewer = PDFViewerTab(self.db_manager)
        self.search_tab = FileSearchTab(self.db_manager)
        self.rec_tab = RecommendationTab(self.db_manager)
        
        self.tabs.addTab(self.pdf_viewer, "📄 PDF Viewer")
        self.tabs.addTab(self.search_tab, "🔍 Search Files")
        self.tabs.addTab(self.rec_tab, "💡 Recommendations")
        
        # Connect signals
        self.search_tab.view_requested.connect(self.show_pdf_in_viewer)
        self.rec_tab.view_requested.connect(self.show_pdf_in_viewer)
        
        # Set layout
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        
        # Style
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QLineEdit, QSpinBox, QComboBox {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)

    def show_pdf_in_viewer(self, pdf_name):
        """Switch to PDF viewer tab and select the specified PDF"""
        self.tabs.setCurrentIndex(0)
        self.pdf_viewer.select_pdf_by_hash(pdf_name)
    
    def closeEvent(self, event):
        """Clean up on close"""
        if self.db_manager:
            self.db_manager.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = StudyAppWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
