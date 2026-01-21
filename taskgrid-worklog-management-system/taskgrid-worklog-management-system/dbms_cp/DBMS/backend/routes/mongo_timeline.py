"""
Timeline and History Routes for TaskGrid
Tracks all actions and provides history view for all user roles
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from utils.mongo_db import timeline_col, users_col, tasks_col, subtasks_col, to_str_id, oid

mongo_timeline_bp = Blueprint('mongo_timeline', __name__)


# ---------- GET MY TIMELINE ----------
@mongo_timeline_bp.route('/timeline/my', methods=['GET'])
@jwt_required()
def get_my_timeline():
    """
    Get timeline entries for current user
    Query params:
    - days: number of days to look back (default: 30)
    - action_type: filter by specific action type
    - limit: max number of entries (default: 100)
    """
    try:
        uid = get_jwt_identity()
        
        # Get query parameters
        days = int(request.args.get('days', 30))
        action_type = request.args.get('action_type')
        limit = int(request.args.get('limit', 100))
        
        # Build query
        query = {'user_id': oid(uid)}
        
        # Filter by date range
        if days > 0:
            start_date = datetime.utcnow() - timedelta(days=days)
            query['timestamp'] = {'$gte': start_date}
        
        # Filter by action type
        if action_type:
            query['action_type'] = action_type
        
        # Fetch timeline entries
        cursor = timeline_col.find(query).sort('timestamp', -1).limit(limit)
        entries = []
        
        for entry in cursor:
            entry_dict = to_str_id(entry)
            
            # Add task info if present
            if entry.get('task_id'):
                task = tasks_col.find_one({'_id': oid(entry['task_id'])})
                if task:
                    entry_dict['task_title'] = task.get('title')
            
            # Add subtask info if present
            if entry.get('subtask_id'):
                subtask = subtasks_col.find_one({'_id': oid(entry['subtask_id'])})
                if subtask:
                    entry_dict['subtask_title'] = subtask.get('title')
            
            entries.append(entry_dict)
        
        return jsonify({
            'timeline': entries,
            'count': len(entries)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET TEAM TIMELINE (MANAGER) ----------
@mongo_timeline_bp.route('/timeline/team', methods=['GET'])
@jwt_required()
def get_team_timeline():
    """
    Get timeline for all team members (Manager/Admin view)
    Shows updates from team members assigned to tasks
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check permissions
        if user.get('role') not in ['admin', 'project_manager']:
            return jsonify({'error': 'Manager or Admin access required'}), 403
        
        # Get query parameters
        days = int(request.args.get('days', 30))
        limit = int(request.args.get('limit', 200))
        
        # Build query
        query = {}
        
        # Filter by date
        if days > 0:
            start_date = datetime.utcnow() - timedelta(days=days)
            query['timestamp'] = {'$gte': start_date}
        
        # Fetch entries
        cursor = timeline_col.find(query).sort('timestamp', -1).limit(limit)
        entries = []
        
        for entry in cursor:
            entry_dict = to_str_id(entry)
            
            # Add user info
            if entry.get('user_id'):
                entry_user = users_col.find_one({'_id': oid(entry['user_id'])})
                if entry_user:
                    entry_dict['user_name'] = f"{entry_user.get('first_name', '')} {entry_user.get('last_name', '')}".strip()
                    entry_dict['user_email'] = entry_user.get('email')
                    entry_dict['user_role'] = entry_user.get('role')
            
            # Add task info
            if entry.get('task_id'):
                task = tasks_col.find_one({'_id': oid(entry['task_id'])})
                if task:
                    entry_dict['task_title'] = task.get('title')
            
            # Add subtask info
            if entry.get('subtask_id'):
                subtask = subtasks_col.find_one({'_id': oid(entry['subtask_id'])})
                if subtask:
                    entry_dict['subtask_title'] = subtask.get('title')
            
            entries.append(entry_dict)
        
        return jsonify({
            'timeline': entries,
            'count': len(entries)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET TASK TIMELINE ----------
@mongo_timeline_bp.route('/timeline/task/<task_id>', methods=['GET'])
@jwt_required()
def get_task_timeline(task_id):
    """Get timeline for a specific task and its subtasks"""
    try:
        uid = get_jwt_identity()
        
        # Verify task exists
        task = tasks_col.find_one({'_id': oid(task_id)})
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Get query parameters
        limit = int(request.args.get('limit', 100))
        
        # Build query to include task and its subtasks
        query = {
            '$or': [
                {'task_id': oid(task_id)},
                {'subtask_id': {'$in': [
                    s['_id'] for s in subtasks_col.find({'task_id': oid(task_id)}, {'_id': 1})
                ]}}
            ]
        }
        
        # Fetch entries
        cursor = timeline_col.find(query).sort('timestamp', -1).limit(limit)
        entries = []
        
        for entry in cursor:
            entry_dict = to_str_id(entry)
            
            # Add user info
            if entry.get('user_id'):
                entry_user = users_col.find_one({'_id': oid(entry['user_id'])})
                if entry_user:
                    entry_dict['user_name'] = f"{entry_user.get('first_name', '')} {entry_user.get('last_name', '')}".strip()
            
            # Add subtask info if present
            if entry.get('subtask_id'):
                subtask = subtasks_col.find_one({'_id': oid(entry['subtask_id'])})
                if subtask:
                    entry_dict['subtask_title'] = subtask.get('title')
            
            entries.append(entry_dict)
        
        return jsonify({
            'task_title': task.get('title'),
            'timeline': entries,
            'count': len(entries)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET ADMIN TIMELINE (ALL ACTIVITIES) ----------
@mongo_timeline_bp.route('/timeline/admin', methods=['GET'])
@jwt_required()
def get_admin_timeline():
    """
    Get complete timeline of all activities (Admin only)
    Shows tasks, submissions, approvals, rejections, etc.
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if admin
        if user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get query parameters
        days = int(request.args.get('days', 30))
        action_type = request.args.get('action_type')
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 500))
        
        # Build query
        query = {}
        
        # Filter by date
        if days > 0:
            start_date = datetime.utcnow() - timedelta(days=days)
            query['timestamp'] = {'$gte': start_date}
        
        # Filter by action type
        if action_type:
            query['action_type'] = action_type
        
        # Filter by user
        if user_id:
            query['user_id'] = oid(user_id)
        
        # Fetch entries
        cursor = timeline_col.find(query).sort('timestamp', -1).limit(limit)
        entries = []
        
        for entry in cursor:
            entry_dict = to_str_id(entry)
            
            # Add user info
            if entry.get('user_id'):
                entry_user = users_col.find_one({'_id': oid(entry['user_id'])})
                if entry_user:
                    entry_dict['user_name'] = f"{entry_user.get('first_name', '')} {entry_user.get('last_name', '')}".strip()
                    entry_dict['user_email'] = entry_user.get('email')
                    entry_dict['user_role'] = entry_user.get('role')
            
            # Add task info
            if entry.get('task_id'):
                task = tasks_col.find_one({'_id': oid(entry['task_id'])})
                if task:
                    entry_dict['task_title'] = task.get('title')
            
            # Add subtask info
            if entry.get('subtask_id'):
                subtask = subtasks_col.find_one({'_id': oid(entry['subtask_id'])})
                if subtask:
                    entry_dict['subtask_title'] = subtask.get('title')
            
            entries.append(entry_dict)
        
        # Get statistics
        stats = {
            'total_entries': len(entries),
            'date_range_days': days,
            'action_types': {}
        }
        
        # Count by action type
        for entry in entries:
            action = entry.get('action_type', 'unknown')
            stats['action_types'][action] = stats['action_types'].get(action, 0) + 1
        
        return jsonify({
            'timeline': entries,
            'statistics': stats
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET TIMELINE STATISTICS ----------
@mongo_timeline_bp.route('/timeline/stats', methods=['GET'])
@jwt_required()
def get_timeline_stats():
    """Get statistics about timeline activities"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Role-based query
        if user.get('role') in ['admin', 'project_manager']:
            # Admin/Manager see all
            query = {'timestamp': {'$gte': start_date}}
        else:
            # Team members see only their own
            query = {'user_id': oid(uid), 'timestamp': {'$gte': start_date}}
        
        # Get all entries
        entries = list(timeline_col.find(query))
        
        # Calculate statistics
        stats = {
            'total_activities': len(entries),
            'date_range_days': days,
            'action_types': {},
            'daily_activity': {},
            'most_active_days': []
        }
        
        # Count by action type
        for entry in entries:
            action = entry.get('action_type', 'unknown')
            stats['action_types'][action] = stats['action_types'].get(action, 0) + 1
            
            # Count by day
            date_key = entry.get('timestamp', datetime.utcnow()).strftime('%Y-%m-%d')
            stats['daily_activity'][date_key] = stats['daily_activity'].get(date_key, 0) + 1
        
        # Find most active days
        sorted_days = sorted(stats['daily_activity'].items(), key=lambda x: x[1], reverse=True)
        stats['most_active_days'] = sorted_days[:7]  # Top 7 days
        
        return jsonify({'statistics': stats}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
