import http.server
import socketserver
import json
import os
import urllib.parse
import sys
import datetime
import hashlib
import secrets

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 100000
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"

def verify_password(password: str, hashed_val: str) -> bool:
    if not hashed_val.startswith("pbkdf2_sha256$"):
        old_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return old_hash == hashed_val
    parts = hashed_val.split('$')
    if len(parts) != 4:
        return False
    _, iterations, salt, hash_hex = parts
    iterations = int(iterations)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return dk.hex() == hash_hex

def hash_security_answer(answer: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 100000
    cleaned = answer.lower().strip()
    dk = hashlib.pbkdf2_hmac('sha256', cleaned.encode('utf-8'), salt.encode('utf-8'), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"

def verify_security_answer(answer: str, hashed_val: str) -> bool:
    cleaned = answer.lower().strip()
    if not hashed_val.startswith("pbkdf2_sha256$"):
        old_hash = hashlib.sha256(cleaned.encode('utf-8')).hexdigest()
        return old_hash == hashed_val
    parts = hashed_val.split('$')
    if len(parts) != 4:
        return False
    _, iterations, salt, hash_hex = parts
    iterations = int(iterations)
    dk = hashlib.pbkdf2_hmac('sha256', cleaned.encode('utf-8'), salt.encode('utf-8'), iterations)
    return dk.hex() == hash_hex

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
        c.execute('''
            CREATE TABLE IF NOT EXISTS showcase_photos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                image_path VARCHAR(255) NOT NULL,
                category VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                capacity VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Seed default admin if empty
        c.execute("SELECT COUNT(*) FROM admin_users")
        count = c.fetchone()[0]
        if count == 0:
            default_pass = ADMIN_PASSCODE
            default_pass_hash = hash_password(default_pass)
            default_ans = "masala mantra"
            default_ans_hash = hash_security_answer(default_ans)
            c.execute('''
                INSERT INTO admin_users (username, password_hash, security_question, security_answer_hash)
                VALUES (%s, %s, %s, %s)
            ''', ('admin', default_pass_hash, 'What is the name of this banquet hall?', default_ans_hash))
            print("Default admin user ('admin') seeded successfully.")

        # Seed default showcase photos if empty
        c.execute("SELECT COUNT(*) FROM showcase_photos")
        photo_count = c.fetchone()[0]
        if photo_count == 0:
            default_photos = [
                ('real_stage.jpg', 'wedding', 'The Grand Banquet Hall', 'Bespoke elegant setup featuring clean, air-conditioned layouts and luxury decor panels.', '150 - 400 Guests'),
                ('real_entrance.png', 'community', 'The Community Hall', 'Spacious, welcoming hall ideal for Sangeet, Haldi, Mehendi, and family gatherings.', '80 - 200 Guests'),
                ('real_dining.jpg', 'dining', 'Mughlai Dining Lounge', 'Indulge in premium in-house catering layouts serving authentic North Indian and Mughlai buffet tiers.', '40 - 120 Guests'),
                ('real_buffet.png', 'terrace', 'Open-Air Terrace Deck', 'Cozy open-sky terrace optimized for evening birthday parties and cocktail tables under stars.', '50 - 150 Guests')
            ]
            for image_path, category, title, description, capacity in default_photos:
                c.execute('''
                    INSERT INTO showcase_photos (image_path, category, title, description, capacity)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (image_path, category, title, description, capacity))
            print("Default showcase photos seeded successfully.")
            
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

def parse_multipart(content_type, body_bytes):
    """
    Parses multipart/form-data request body manually without external dependencies.
    Returns: (fields_dict, files_dict)
      fields_dict: name -> string value
      files_dict: name -> { 'filename': str, 'content_type': str, 'content': bytes }
    """
    import re
    fields = {}
    files = {}
    
    # Extract boundary
    boundary_match = re.search(r'boundary=([^;]+)', content_type)
    if not boundary_match:
        return fields, files
    boundary = b'--' + boundary_match.group(1).strip().encode('utf-8')
    
    # Split by boundary
    parts = body_bytes.split(boundary)
    for part in parts:
        if not part or part == b'\r\n' or part == b'--\r\n' or part.startswith(b'--'):
            continue
        
        if b'\r\n\r\n' not in part:
            continue
        
        headers_part, content = part.split(b'\r\n\r\n', 1)
        
        if headers_part.startswith(b'\r\n'):
            headers_part = headers_part[2:]
        if content.endswith(b'\r\n'):
            content = content[:-2]
            
        headers_str = headers_part.decode('utf-8', errors='ignore')
        
        name_match = re.search(r'name="([^"]+)"', headers_str)
        filename_match = re.search(r'filename="([^"]+)"', headers_str)
        content_type_match = re.search(r'Content-Type:\s*([^\r\n]+)', headers_str, re.IGNORECASE)
        
        if name_match:
            name = name_match.group(1)
            if filename_match:
                filename = filename_match.group(1)
                ct = content_type_match.group(1) if content_type_match else 'application/octet-stream'
                files[name] = {
                    'filename': filename,
                    'content_type': ct,
                    'content': content
                }
            else:
                fields[name] = content.decode('utf-8', errors='ignore')
                
    return fields, files

class ThreadedHTTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

class BanquetServerHandler(http.server.SimpleHTTPRequestHandler):
    
    def log_message(self, format, *args):
        super().log_message(format, *args)

    def get_cors_origin(self):
        origin = self.headers.get('Origin')
        if origin:
            parsed = urllib.parse.urlparse(origin)
            hostname = parsed.hostname
            # Allow local development origins safely
            if hostname in ('localhost', '127.0.0.1') or (hostname and hostname.startswith('192.168.')):
                return origin
        return None

    def do_OPTIONS(self):
        self.send_response(200)
        origin = self.get_cors_origin()
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Passcode')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path_str = parsed_path.path

        # Prevent Directory Traversal
        if '..' in path_str or '\\' in path_str:
            self.send_error(400, "Bad Request")
            return

        # Reroute root to index.html
        if path_str == '/' or path_str == '/index.html':
            self.path = '/index.html'
            return super().do_GET()

        # If it's an API route, let it pass to handling logic
        if path_str.startswith('/api/'):
            # API Route: Fetch all inquiries (Admin Dashboard)
            if path_str == '/api/admin/inquiries':
                passcode = self.headers.get('X-Admin-Passcode')
                if not passcode or passcode not in ACTIVE_SESSIONS:
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

            # API Route: Fetch all showcase photos
            elif path_str == '/api/photos':
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
                    c.execute('SELECT * FROM showcase_photos ORDER BY created_at DESC')
                    rows = c.fetchall()
                    conn.close()

                    self.send_json_response(rows)
                except Exception as e:
                    self.send_json_response({"error": str(e)}, 500)
                return

            self.send_json_response({"error": "Not Found"}, 404)
            return

        # Secure Static File Serving: Extension Whitelisting
        allowed_extensions = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.ico', '.woff', '.woff2'}
        _, ext = os.path.splitext(path_str)
        if ext.lower() not in allowed_extensions:
            self.send_error(403, "Access Forbidden")
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
            if not passcode or passcode not in ACTIVE_SESSIONS:
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
            if not passcode or passcode not in ACTIVE_SESSIONS:
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
                import uuid
                data = self.read_json_body()
                username = data.get('username')
                password = data.get('password')

                if not username or not password:
                    self.send_json_response({"success": False, "error": "Username and Password are required"}, 400)
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
                c.execute('SELECT * FROM admin_users WHERE username = %s', (username,))
                user = c.fetchone()
                conn.close()

                if user and verify_password(password, user['password_hash']):
                    # Auto-upgrade password hash if it's in the old unsalted format
                    if not user['password_hash'].startswith("pbkdf2_sha256$"):
                        try:
                            new_hash = hash_password(password)
                            conn_upgrade = pymysql.connect(
                                host=MYSQL_HOST,
                                port=MYSQL_PORT,
                                user=MYSQL_USER,
                                password=MYSQL_PASSWORD,
                                database=MYSQL_DB
                            )
                            c_up = conn_upgrade.cursor()
                            c_up.execute('UPDATE admin_users SET password_hash = %s WHERE id = %s', (new_hash, user['id']))
                            conn_upgrade.commit()
                            conn_upgrade.close()
                            print(f"Password hash auto-upgraded to PBKDF2 for user: {username}")
                        except Exception as upgrade_err:
                            print(f"Failed to auto-upgrade password hash: {upgrade_err}")

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
                data = self.read_json_body()
                username = data.get('username')
                answer = data.get('answer')
                new_password = data.get('new_password')

                if not username or not answer or not new_password:
                    self.send_json_response({"success": False, "error": "Username, answer, and new password are required"}, 400)
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
                c.execute('SELECT security_answer_hash FROM admin_users WHERE username = %s', (username,))
                user = c.fetchone()

                if not user:
                    conn.close()
                    self.send_json_response({"success": False, "error": "Username not found"}, 404)
                    return

                if verify_security_answer(answer, user['security_answer_hash']):
                    new_password_hash = hash_password(new_password)
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

        # API Route: Upload Showcase Photo
        elif parsed_path.path == '/api/admin/photos/upload':
            passcode = self.headers.get('X-Admin-Passcode')
            if not passcode or passcode not in ACTIVE_SESSIONS:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            try:
                content_type = self.headers.get('Content-Type', '')
                content_length = int(self.headers.get('Content-Length', 0))
                
                # Protect against excessive upload size at server level
                max_size = 5 * 1024 * 1024  # 5 MB
                if content_length > max_size * 1.1:  # Allow 10% overhead for multipart headers
                    self.send_json_response({"success": False, "error": "Uploaded payload is too large. Max allowed is 5MB."}, 400)
                    return

                body_bytes = self.rfile.read(content_length)
                fields, files = parse_multipart(content_type, body_bytes)

                category = fields.get('category')
                title = fields.get('title')
                description = fields.get('description', '')
                capacity = fields.get('capacity', '')
                image_file = files.get('image')

                if not category or not title or not image_file:
                    self.send_json_response({"success": False, "error": "Category, Title, and Image are required"}, 400)
                    return

                # Validate category
                allowed_categories = {'wedding', 'community', 'dining', 'terrace'}
                if category not in allowed_categories:
                    self.send_json_response({"success": False, "error": "Invalid hall category specified."}, 400)
                    return

                # Validate file size
                if len(image_file['content']) > max_size:
                    self.send_json_response({"success": False, "error": "Image file size exceeds the 5MB limit."}, 400)
                    return

                # Validate extension
                filename = image_file['filename']
                ext = os.path.splitext(filename)[1].lower()
                allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
                if ext not in allowed_extensions:
                    self.send_json_response({"success": False, "error": f"Invalid file type {ext}. Only JPG, PNG, WEBP allowed."}, 400)
                    return

                # Validate MIME content-type
                mime_type = image_file.get('content_type', '').lower()
                allowed_mimes = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
                if mime_type not in allowed_mimes:
                    self.send_json_response({"success": False, "error": "Invalid MIME type. Only image uploads allowed."}, 400)
                    return

                # Save file
                import uuid
                unique_filename = f"{uuid.uuid4().hex}{ext}"
                
                upload_dir = os.path.join(script_dir, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                filepath = os.path.join(upload_dir, unique_filename)
                with open(filepath, 'wb') as f:
                    f.write(image_file['content'])

                image_path = f"uploads/{unique_filename}"

                # Insert database record
                conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB
                )
                c = conn.cursor()
                c.execute('''
                    INSERT INTO showcase_photos (image_path, category, title, description, capacity)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (image_path, category, title, description, capacity))
                conn.commit()
                conn.close()

                self.send_json_response({"success": True, "message": "Photo uploaded successfully", "image_path": image_path})
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, 500)
            return

        # API Route: Delete Showcase Photo
        elif parsed_path.path == '/api/admin/photos/delete':
            passcode = self.headers.get('X-Admin-Passcode')
            if not passcode or passcode not in ACTIVE_SESSIONS:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            try:
                data = self.read_json_body()
                photo_id = data.get('id')

                if not photo_id:
                    self.send_json_response({"error": "Photo ID is required"}, 400)
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
                # Fetch filepath to delete from disk
                c.execute('SELECT image_path FROM showcase_photos WHERE id = %s', (photo_id,))
                photo = c.fetchone()

                if photo:
                    # Delete database record
                    c.execute('DELETE FROM showcase_photos WHERE id = %s', (photo_id,))
                    conn.commit()
                    conn.close()

                    # Delete from file system if it's in uploads directory
                    image_path = photo['image_path']
                    if image_path.startswith('uploads/'):
                        full_path = os.path.join(script_dir, image_path)
                        if os.path.exists(full_path):
                            try:
                                os.remove(full_path)
                            except Exception as fs_err:
                                print(f"Error removing physical photo file: {fs_err}")
                    
                    self.send_json_response({"success": True, "message": "Photo successfully deleted!"})
                else:
                    conn.close()
                    self.send_json_response({"error": "Photo not found"}, 404)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        # API Route: Change Admin Credentials
        elif parsed_path.path == '/api/admin/change-credentials':
            passcode = self.headers.get('X-Admin-Passcode')
            if not passcode or passcode not in ACTIVE_SESSIONS:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            username = ACTIVE_SESSIONS.get(passcode)
            if not username:
                username = 'admin'

            try:
                data = self.read_json_body()
                current_password = data.get('current_password')
                new_password = data.get('new_password')
                new_question = data.get('new_question')
                new_answer = data.get('new_answer')

                if not current_password or not new_password or not new_question or not new_answer:
                    self.send_json_response({"success": False, "error": "All fields are required"}, 400)
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
                # Verify current password
                c.execute('SELECT password_hash FROM admin_users WHERE username = %s', (username,))
                user = c.fetchone()

                if not user or not verify_password(current_password, user['password_hash']):
                    conn.close()
                    self.send_json_response({"success": False, "error": "Incorrect current password"}, 400)
                    return

                # Update password, question, and answer
                new_password_hash = hash_password(new_password)
                new_answer_hash = hash_security_answer(new_answer)

                c.execute('''
                    UPDATE admin_users 
                    SET password_hash = %s, security_question = %s, security_answer_hash = %s 
                    WHERE username = %s
                ''', (new_password_hash, new_question, new_answer_hash, username))
                conn.commit()
                conn.close()

                self.send_json_response({"success": True, "message": "Credentials updated successfully"})
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
        origin = self.get_cors_origin()
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Passcode')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Credentials', 'true')
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
