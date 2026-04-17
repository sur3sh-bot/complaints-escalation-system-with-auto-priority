# 🚀 Web-based Complaint Escalation System

A full-stack web application built using **Flask (Python)** and **SQLite** that allows students to lodge complaints and administrators to manage, track, and analyze them efficiently.

---

## 📌 Features

### 👨‍🎓 Student Portal

* Submit complaints with description
* Automatic **AI-based priority detection**
* View **real-time status updates**
* Track submitted complaints (Open → In Progress → Resolved)

---

### 🛠️ Admin Dashboard

* View all complaints in a structured table
* Update complaint status
* Delete complaints
* View **status history (audit trail)**
* Filter complaints by:

  * Status
  * Priority
  * Search keywords

---

### 📊 Analytics Dashboard

* Pie chart: Priority distribution
* Bar chart: Department-wise complaints
* Live statistics:

  * Urgent / High / Low
  * Total active complaints

---

### 🤖 AI Priority Engine

Automatically classifies complaints using:

* Keyword detection (fire, leak, explosion, etc.)
* Sentiment analysis (TextBlob)
* Weighted scoring logic

---

### 🧾 Complaint Lifecycle

```text
Open → In Progress → Resolved
```

---

## 🧠 DBMS Concepts Used

* **CRUD Operations** (Create, Read, Update, Delete)
* **Filtering & Searching** using SQL (`WHERE`, `LIKE`)
* **Aggregation** (`GROUP BY`, `COUNT`)
* **Audit Logging** (`complaint_history` table)
* **Session Management**
* **Relational Database Design**

---

## 🏗️ Tech Stack

* **Backend:** Flask (Python)
* **Database:** SQLite
* **Frontend:** HTML, CSS, Jinja2
* **Charts:** Chart.js
* **AI Tools:** TextBlob, RapidFuzz

---

## 📁 Project Structure

```
project/
│
├── app.py
├── complaints.db
├── templates/
│   ├── login.html
│   ├── student.html
│   ├── admin.html
│   ├── status_page.html
│   └── history.html
```

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/complaint-system.git
cd complaint-system
```

---

### 2️⃣ Install dependencies

```bash
pip install flask textblob rapidfuzz
```

---

### 3️⃣ Run the application

```bash
python app.py
```

---

### 4️⃣ Open in browser

```
http://127.0.0.1:5000
```

---

## 🔐 Demo Credentials

| Role    | Access          |
| ------- | --------------- |
| Student | Direct login    |
| Admin   | Password: `123` |

---

## 🔄 Live Updates

The system supports **auto-refreshing complaint status** using polling (JavaScript), enabling near real-time updates without manual refresh.

---

## ✨ Unique Highlights

* AI-powered complaint prioritization
* Role-based access control (RBAC)
* Real-time status tracking
* Analytics dashboard with visual insights
* Complaint history tracking (audit system)

---

## 📸 Screenshots

> Add your screenshots here (Admin Dashboard, Student Portal, Analytics)

---

## 📈 Future Improvements

* Email/SMS notifications
* Authentication system (multi-user login)
* Role-based department assignment
* REST API integration
* Deployment on cloud (Render / AWS)

---

## 👨‍💻 Author

**Suresh Naidu**

---

## 📄 License

This project is for academic and learning purposes.

---

# ⭐ If you like this project, consider giving it a star!

