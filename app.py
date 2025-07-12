from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_db_connection()
        conn.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            );
        ''')
        password_hash = generate_password_hash('dev')
        conn.execute('INSERT INTO users (name, username, email, password) VALUES (?, ?, ?, ?)',
                     ('Developer', 'dev', 'dev@example.com', password_hash))
        conn.commit()
        conn.close()

# Initialize database on import
init_db()

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (identifier, identifier)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('ui'))
        else:
            error = 'Invalid credentials'
            return render_template('login.html', error=error)
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm']
        error = None
        if password != confirm:
            error = 'Passwords do not match'
        else:
            conn = get_db_connection()
            existing = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
            if existing:
                error = 'Username or email already taken'
            else:
                password_hash = generate_password_hash(password)
                conn.execute('INSERT INTO users (name, username, email, password) VALUES (?, ?, ?, ?)',
                             (name, username, email, password_hash))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            conn.close()
        return render_template('signup.html', error=error)
    return render_template('signup.html')

@app.route('/ui')
def ui():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('ui.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
