import sqlite3
import re
import os
from flask import Flask, render_template, request, redirect, session, flash
from textblob import TextBlob
from rapidfuzz import process, fuzz

app = Flask(__name__)

# --- SECURITY ---
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123")

DB_FILE = "complaints.db"

VALID_STATUSES = ['Open', 'In Progress', 'Resolved']

# --- DATABASE ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'Low',
            status TEXT DEFAULT 'Open',
            department TEXT DEFAULT 'General',
            assigned_to TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
CREATE TABLE IF NOT EXISTS complaint_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER,
    old_status TEXT,
    new_status TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

    conn.commit()
    conn.close()

# --- AI PRIORITY ENGINE ---
def calculate_priority(text):
    desc = re.sub(r'[^\w\s]', '', text.lower())

    score = 0

    # --- 1. EMERGENCY → DIRECT URGENT ---
    emergency_keywords = [
        "fire", "alarm", "gas leak", "explosion",
        "sparking", "short circuit"
    ]
    if any(k in desc for k in emergency_keywords):
        return "Urgent"

    # --- 2. INFRASTRUCTURE (IMPORTANT BUT NOT ALWAYS URGENT) ---
    infra_keywords = [
        "lift", "elevator", "ac", "air conditioner",
        "water", "electricity", "power", "wifi", "internet"
    ]
    if any(k in desc for k in infra_keywords):
        score += 2   # ↓ reduced from 3

    # --- 3. FAILURE WORDS ---
    if any(w in desc for w in ['broken', 'not working', 'failed', 'down', 'leak']):
        score += 2

    # --- 4. SCALE IMPACT ---
    if any(w in desc for w in ['entire', 'whole', 'everyone', 'block', 'floor']):
        score += 2

    # --- 5. SENTIMENT (VERY LOW IMPACT) ---
    blob = TextBlob(desc)
    if blob.sentiment.polarity < -0.5:
        score += 1

    # --- FINAL DECISION ---
    if score >= 6:
        return "Urgent"
    elif score >= 3:
        return "High"
    else:
        return "Low"

# --- DEPARTMENT DETECTION ---
def detect_department(text):
    mapping = {
        "Electrical": ["light", "electric", "power", "fan"],
        "Plumbing": ["water", "leak", "pipe", "tap"],
        "IT": ["wifi", "internet", "server", "network"],
        "Maintenance": ["broken", "repair", "damage"]
    }

    text = text.lower()

    for dept, keywords in mapping.items():
        if any(k in text for k in keywords):
            return dept

    return "General"

# --- ROUTES ---

@app.route('/')
def home():
    if 'user_role' not in session:
        return redirect('/login')

    if session['user_role'] == 'admin':
        return redirect('/admin')

    return redirect('/student')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role', '').strip().lower()

        if role == 'admin':
            password = request.form.get('password', '')

            if password == ADMIN_PASSWORD:
                session['user_role'] = 'admin'
                return redirect('/admin')
            else:
                flash("Invalid admin password")
                return redirect('/login')

        else:
            session['user_role'] = 'student'
            return redirect('/student')

    return render_template('login.html')


@app.route('/student')
def student_portal():
    if session.get('user_role') != 'student':
        return redirect('/login')

    return render_template('student.html')


@app.route('/admin')
def admin_portal():
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()

    complaints = conn.execute(
        'SELECT * FROM complaints ORDER BY created_at DESC'
    ).fetchall()

    stats = conn.execute('''
    SELECT 
        SUM(CASE WHEN severity = 'Urgent' THEN 1 ELSE 0 END) as urgent_count,
        SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) as high_count,
        SUM(CASE WHEN severity = 'Low' THEN 1 ELSE 0 END) as low_count,
        COUNT(*) as total_count
    FROM complaints
    WHERE status != 'Resolved'
''').fetchone()

    conn.close()

    return render_template('admin.html', complaints=complaints, stats=stats)

@app.route('/open')
def open_complaints():
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status = 'Open' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template('status_page.html',
                       complaints=complaints,
                       title="Open Complaints",
                       page_type="open")


@app.route('/in-progress')
def in_progress_complaints():
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status = 'In Progress' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template('status_page.html',
                       complaints=complaints,
                       title="Resolved Complaints",
                       page_type="resolved")


@app.route('/resolved')
def resolved_complaints():
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status = 'Resolved' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template('status_page.html', complaints=complaints, title="Resolved Complaints")




@app.route('/add', methods=['POST'])
def add_complaint():
    user_text = request.form.get('description', '').strip()

    # --- VALIDATION ---
    if not user_text or len(user_text) < 10:
        flash("Complaint must be at least 10 characters.")
        return redirect('/student')

    if len(user_text) > 500:
        flash("Complaint too long (max 500 characters).")
        return redirect('/student')

    # --- AI PROCESSING ---
    priority = calculate_priority(user_text)
    department = detect_department(user_text)

    conn = get_db_connection()

    conn.execute(
        'INSERT INTO complaints (description, severity, department) VALUES (?, ?, ?)',
        (user_text, priority, department)
    )

    conn.commit()
    conn.close()

    flash(f"Complaint submitted! Priority: {priority}, Department: {department}")

    return redirect('/student')


@app.route('/update_status/<int:id>/<string:new_status>')
def update_status(id, new_status):
    if session.get('user_role') != 'admin':
        return redirect('/login')

    if new_status not in VALID_STATUSES:
        return "Invalid status", 400

    conn = get_db_connection()

    # 1) Fetch current (old) status
    row = conn.execute(
        'SELECT status FROM complaints WHERE id = ?', (id,)
    ).fetchone()

    if not row:
        conn.close()
        return "Complaint not found", 404

    old_status = row['status']

    # Avoid redundant writes (nice touch)
    if old_status == new_status:
        conn.close()
        return redirect('/admin')

    # 2) TRANSACTION (ACID - atomic)
    try:
        conn.execute("BEGIN")

        # Update main table
        conn.execute(
            'UPDATE complaints SET status = ? WHERE id = ?',
            (new_status, id)
        )

        # Insert history row
        conn.execute(
            '''INSERT INTO complaint_history (complaint_id, old_status, new_status)
               VALUES (?, ?, ?)''',
            (id, old_status, new_status)
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Error: {e}", 500

    conn.close()
    return redirect('/admin')


@app.route('/delete/<int:id>')
def delete_complaint(id):
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()

    conn.execute(
        'DELETE FROM complaints WHERE id = ?',
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect('/admin')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/history/<int:complaint_id>')
def view_history(complaint_id):
    if session.get('user_role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()

    history = conn.execute('''
        SELECT old_status, new_status, changed_at
        FROM complaint_history
        WHERE complaint_id = ?
        ORDER BY changed_at DESC
    ''', (complaint_id,)).fetchall()

    conn.close()

    return render_template('history.html', history=history)


# --- RUN ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)