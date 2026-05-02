import sqlite3 #to handle database operations
import re #for text preprocessing in AI priority engine
import os #to handle environment variables for security
from flask import Flask, render_template, request, redirect, session, flash #for web framework and user session management
from textblob import TextBlob #for sentiment analysis in AI priority engine

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

def init_db(): #to initialize the database and create necessary tables if they don't exist
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
def calculate_priority(text): #to analyze the complaint description and assign a priority level based on keywords, sentiment, and scale
    #  FIXED preprocessing
    desc = re.sub(r'[^\w\s]', ' ', text.lower())
    score = 0

    #  FIXED emergency block (INSIDE function)
    emergency_keywords = [
        "fire", "alarm", "gas leak", "explosion",
        "sparking", "sparks", "short circuit"
    ]

    if any(k in desc for k in emergency_keywords):
        return "Urgent"

    # Infrastructure
    if any(k in desc for k in ["lift", "ac", "water", "electricity", "wifi"]):
        score += 2

    # Failure
    if any(w in desc for w in ['broken', 'not working', 'failed', 'down', 'leak']):
        score += 2

    # Scale
    if any(w in desc for w in ['entire', 'whole', 'everyone']):
        score += 3

    # Sentiment
    blob = TextBlob(desc)
    if blob.sentiment.polarity < -0.5:
        score += 1

    # Final decision
    if score >= 6:
        return "Urgent"
    elif score >= 3:
        return "High"
    else:
        return "Low"

# --- DEPARTMENT DETECTION ---
def detect_department(text): #to analyze the complaint description and determine which department should handle it based on keywords
    mapping = {
        "Electrical": ["light", "electric", "fan"],
        "Plumbing": ["water", "leak", "tap"],
        "IT": ["wifi", "internet"],
        "Maintenance": ["broken", "repair"]
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

    return redirect('/admin' if session['user_role'] == 'admin' else '/student')


@app.route('/login', methods=['GET', 'POST']) #to handle user login and role assignment (admin or student)
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

    conn = get_db_connection()

    my_ids = session.get('my_complaints', [])

    if my_ids:
        placeholders = ','.join(['?'] * len(my_ids))
        query = f"SELECT * FROM complaints WHERE id IN ({placeholders}) ORDER BY created_at DESC"
        complaints = conn.execute(query, my_ids).fetchall()
    else:
        complaints = []

    conn.close()

    return render_template('student.html', complaints=complaints)


@app.route('/admin') #to display the admin portal with dynamic filtering options and department analytics, allowing admins to efficiently manage complaints and gain insights into departmental performance
def admin_portal():
    if session.get('user_role') != 'admin':
        return redirect('/login')

    # --- FILTER INPUTS ---
    status = request.args.get('status')
    severity = request.args.get('severity')
    q = request.args.get('q')

    conn = get_db_connection()

    # --- DYNAMIC QUERY ---
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if severity:
        query += " AND severity = ?"
        params.append(severity)

    if q:
        query += " AND description LIKE ?"
        params.append(f"%{q}%")

    query += " ORDER BY created_at DESC"

    complaints = conn.execute(query, params).fetchall()

    # ---  NEW: DEPARTMENT ANALYTICS ---
    dept_data = conn.execute('''
        SELECT department, COUNT(*) as count
        FROM complaints
        GROUP BY department
    ''').fetchall()

    # --- STATS (ACTIVE ONLY) ---
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

    return render_template(
        'admin.html',
        complaints=complaints,
        stats=stats,
        filters={
            "status": status,
            "severity": severity,
            "q": q
        },
        dept_data=dept_data   #  NEW DATA FOR CHART
    )

# --- STATUS PAGES ---
@app.route('/open') #to display complaints filtered by "Open" status, allowing admins to focus on new issues that need attention
def open_complaints():
    conn = get_db_connection()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status = 'Open' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template('status_page.html', complaints=complaints,
                           title="Open Complaints", page_type="open")


@app.route('/in-progress') #to display complaints filtered by "In Progress" status, allowing admins to track ongoing issues and their progress
def in_progress_complaints():
    conn = get_db_connection()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status = 'In Progress' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template('status_page.html', complaints=complaints,
                           title="In Progress Complaints", page_type="progress")


@app.route('/resolved') #to display complaints filtered by "Resolved" status, allowing admins to review completed issues and maintain a record of past complaints
def resolved_complaints():
    conn = get_db_connection()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status = 'Resolved' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template('status_page.html', complaints=complaints,
                           title="Resolved Complaints", page_type="resolved")


# --- ADD ---
@app.route('/add', methods=['POST'])
def add_complaint():
    text = request.form.get('description', '').strip()

    if not text or len(text) < 10:
        flash("Complaint must be at least 10 characters")
        return redirect('/student')

    priority = calculate_priority(text)
    dept = detect_department(text)

    conn = get_db_connection()

    conn.execute(
        'INSERT INTO complaints (description, severity, department) VALUES (?, ?, ?)',
        (text, priority, dept)
    )

    #  MUST be inside function 
    last_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

    if 'my_complaints' not in session:
        session['my_complaints'] = []

    session['my_complaints'].append(last_id)
    session.modified = True

    conn.commit()
    conn.close()
    flash("Complaint submitted successfully")

    return redirect('/student')


# --- UPDATE ---
@app.route('/update_status/<int:id>/<string:new_status>') #to handle the updating of complaint status by admins, ensuring that changes are logged in the history table for audit purposes and allowing for redirection to the appropriate status page after the update
def update_status(id, new_status):
    if new_status not in VALID_STATUSES:
        return "Invalid status", 400

    conn = get_db_connection()

    row = conn.execute(
        'SELECT status FROM complaints WHERE id = ?', (id,)
    ).fetchone()

    if not row:
        return "Not found", 404

    old_status = row['status']

    conn.execute("BEGIN")

    conn.execute(
        'UPDATE complaints SET status = ? WHERE id = ?',
        (new_status, id)
    )

    conn.execute(
        '''INSERT INTO complaint_history (complaint_id, old_status, new_status)
           VALUES (?, ?, ?)''',
        (id, old_status, new_status)
    )

    conn.commit()
    conn.close()

    if new_status == "In Progress":
        return redirect('/in-progress')
    elif new_status == "Resolved":
        return redirect('/resolved')
    else:
        return redirect('/open')


# --- DELETE ---
@app.route('/delete/<int:id>') #to handle the deletion of complaints by admins, ensuring that the complaint is removed from the database and the admin is redirected back to the main admin page to see the updated list of complaints
def delete_complaint(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM complaints WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect('/admin')


# --- HISTORY ---
@app.route('/history/<int:id>')
def history(id):
    conn = get_db_connection()

    history = conn.execute('''
        SELECT old_status, new_status, changed_at
        FROM complaint_history
        WHERE complaint_id = ?
        ORDER BY changed_at DESC
    ''', (id,)).fetchall()

    conn.close()
    return render_template('history.html', history=history)


# --- LOGOUT ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# --- RUN ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)