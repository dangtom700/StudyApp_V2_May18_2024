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
    QFileDialog, QSplitter, QComboBox, QSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
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
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Top controls
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("PDF File:"))
        
        self.pdf_combo = QComboBox()
        self.pdf_combo.currentTextChanged.connect(self.on_pdf_selected)
        top_layout.addWidget(self.pdf_combo)
        
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self.refresh_pdf_list)
        top_layout.addWidget(refresh_btn)
        
        layout.addLayout(top_layout)
        
        # Info panel
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 4px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # Content preview
        self.content_label = QLabel("")
        self.content_label.setWordWrap(True)
        self.content_label.setStyleSheet("background-color: white; padding: 10px; border: 1px solid #ccc;")
        layout.addWidget(QLabel("Content Preview (first 500 chars):"))
        layout.addWidget(self.content_label)
        
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
            preview = self.db_manager.get_pdf_preview(pdf_name, chars=500)
            self.content_label.setText(preview if preview else "No content available")
        else:
            self.info_label.setText("File not found in database")
            self.content_label.setText("")


class FileSearchTab(QWidget):
    """Tab for searching and looking up files"""
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
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
        self.result_detail.setStyleSheet("background-color: #f9f9f9; padding: 10px; border: 1px solid #ccc;")
        layout.addWidget(self.result_detail)
        
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
            item = QListWidgetItem(f"📄 {file_name}")
            item.setData(Qt.UserRole, (file_name, chunk_text, chunk_id))
            self.results_list.addItem(item)
        
        self.result_detail.setText(f"Found {len(results)} results")
    
    def on_result_selected(self, item):
        """Display selected search result"""
        data = item.data(Qt.UserRole)
        if data:
            file_name, chunk_text, chunk_id = data
            preview = chunk_text[:1000] if chunk_text else "No content"
            self.result_detail.setText(f"<b>File:</b> {file_name}<br><b>Chunk ID:</b> {chunk_id}<br><br><b>Content:</b><br>{preview}")


class RecommendationTab(QWidget):
    """Tab for showing file recommendations based on dissimilarity"""
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.current_file = None
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
        self.rec_detail.setStyleSheet("background-color: #f9f9f9; padding: 10px; border: 1px solid #ccc;")
        layout.addWidget(self.rec_detail)
        
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
            item = QListWidgetItem(f"📄 {file_name} (distance: {distance:.4f})")
            item.setData(Qt.UserRole, (file_name, distance))
            self.rec_list.addItem(item)
        
        self.rec_detail.setText(f"Showing {len(recommendations)} recommendations")
    
    def on_rec_selected(self, item):
        """Display recommendation details"""
        data = item.data(Qt.UserRole)
        if data:
            file_name, distance = data
            info = self.db_manager.get_pdf_info(file_name)
            if info:
                file_path, chunk_count = info
                detail_text = f"""
                <b>File Name:</b> {file_name}<br>
                <b>Distance Score:</b> {distance:.6f}<br>
                <b>Total Chunks:</b> {chunk_count}<br>
                <b>Path:</b> {file_path}<br>
                <i>Higher distance indicates more dissimilar content</i>
                """
                self.rec_detail.setText(detail_text)


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
        tabs = QTabWidget()
        
        # Add tabs
        tabs.addTab(PDFViewerTab(self.db_manager), "📄 PDF Viewer")
        tabs.addTab(FileSearchTab(self.db_manager), "🔍 Search Files")
        tabs.addTab(RecommendationTab(self.db_manager), "💡 Recommendations")
        
        # Set layout
        layout = QVBoxLayout()
        layout.addWidget(tabs)
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
