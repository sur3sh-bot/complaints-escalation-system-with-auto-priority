import sqlite3
import re
import os
from flask import Flask, render_template, request, redirect, session, flash
from textblob import TextBlob
from rapidfuzz import process, fuzz

app = Flask(__name__)

# --- SECURITY ---
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

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

    conn.commit()
    conn.close()

# --- AI PRIORITY ENGINE ---
def calculate_priority(text):
    desc = re.sub(r'[^\w\s]', '', text.lower())

    score = 0

    # --- 1. CRITICAL EMERGENCY KEYWORDS ---
    emergency_keywords = [
        "fire", "alarm", "emergency", "danger", "gas leak",
        "short circuit", "sparking", "explosion"
    ]
    if any(k in desc for k in emergency_keywords):
        return "Urgent"

    # --- 2. INFRASTRUCTURE FAILURES (HIGH PRIORITY) ---
    high_keywords = [
        "lift", "elevator", "ac", "air conditioner",
        "electricity", "power", "water", "wifi",
        "internet", "server"
    ]
    if any(k in desc for k in high_keywords):
        score += 3

    # --- 3. FAILURE WORDS ---
    if any(w in desc for w in ['broken', 'not working', 'failed', 'down', 'leak']):
        score += 2

    # --- 4. SCALE IMPACT ---
    if any(w in desc for w in ['entire', 'whole', 'everyone', 'floor', 'block']):
        score += 2

    # --- 5. SENTIMENT (LOW WEIGHT) ---
    blob = TextBlob(desc)
    if blob.sentiment.polarity < -0.5:
        score += 1

    # --- FINAL DECISION ---
    if score >= 5:
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
    ''').fetchone()

    conn.close()

    return render_template('admin.html', complaints=complaints, stats=stats)


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

    conn.execute(
        'UPDATE complaints SET status = ? WHERE id = ?',
        (new_status, id)
    )

    conn.commit()
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


# --- RUN ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)