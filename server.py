import http.server
import socketserver
import json
import os
import urllib.parse
import sys
import datetime

# 1. Automated Dependency Handler: Resolve pymysql driver
try:
    import pymysql
    import pymysql.cursors
except ImportError:
    import subprocess
    print("pymysql module not found. Installing now using system pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pymysql"])
        import pymysql
        import pymysql.cursors
        print("pymysql installed successfully.")
    except Exception as e:
        print(f"Error installing pymysql: {e}")
        print("Please run 'pip install pymysql' manually in your command prompt.")
        sys.exit(1)

PORT = int(os.environ.get('PORT', 8000))
ADMIN_PASSCODE = os.environ.get('ADMIN_PASSCODE', 'mantra123')

# 2. Database Connection Settings (Loads environment variables first, defaults to local settings)
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB = os.environ.get('MYSQL_DB', 'masala_mantra')

def init_db():
    print(f"Connecting to MySQL server at {MYSQL_HOST}:{MYSQL_PORT}...")
    try:
        # Connect to MySQL instance without selecting database to initialize it
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        c = conn.cursor()
        c.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
        conn.commit()
        conn.close()

        # Connect to the created database to construct schema
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB
        )
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS inquiries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                type VARCHAR(50) NOT NULL,          -- 'contact' or 'booking'
                name VARCHAR(255) NOT NULL,
                phone VARCHAR(50) NOT NULL,
                email VARCHAR(255),
                event_type VARCHAR(100),
                guests INT,
                date VARCHAR(50),
                session VARCHAR(50),
                theme VARCHAR(100),
                notes TEXT,
                addons TEXT,                 -- Comma-separated list
                estimated_cost VARCHAR(100),
                ref_code VARCHAR(100),
                status VARCHAR(50) DEFAULT 'Pending', -- 'Pending', 'Contacted', 'Confirmed', 'Cancelled'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        print("MySQL database and table initialized successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect to MySQL database! Please ensure MySQL server is running. Detail: {e}")
        sys.exit(1)

# Custom JSON Encoder to serialize datetime columns
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)

class ThreadedHTTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

class BanquetServerHandler(http.server.SimpleHTTPRequestHandler):
    
    def log_message(self, format, *args):
        super().log_message(format, *args)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Passcode')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def do_GET(self):
        # Reroute root to banquet.html
        if self.path == '/' or self.path == '/index.html':
            self.path = '/banquet.html'
            return super().do_GET()

        parsed_path = urllib.parse.urlparse(self.path)
        
        # API Route: Fetch all inquiries (Admin Dashboard)
        if parsed_path.path == '/api/admin/inquiries':
            passcode = self.headers.get('X-Admin-Passcode')
            if passcode != ADMIN_PASSCODE:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            try:
                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB,
                    cursorclass=pymysql.cursors.DictCursor
                )
                c = conn.cursor()
                c.execute('SELECT * FROM inquiries ORDER BY created_at DESC')
                rows = c.fetchall()
                conn.close()

                self.send_json_response(rows)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        return super().do_GET()

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)

        # API Route: Customer general tour inquiry
        if parsed_path.path == '/api/inquiries':
            try:
                data = self.read_json_body()
                name = data.get('name')
                phone = data.get('phone')
                email = data.get('email')
                notes = data.get('notes', '')

                if not name or not phone:
                    self.send_json_response({"error": "Name and Phone are required"}, 400)
                    return

                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB
                )
                c = conn.cursor()
                c.execute('''
                    INSERT INTO inquiries (type, name, phone, email, notes, event_type, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', ('contact', name, phone, email, notes, 'Social Gathering', 'Pending'))
                conn.commit()
                conn.close()

                self.send_json_response({"success": True, "message": "Inquiry recorded successfully!"})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        # API Route: Calculator modal detailed package booking
        elif parsed_path.path == '/api/bookings':
            try:
                data = self.read_json_body()
                name = data.get('name')
                phone = data.get('phone')
                email = data.get('email')
                event_type = data.get('event_type')
                guests = data.get('guests')
                date = data.get('date')
                session = data.get('session')
                theme = data.get('theme')
                notes = data.get('notes', '')
                addons = data.get('addons', [])
                estimated_cost = data.get('estimated_cost')
                ref_code = data.get('ref_code')

                if not name or not phone or not date:
                    self.send_json_response({"error": "Name, Phone, and Date are required"}, 400)
                    return

                addons_str = ", ".join(addons) if isinstance(addons, list) else str(addons)

                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB
                )
                c = conn.cursor()
                c.execute('''
                    INSERT INTO inquiries (type, name, phone, email, event_type, guests, date, session, theme, notes, addons, estimated_cost, ref_code, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', ('booking', name, phone, email, event_type, guests, date, session, theme, notes, addons_str, estimated_cost, ref_code, 'Pending'))
                conn.commit()
                conn.close()

                self.send_json_response({"success": True, "message": "Booking request submitted successfully!", "ref_code": ref_code})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        # API Route: Admin update inquiry status
        elif parsed_path.path == '/api/admin/update_status':
            passcode = self.headers.get('X-Admin-Passcode')
            if passcode != ADMIN_PASSCODE:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            try:
                data = self.read_json_body()
                inquiry_id = data.get('id')
                status = data.get('status')

                if not inquiry_id or not status:
                    self.send_json_response({"error": "ID and Status are required"}, 400)
                    return

                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB
                )
                c = conn.cursor()
                c.execute('UPDATE inquiries SET status = %s WHERE id = %s', (status, inquiry_id))
                conn.commit()
                conn.close()

                self.send_json_response({"success": True, "message": f"Status updated to '{status}'"})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        # API Route: Admin delete inquiry
        elif parsed_path.path == '/api/admin/delete':
            passcode = self.headers.get('X-Admin-Passcode')
            if passcode != ADMIN_PASSCODE:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            try:
                data = self.read_json_body()
                inquiry_id = data.get('id')

                if not inquiry_id:
                    self.send_json_response({"error": "Inquiry ID is required"}, 400)
                    return

                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB
                )
                c = conn.cursor()
                c.execute('DELETE FROM inquiries WHERE id = %s', (inquiry_id,))
                conn.commit()
                conn.close()

                self.send_json_response({"success": True, "message": "Inquiry successfully deleted!"})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        self.send_json_response({"error": "Not Found"}, 404)

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Passcode')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(json.dumps(data, cls=DateTimeEncoder).encode('utf-8'))

if __name__ == '__main__':
    init_db()
    with ThreadedHTTPServer(("", PORT), BanquetServerHandler) as server:
        print(f"MySQL Backend Server running at: http://localhost:{PORT}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
