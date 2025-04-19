import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

def init_db():
    """Initialize SQLite database with users and presentations tables."""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Create presentations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS presentations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            download_url TEXT NOT NULL,
            topic TEXT NOT NULL,
            num_slides INTEGER NOT NULL,
            template_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(username, email, password):
    """Add a new user to the database."""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        cursor.execute('''
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        ''', (username, email, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username or email already exists
    finally:
        conn.close()

def get_user_by_email(email):
    """Retrieve a user by email."""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    return user  # Returns (id, username, email, password_hash) or None

def add_presentation(user_id, filename, download_url, topic, num_slides, template_id):
    """Add a presentation to the database."""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO presentations (user_id, filename, download_url, topic, num_slides, template_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, filename, download_url, topic, num_slides, template_id, datetime.now()))
    conn.commit()
    conn.close()

def get_user_presentations(user_id):
    """Retrieve all presentations for a user."""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, filename, download_url, topic, num_slides, template_id, created_at FROM presentations WHERE user_id = ?', (user_id,))
    presentations = cursor.fetchall()
    conn.close()
    return presentations  # List of tuples