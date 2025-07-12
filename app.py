from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
import sqlite3
import os
import base64
import math
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_in_production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database initialization
def init_db():
    conn = sqlite3.connect('skillswap.db')
    cursor = conn.cursor()
    
    # Users table for authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User profiles table for skill sharing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            skills_offer TEXT NOT NULL,
            skills_wanted TEXT NOT NULL,
            availability_start TEXT NOT NULL,
            availability_end TEXT NOT NULL,
            profile_type TEXT NOT NULL,
            profile_picture TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Skill requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS skill_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            requested_user_id INTEGER NOT NULL,
            skill_requested TEXT NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (requester_id) REFERENCES users (id),
            FOREIGN KEY (requested_user_id) REFERENCES users (id)
        )
    ''')
    
    # Create default admin user if it doesn't exist
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        password_hash = generate_password_hash('admin123')
        cursor.execute('INSERT INTO users (name, username, email, password) VALUES (?, ?, ?, ?)',
                      ('Administrator', 'admin', 'admin@skillswap.com', password_hash))
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('skillswap.db')
    conn.row_factory = sqlite3.Row
    return conn

# Authentication Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', 
                           (identifier, identifier)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
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
            existing = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', 
                                  (username, email)).fetchone()
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Dashboard and Profile Management Routes
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user has a profile
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                          (session['user_id'],)).fetchone()
    conn.close()
    
    if not profile:
        return redirect(url_for('create_profile'))
    
    return redirect(url_for('browse_skills'))

@app.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            location = request.form.get('location', '').strip()
            skills_offer = ','.join(request.form.getlist('skills_offer'))
            skills_wanted = ','.join(request.form.getlist('skills_wanted'))
            availability_start = request.form.get('availability_start')
            availability_end = request.form.get('availability_end')
            profile_type = request.form.get('profile_type')
            
            # Handle profile picture
            profile_picture = None
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    # Convert to base64 for database storage
                    profile_picture = base64.b64encode(file.read()).decode('utf-8')
            
            # Validate required fields
            if not all([name, location, skills_offer, skills_wanted, availability_start, availability_end, profile_type]):
                return jsonify({'success': False, 'message': 'All fields are required'})
            
            # Save to database
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO user_profiles 
                (user_id, name, location, skills_offer, skills_wanted, availability_start, availability_end, profile_type, profile_picture)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], name, location, skills_offer, skills_wanted, 
                  availability_start, availability_end, profile_type, profile_picture))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Profile created successfully!'})
        
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    
    return render_template('create_profile.html')

# Skill Browsing Routes
@app.route('/browse')
def browse_skills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('browse_skills.html')

@app.route('/api/users')
def get_users():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    availability = request.args.get('availability', '', type=str)
    per_page = 6  # Users per page
    
    conn = get_db_connection()
    
    # Build query with search and availability filters
    query = '''SELECT up.id, up.name, up.location, up.skills_offer, up.skills_wanted, 
                      up.availability_start, up.availability_end, up.profile_picture, up.user_id
               FROM user_profiles up 
               WHERE up.user_id != ? '''
    params = [session['user_id']]
    
    if search:
        query += " AND (up.name LIKE ? OR up.skills_offer LIKE ? OR up.skills_wanted LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if availability:
        query += " AND ? BETWEEN up.availability_start AND up.availability_end"
        params.append(availability)
    
    # Count total users for pagination
    count_query = query.replace("SELECT up.id, up.name, up.location, up.skills_offer, up.skills_wanted, up.availability_start, up.availability_end, up.profile_picture, up.user_id", "SELECT COUNT(*)")
    total_users = conn.execute(count_query, params).fetchone()[0]
    
    # Add pagination
    offset = (page - 1) * per_page
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    users = conn.execute(query, params).fetchall()
    conn.close()
    
    # Calculate pagination info
    total_pages = math.ceil(total_users / per_page)
    
    # Convert users to dictionaries and process skills
    users_list = []
    for user in users:
        user_dict = dict(user)
        user_dict['skills_offered'] = user_dict['skills_offer'].split(',') if user_dict['skills_offer'] else []
        user_dict['skills_wanted'] = user_dict['skills_wanted'].split(',') if user_dict['skills_wanted'] else []
        users_list.append(user_dict)
    
    return jsonify({
        'users': users_list,
        'pagination': {
            'page': page,
            'total_pages': total_pages,
            'total_users': total_users,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    })

@app.route('/profile/<int:user_id>')
def profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get user profile details
    user = conn.execute('''
        SELECT up.id, up.name, up.location, up.skills_offer as skills_offered, up.skills_wanted, 
               up.availability_start, up.availability_end, up.profile_picture, up.user_id
        FROM user_profiles up 
        WHERE up.id = ?
    ''', (user_id,)).fetchone()
    
    conn.close()
    
    if user is None:
        return "User not found", 404
    
    # Convert to dictionary and process skills
    user_dict = dict(user)
    user_dict['skills_offered'] = user_dict['skills_offered'].split(',') if user_dict['skills_offered'] else []
    user_dict['skills_wanted'] = user_dict['skills_wanted'].split(',') if user_dict['skills_wanted'] else []
    
    # Generate a random rating for demo purposes
    import random
    rating = round(random.uniform(3.5, 5.0), 1)
    
    return render_template('profile.html', user=user_dict, rating=rating)

@app.route('/my_profile')
def my_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                          (session['user_id'],)).fetchone()
    conn.close()
    
    if not profile:
        return redirect(url_for('create_profile'))
    
    # Convert to dictionary and process skills
    profile_dict = dict(profile)
    profile_dict['skills_offered'] = profile_dict['skills_offer'].split(',') if profile_dict['skills_offer'] else []
    profile_dict['skills_wanted'] = profile_dict['skills_wanted'].split(',') if profile_dict['skills_wanted'] else []
    
    return render_template('my_profile.html', profile=profile_dict)

# Skill Request Routes
@app.route('/api/request_skill', methods=['POST'])
def request_skill():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    requested_user_id = data.get('user_id')
    skill_requested = data.get('skill')
    message = data.get('message', '')
    
    if not requested_user_id or not skill_requested:
        return jsonify({'status': 'error', 'message': 'Missing required fields'})
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO skill_requests (requester_id, requested_user_id, skill_requested, message)
        VALUES (?, ?, ?, ?)
    ''', (session['user_id'], requested_user_id, skill_requested, message))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Request sent successfully!'})

@app.route('/my_requests')
def my_requests():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get requests made by current user
    sent_requests = conn.execute('''
        SELECT sr.*, up.name as requested_user_name 
        FROM skill_requests sr
        JOIN user_profiles up ON sr.requested_user_id = up.user_id
        WHERE sr.requester_id = ?
        ORDER BY sr.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    # Get requests received by current user
    received_requests = conn.execute('''
        SELECT sr.*, up.name as requester_name 
        FROM skill_requests sr
        JOIN user_profiles up ON sr.requester_id = up.user_id
        WHERE sr.requested_user_id = ?
        ORDER BY sr.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('my_requests.html', 
                         sent_requests=sent_requests, 
                         received_requests=received_requests)

# File serving route
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
