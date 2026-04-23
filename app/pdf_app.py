"""
PDF Study App - Main PyQt5 Application
Provides PDF preview, file lookup, and recommendation features
"""

import sys
import os
import sqlite3
from pathlib import Path
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
        self.pdf_combo.currentTextChanged.connect(self.on_pdf_selected)
        top_layout.addWidget(self.pdf_combo)
        
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self.refresh_pdf_list)
        top_layout.addWidget(refresh_btn)
        
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
        """Load list of PDFs from database"""
        self.pdf_combo.blockSignals(True)
        self.pdf_combo.clear()
        
        pdfs = self.db_manager.get_all_pdfs()
        self.pdf_combo.addItems(pdfs)
        
        self.pdf_combo.blockSignals(False)
        if pdfs:
            self.on_pdf_selected(pdfs[0])
    
    def on_pdf_selected(self, pdf_name):
        """Display selected PDF info and preview"""
        if not pdf_name:
            return
        
        self.current_pdf = pdf_name
        
        # Get file info from database
        info = self.db_manager.get_pdf_info(pdf_name)
        
        if info:
            file_path, chunk_count = info
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
        
        # Search controls
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter keywords to search...")
        search_layout.addWidget(self.search_input)
        
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(search_btn)
        
        layout.addLayout(search_layout)
        
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
        
        self.results_list.clear()
        for file_name, chunk_text, chunk_id in results:
            # Get the base PDF name (remove .txt)
            pdf_name = file_name.removesuffix('.txt')
            # Get the stem for display (no extensions)
            display_name = Path(pdf_name).stem
            
            item = QListWidgetItem(f"📄 {display_name}")
            item.setData(Qt.UserRole, (pdf_name, chunk_text, chunk_id))
            self.results_list.addItem(item)
        
        self.result_detail.setText(f"Found {len(results)} results")
    
    def on_result_selected(self, item):
        """Display selected search result"""
        data = item.data(Qt.UserRole)
        if data:
            file_name, chunk_text, chunk_id = data
            self.selected_pdf = file_name
            self.view_pdf_btn.setEnabled(True)
            preview = chunk_text[:1000] if chunk_text else "No content"
            self.result_detail.setText(f"<b>File:</b> {file_name}<br><b>Chunk ID:</b> {chunk_id}<br><br><b>Content:</b><br>{preview}")

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
        self.file_combo.currentTextChanged.connect(self.on_file_selected)
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
        self.file_combo.addItems(files)
        
        self.file_combo.blockSignals(False)
        if files:
            self.on_file_selected(files[0])
    
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
        
        self.rec_list.clear()
        for file_name, distance in recommendations:
            display_name = Path(file_name).stem
            item = QListWidgetItem(f"📄 {display_name} (score: {distance:.4f})")
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
        self.pdf_viewer.pdf_combo.setCurrentText(pdf_name)
    
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
