from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from bson.objectid import ObjectId

from utils.mongo_db import (
    users_col,
    projects_col,
    tasks_col,
    worklogs_col,
    to_str_id,
    oid,
)

mongo_data_bp = Blueprint('mongo_data', __name__)

# ---------- Utility functions ----------

def _parse_datetime(s):
    """Convert string (YYYY-MM-DD) to datetime.datetime for MongoDB."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


# ---------- PROJECT ROUTES ----------

@mongo_data_bp.route('/projects', methods=['GET'])
@jwt_required()
def get_projects():
    try:
        uid = oid(get_jwt_identity())
        user = users_col.find_one({'_id': uid})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Admin or Manager → can view all projects
        if user.get('role') in ['admin', 'project_manager']:
            cursor = projects_col.find({})
        else:
            # Normal user → only see own or assigned projects
            project_ids = set()
            # tasks may store project_id as ObjectId or as string — normalize via oid()
            for t in tasks_col.find({'$or': [{'created_by': uid}, {'assigned_to': uid}]}):
                pid = t.get('project_id')
                if not pid:
                    continue
                if isinstance(pid, ObjectId):
                    project_ids.add(pid)
                else:
                    pid_oid = oid(pid)
                    if pid_oid:
                        project_ids.add(pid_oid)
            # If project_ids empty this query will still allow owner matches
            cursor = projects_col.find({
                '$or': [
                    {'owner_id': uid},
                    {'_id': {'$in': list(project_ids)}} if project_ids else {'_id': {'$exists': False}}
                ]
            })

        items = []
        for p in cursor:
            d = to_str_id(p)  # ✅ convert _id to string for JSON

            # Convert any remaining ObjectId fields to string
            if 'owner_id' in d and isinstance(d['owner_id'], ObjectId):
                d['owner_id'] = str(d['owner_id'])

            # Count tasks where project_id may be stored as ObjectId or string
            d['task_count'] = tasks_col.count_documents({
                '$or': [
                    {'project_id': p['_id']},
                    {'project_id': str(p['_id'])},
                    {'project_id': {'$exists': False}}  # keeps behavior when none; optional
                ]
            })

            # ✅ Fix: ensure correct ObjectId lookup for owner
            owner = None
            if p.get('owner_id'):
                owner = users_col.find_one({'_id': oid(p.get('owner_id'))})

            d['owner_name'] = (
                f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
                if owner else None
            )

            items.append(d)

        return jsonify({'projects': items}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mongo_data_bp.route('/projects', methods=['POST'])
@jwt_required()
def create_project():
    try:
        uid = oid(get_jwt_identity())
        user = users_col.find_one({'_id': uid})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'error': 'Project name is required'}), 400

        # Convert date fields safely
        start_date = _parse_datetime(data.get('start_date'))
        end_date = _parse_datetime(data.get('end_date'))
        deadline = _parse_datetime(data.get('deadline'))

        doc = {
            'name': data['name'],
            'description': data.get('description', ''),
            'status': data.get('status', 'active'),
            'priority': data.get('priority', 'medium'),
            'start_date': start_date,
            'end_date': end_date,
            'deadline': deadline,
            'budget': float(data.get('budget', 0.0)),
            'owner_id': uid,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }

        # Insert into MongoDB
        res = projects_col.insert_one(doc)
        created = projects_col.find_one({'_id': res.inserted_id})

        # ✅ Convert ObjectIds to strings for JSON
        d = to_str_id(created)
        d['owner_id'] = str(d.get('owner_id')) if d.get('owner_id') else None
        d['task_count'] = tasks_col.count_documents({
            '$or': [
                {'project_id': created['_id']},
                {'project_id': str(created['_id'])}
            ]
        })

        # Add readable owner name
        owner = users_col.find_one({'_id': uid})
        d['owner_name'] = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip() if owner else None

        return jsonify({'message': 'Project created successfully', 'project': d}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mongo_data_bp.route('/projects/<string:project_id>', methods=['PUT'])
@jwt_required()
def update_project(project_id):
    try:
        uid = oid(get_jwt_identity())
        user = users_col.find_one({'_id': uid})
        proj = projects_col.find_one({'_id': oid(project_id)})

        if not proj:
            return jsonify({'error': 'Project not found'}), 404
        if user.get('role') not in ['admin', 'project_manager'] and proj.get('owner_id') != uid:
            return jsonify({'error': 'Access denied'}), 403

        data = request.get_json() or {}
        updates = {}

        # Basic fields
        for f in ['name', 'description', 'status', 'priority', 'budget']:
            if f in data:
                updates[f] = data[f]

        # Date fields
        for date_field in ['start_date', 'end_date', 'deadline']:
            if date_field in data:
                updates[date_field] = _parse_datetime(data[date_field]) if data[date_field] else None

        if updates:
            updates['updated_at'] = datetime.utcnow()
            projects_col.update_one({'_id': proj['_id']}, {'$set': updates})

        # Fetch updated project
        proj = projects_col.find_one({'_id': proj['_id']})
        d = to_str_id(proj)
        d['task_count'] = tasks_col.count_documents({'project_id': proj['_id']})

        owner = None
        if proj.get('owner_id'):
            owner = users_col.find_one({'_id': oid(proj.get('owner_id'))})

        d['owner_name'] = (
            f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
            if owner else None
        )

        return jsonify({'message': 'Project updated successfully', 'project': d}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- USER ROUTES ----------

@mongo_data_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    """Get list of all users (for assigning tasks, viewing team members)"""
    try:
        uid = oid(get_jwt_identity())
        user = users_col.find_one({'_id': uid})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get all active users
        cursor = users_col.find({'is_active': True})
        
        users_list = []
        for u in cursor:
            user_data = to_str_id(u)
            # Remove sensitive data
            user_data.pop('password_hash', None)
            # Add name field for frontend compatibility
            user_data['name'] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get('username', 'Unknown')
            users_list.append(user_data)

        return jsonify({'users': users_list}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
