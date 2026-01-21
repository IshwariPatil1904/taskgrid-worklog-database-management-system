from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash

from utils.mongo_db import users_col, to_str_id, oid

mongo_auth_bp = Blueprint('mongo_auth', __name__)

# ------------------ Helper Function ------------------ #

def _user_public(doc):
    """Convert MongoDB document to public-safe user dict"""
    d = to_str_id(doc)
    if not d:
        return None
    d.pop('password_hash', None)
    return d


# ------------------ REGISTER ------------------ #
@mongo_auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        required = ['username', 'email', 'password', 'first_name', 'last_name']
        for f in required:
            if not data.get(f):
                return jsonify({'error': f'{f} is required'}), 400

        # ✅ Use the collection directly (not callable)
        users = users_col

        # Check uniqueness
        if users.count_documents({'username': data['username']}, limit=1):
            return jsonify({'error': 'Username already exists'}), 400
        if users.count_documents({'email': data['email']}, limit=1):
            return jsonify({'error': 'Email already exists'}), 400

        doc = {
            'username': data['username'],
            'email': data['email'],
            'password_hash': generate_password_hash(data['password']),
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'role': data.get('role', 'team_member'),
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }

        res = users.insert_one(doc)
        created = users.find_one({'_id': res.inserted_id})

        return jsonify({
            'message': 'User registered successfully',
            'user': _user_public(created)
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ------------------ LOGIN ------------------ #
@mongo_auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        users = users_col
        user = users.find_one({'username': username})

        if not user or not check_password_hash(user.get('password_hash', ''), password):
            return jsonify({'error': 'Invalid username or password'}), 401

        if not user.get('is_active', True):
            return jsonify({'error': 'Account is deactivated'}), 401

        access_token = create_access_token(
            identity=str(user['_id']),
            expires_delta=timedelta(days=1)
        )

        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'user': _user_public(user)
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ------------------ PROFILE (GET) ------------------ #
@mongo_auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        uid = get_jwt_identity()
        users = users_col
        user = users.find_one({'_id': oid(uid)})

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({'user': _user_public(user)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ------------------ PROFILE (UPDATE) ------------------ #
@mongo_auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        uid = get_jwt_identity()
        users = users_col
        user = users.find_one({'_id': oid(uid)})

        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        updates = {}

        if 'first_name' in data:
            updates['first_name'] = data['first_name']
        if 'last_name' in data:
            updates['last_name'] = data['last_name']
        if 'email' in data:
            # Ensure uniqueness
            existing = users.find_one({'email': data['email'], '_id': {'$ne': oid(uid)}})
            if existing:
                return jsonify({'error': 'Email already exists'}), 400
            updates['email'] = data['email']

        if not updates:
            return jsonify({'message': 'No changes'}), 200

        updates['updated_at'] = datetime.utcnow()
        users.update_one({'_id': oid(uid)}, {'$set': updates})
        user = users.find_one({'_id': oid(uid)})

        return jsonify({
            'message': 'Profile updated successfully',
            'user': _user_public(user)
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ------------------ CHANGE PASSWORD ------------------ #
@mongo_auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    try:
        uid = get_jwt_identity()
        users = users_col
        user = users.find_one({'_id': oid(uid)})

        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'error': 'Current password and new password are required'}), 400

        if not check_password_hash(user.get('password_hash', ''), current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400

        users.update_one(
            {'_id': oid(uid)},
            {
                '$set': {
                    'password_hash': generate_password_hash(new_password),
                    'updated_at': datetime.utcnow()
                }
            }
        )

        return jsonify({'message': 'Password changed successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
