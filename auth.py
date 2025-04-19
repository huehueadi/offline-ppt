from flask import Blueprint, request, jsonify, session, redirect, url_for
from db import add_user, get_user_by_email
from werkzeug.security import check_password_hash
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if add_user(username, email, password):
        return jsonify({'message': 'Registration successful'}), 201
    else:
        return jsonify({'error': 'Username or email already exists'}), 409

@auth_bp.route('/login', methods=['POST'])
def login():
    """Log in a user."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Missing email or password'}), 400
    
    user = get_user_by_email(email)
    if user and check_password_hash(user[3], password):  # user[3] is password_hash
        session['user_id'] = user[0]  # user[0] is id
        session['username'] = user[1]  # user[1] is username
        return jsonify({'message': 'Login successful', 'username': user[1]}), 200
    else:
        return jsonify({'error': 'Invalid email or password'}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Log out the current user."""
    session.pop('user_id', None)
    session.pop('username', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@auth_bp.route('/check_auth', methods=['GET'])
def check_auth():
    """Check if user is authenticated."""
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'username': session.get('username')}), 200
    return jsonify({'authenticated': False}), 200