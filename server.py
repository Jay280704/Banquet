import http.server
import socketserver
import json
import os
import urllib.parse
import sys
import datetime

# Ensure the server runs in the script's directory so it can resolve index.html and assets
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir:
    os.chdir(script_dir)

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
ACTIVE_SESSIONS = {}  # In-memory store for session tokens: token -> username

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
        c.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                security_question VARCHAR(255) NOT NULL,
                security_answer_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Seed default admin if empty
        c.execute("SELECT COUNT(*) FROM admin_users")
        count = c.fetchone()[0]
        if count == 0:
            import hashlib
            default_pass = ADMIN_PASSCODE
            default_pass_hash = hashlib.sha256(default_pass.encode('utf-8')).hexdigest()
            default_ans = "masala mantra"
            default_ans_hash = hashlib.sha256(default_ans.lower().strip().encode('utf-8')).hexdigest()
            c.execute('''
                INSERT INTO admin_users (username, password_hash, security_question, security_answer_hash)
                VALUES (%s, %s, %s, %s)
            ''', ('admin', default_pass_hash, 'What is the name of this banquet hall?', default_ans_hash))
            print("Default admin user ('admin') seeded successfully.")
            
        conn.commit()
        conn.close()
        print("MySQL database and tables initialized successfully.")
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
        # Reroute root to index.html
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
            return super().do_GET()

        parsed_path = urllib.parse.urlparse(self.path)
        
        # API Route: Fetch all inquiries (Admin Dashboard)
        if parsed_path.path == '/api/admin/inquiries':
            passcode = self.headers.get('X-Admin-Passcode')
            if passcode != ADMIN_PASSCODE and passcode not in ACTIVE_SESSIONS:
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
            if passcode != ADMIN_PASSCODE and passcode not in ACTIVE_SESSIONS:
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
            if passcode != ADMIN_PASSCODE and passcode not in ACTIVE_SESSIONS:
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

        # API Route: Admin login
        elif parsed_path.path == '/api/admin/login':
            try:
                import hashlib
                import uuid
                data = self.read_json_body()
                username = data.get('username')
                password = data.get('password')

                if not username or not password:
                    self.send_json_response({"success": False, "error": "Username and Password are required"}, 400)
                    return

                password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB,
                    cursorclass=pymysql.cursors.DictCursor
                )
                c = conn.cursor()
                c.execute('SELECT * FROM admin_users WHERE username = %s AND password_hash = %s', (username, password_hash))
                user = c.fetchone()
                conn.close()

                if user:
                    token = uuid.uuid4().hex
                    ACTIVE_SESSIONS[token] = username
                    self.send_json_response({"success": True, "token": token})
                else:
                    self.send_json_response({"success": False, "error": "Invalid username or password"}, 401)
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, 500)
            return

        # API Route: Fetch Security Question
        elif parsed_path.path == '/api/admin/forgot-password/question':
            try:
                data = self.read_json_body()
                username = data.get('username')

                if not username:
                    self.send_json_response({"success": False, "error": "Username is required"}, 400)
                    return

                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB,
                    cursorclass=pymysql.cursors.DictCursor
                )
                c = conn.cursor()
                c.execute('SELECT security_question FROM admin_users WHERE username = %s', (username,))
                user = c.fetchone()
                conn.close()

                if user:
                    self.send_json_response({"success": True, "question": user['security_question']})
                else:
                    self.send_json_response({"success": False, "error": "Username not found"}, 404)
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, 500)
            return

        # API Route: Verify Answer & Reset Password
        elif parsed_path.path == '/api/admin/forgot-password/reset':
            try:
                import hashlib
                data = self.read_json_body()
                username = data.get('username')
                answer = data.get('answer')
                new_password = data.get('new_password')

                if not username or not answer or not new_password:
                    self.send_json_response({"success": False, "error": "Username, answer, and new password are required"}, 400)
                    return

                answer_hash = hashlib.sha256(answer.lower().strip().encode('utf-8')).hexdigest()

                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB,
                    cursorclass=pymysql.cursors.DictCursor
                )
                c = conn.cursor()
                c.execute('SELECT security_answer_hash FROM admin_users WHERE username = %s', (username,))
                user = c.fetchone()

                if not user:
                    conn.close()
                    self.send_json_response({"success": False, "error": "Username not found"}, 404)
                    return

                if user['security_answer_hash'] == answer_hash:
                    new_password_hash = hashlib.sha256(new_password.encode('utf-8')).hexdigest()
                    c.execute('UPDATE admin_users SET password_hash = %s WHERE username = %s', (new_password_hash, username))
                    conn.commit()
                    conn.close()
                    self.send_json_response({"success": True, "message": "Password updated successfully"})
                else:
                    conn.close()
                    self.send_json_response({"success": False, "error": "Incorrect answer to security question"}, 400)
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, 500)
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
