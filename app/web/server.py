import json
import sqlite3
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'pdf_text.db'))
PDF_DIR = r"D:\\READING_LIST"

class APIHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == '/api/search':
            self.handle_search(query_params.get('q', [''])[0])
        elif path == '/api/recommend':
            self.handle_recommend()
        elif path == '/api/pdf':
            self.handle_pdf(query_params.get('filename', [''])[0])
        else:
            # Fall back to serving static files from the current directory (app/web)
            super().do_GET()

    def handle_search(self, query):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response_data = []
        print(f"DEBUG: Handling search for query: {query}", flush=True)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Simple wildcard search
            search_query = f"%{query}%"
            cursor.execute("SELECT id, file_name, chunk_count FROM file_info WHERE file_name LIKE ? LIMIT 20", (search_query,))
            
            for row in cursor.fetchall():
                response_data.append(dict(row))
            conn.close()
        except Exception as e:
            print(f"DEBUG ERROR: Search failed: {e}")
            response_data = {"error": str(e)}

        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_recommend(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response_data = []
        print(f"DEBUG: Handling recommendations request", flush=True)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get top docs based on chunk_count
            cursor.execute("SELECT id, file_name, chunk_count FROM file_info ORDER BY chunk_count DESC LIMIT 20")
            
            for row in cursor.fetchall():
                response_data.append(dict(row))
            conn.close()
        except Exception as e:
            print(f"DEBUG ERROR: Recommendations failed: {e}")
            response_data = {"error": str(e)}

        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_pdf(self, filename):
        if not filename:
            self.send_error(400, "Filename not provided")
            return
            
        pdf_path = os.path.join(PDF_DIR, f"{filename}.pdf")
        
        if not os.path.exists(pdf_path):
            self.send_error(404, "PDF not found")
            return
            
        try:
            with open(pdf_path, 'rb') as f:
                pdf_data = f.read()
            self.send_response(200)
            self.send_header('Content-type', 'application/pdf')
            self.send_header('Content-length', str(len(pdf_data)))
            self.send_header('Content-Disposition', f'inline; filename="{filename}.pdf"')
            self.end_headers()
            self.wfile.write(pdf_data)
        except Exception as e:
            self.send_error(500, f"Error reading PDF: {e}")

def run(server_class=HTTPServer, handler_class=APIHandler, port=8000):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting lightweight Python web server on port {port}...", flush=True)
    print(f"Serving files from {os.getcwd()}", flush=True)
    print(f"Database Path: {DB_PATH}", flush=True)
    print(f"PDF Directory: {PDF_DIR}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("Server stopped.")

if __name__ == '__main__':
    run()
