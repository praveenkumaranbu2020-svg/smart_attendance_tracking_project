# Smart Attendance Tracking System

A beginner-friendly CSE final-year project using Flask + SQLite.

## Features
- Faculty/Admin login
- Student registration
- Daily attendance marking
- Duplicate attendance prevention
- Attendance percentage calculation
- Student attendance history
- Dashboard statistics

## Default login
Username: admin
Password: admin123

Change the secret key and default password before deployment.

## Run
1. Install Python 3.10+
2. Open terminal in this folder
3. Create a virtual environment:
   python -m venv venv
4. Activate it:
   Windows: venv\Scripts\activate
   Linux/macOS: source venv/bin/activate
5. Install packages:
   pip install -r requirements.txt
6. Run:
   python app.py
7. Open:
   http://127.0.0.1:5000

The SQLite database `attendance.db` is created automatically.
