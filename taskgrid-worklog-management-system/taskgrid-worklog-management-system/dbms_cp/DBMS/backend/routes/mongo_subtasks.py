"""
Subtask Management Routes for TaskGrid
Handles subtask creation, distribution, and percentage allocation by Project Managers
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from utils.mongo_db import tasks_col, users_col, subtasks_col, timeline_col, notifications_col, to_str_id, oid
from utils.notification_helper import send_subtask_assigned_notification

mongo_subtasks_bp = Blueprint('mongo_subtasks', __name__)

# ---------- Helper Functions ----------
def create_notification(user_id, notification_type, title, message, task_id=None, subtask_id=None):
    """Create a notification for a user and send email"""
    notification = {
        'user_id': oid(user_id),
        'type': notification_type,
        'title': title,
        'message': message,
        'task_id': oid(task_id) if task_id else None,
        'subtask_id': oid(subtask_id) if subtask_id else None,
        'read': False,
        'timestamp': datetime.utcnow(),
        'created_at': datetime.utcnow()
    }
    notifications_col.insert_one(notification)
    
    # Send email notification only if enabled
    import os
    if os.getenv('ENABLE_EMAIL', 'false').lower() == 'true':
        try:
            from flask_mail import Mail
            mail = Mail(current_app)
            user = users_col.find_one({'_id': oid(user_id)})
            if user and user.get('email'):
                if notification_type == 'subtask_assigned':
                    task = tasks_col.find_one({'_id': oid(task_id)}) if task_id else None
                    subtask = subtasks_col.find_one({'_id': oid(subtask_id)}) if subtask_id else None
                    manager = users_col.find_one({'_id': subtask.get('assigned_by')}) if subtask else None
                    send_subtask_assigned_notification(
                        mail=mail,
                        team_member=user,
                        subtask_title=subtask.get('title', 'Subtask') if subtask else 'Subtask',
                        percentage=subtask.get('percentage', 0) if subtask else 0,
                        manager_name=manager.get('username', 'Manager') if manager else 'Manager'
                    )
        except Exception as e:
            print(f"Failed to send email notification: {e}")

def create_timeline_entry(user_id, action_type, description, task_id=None, subtask_id=None, metadata=None):
    """Create a timeline entry"""
    entry = {
        'user_id': oid(user_id),
        'action_type': action_type,
        'description': description,
        'task_id': oid(task_id) if task_id else None,
        'subtask_id': oid(subtask_id) if subtask_id else None,
        'metadata': metadata or {},
        'timestamp': datetime.utcnow(),
        'created_at': datetime.utcnow()
    }
    timeline_col.insert_one(entry)

# ---------- CREATE SUBTASKS ----------
@mongo_subtasks_bp.route('/subtasks', methods=['POST'])
@jwt_required()
def create_subtasks():
    """
    Project Manager creates subtasks from a main task and distributes to team members
    Request body: {
        "task_id": "main_task_id",
        "subtasks": [
            {
                "title": "Subtask 1",
                "description": "Description",
                "assigned_to": "user_id",
                "percentage": 40,
                "due_date": "2024-12-31",
                "priority": "high"
            }
        ]
    }
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is Project Manager or Admin
        if user.get('role') not in ['project_manager', 'admin']:
            return jsonify({'error': 'Only Project Managers and Admins can create subtasks'}), 403
        
        data = request.get_json() or {}
        task_id = data.get('task_id')
        subtasks_data = data.get('subtasks', [])
        
        if not task_id:
            return jsonify({'error': 'task_id is required'}), 400
        
        if not subtasks_data:
            return jsonify({'error': 'At least one subtask is required'}), 400
        
        # Verify main task exists
        main_task = tasks_col.find_one({'_id': oid(task_id)})
        if not main_task:
            return jsonify({'error': 'Main task not found'}), 404
        
        # Validate total percentage
        total_percentage = sum(st.get('percentage', 0) for st in subtasks_data)
        if total_percentage != 100:
            return jsonify({'error': f'Total percentage must equal 100%, got {total_percentage}%'}), 400
        
        # Create subtasks
        created_subtasks = []
        for subtask_data in subtasks_data:
            if not subtask_data.get('title'):
                return jsonify({'error': 'Each subtask must have a title'}), 400
            
            if not subtask_data.get('assigned_to'):
                return jsonify({'error': 'Each subtask must be assigned to a team member'}), 400
            
            assigned_user = users_col.find_one({'_id': oid(subtask_data['assigned_to'])})
            if not assigned_user:
                return jsonify({'error': f'Assigned user not found: {subtask_data["assigned_to"]}'}), 404
            
            subtask = {
                'task_id': oid(task_id),
                'title': subtask_data['title'],
                'description': subtask_data.get('description', ''),
                'assigned_to': oid(subtask_data['assigned_to']),
                'assigned_by': oid(uid),
                'percentage': float(subtask_data.get('percentage', 0)),
                'status': 'assigned',  # assigned, in_progress, submitted, approved, rejected
                'priority': subtask_data.get('priority', 'medium'),
                'start_date': subtask_data.get('start_date'),
                'due_date': subtask_data.get('due_date'),
                'progress': 0,
                'work_uploads': [],
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            result = subtasks_col.insert_one(subtask)
            created = subtasks_col.find_one({'_id': result.inserted_id})
            created_subtasks.append(to_str_id(created))
            
            # Create notification for assigned team member
            create_notification(
                user_id=subtask_data['assigned_to'],
                notification_type='subtask_assigned',
                title='New Subtask Assigned',
                message=f'You have been assigned a subtask: {subtask["title"]} ({subtask["percentage"]}%)',
                task_id=task_id,
                subtask_id=str(result.inserted_id)
            )
            
            # Create timeline entry
            create_timeline_entry(
                user_id=uid,
                action_type='subtask_created',
                description=f'Created subtask "{subtask["title"]}" and assigned to {assigned_user.get("username")}',
                task_id=task_id,
                subtask_id=str(result.inserted_id),
                metadata={'percentage': subtask['percentage']}
            )
        
        # Update main task status
        tasks_col.update_one(
            {'_id': oid(task_id)},
            {'$set': {
                'has_subtasks': True,
                'subtasks_count': len(created_subtasks),
                'updated_at': datetime.utcnow()
            }}
        )
        
        return jsonify({
            'message': f'{len(created_subtasks)} subtasks created successfully',
            'subtasks': created_subtasks
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET SUBTASKS FOR A TASK ----------
@mongo_subtasks_bp.route('/tasks/<task_id>/subtasks', methods=['GET'])
@jwt_required()
def get_task_subtasks(task_id):
    """Get all subtasks for a specific task"""
    try:
        uid = get_jwt_identity()
        
        # Verify task exists
        task = tasks_col.find_one({'_id': oid(task_id)})
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Get subtasks
        cursor = subtasks_col.find({'task_id': oid(task_id)}).sort('created_at', -1)
        subtasks = []
        
        for subtask in cursor:
            subtask_dict = to_str_id(subtask)
            
            # Add assigned user info
            if subtask.get('assigned_to'):
                assigned_user = users_col.find_one({'_id': oid(subtask['assigned_to'])})
                if assigned_user:
                    subtask_dict['assigned_to_name'] = f"{assigned_user.get('first_name', '')} {assigned_user.get('last_name', '')}".strip()
                    subtask_dict['assigned_to_email'] = assigned_user.get('email')
            
            # Add assigned by info
            if subtask.get('assigned_by'):
                assigned_by = users_col.find_one({'_id': oid(subtask['assigned_by'])})
                if assigned_by:
                    subtask_dict['assigned_by_name'] = f"{assigned_by.get('first_name', '')} {assigned_by.get('last_name', '')}".strip()
            
            subtasks.append(subtask_dict)
        
        return jsonify({'subtasks': subtasks}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET MY SUBTASKS (TEAM MEMBER) ----------
@mongo_subtasks_bp.route('/my-subtasks', methods=['GET'])
@jwt_required()
def get_my_subtasks():
    """Get all subtasks assigned to current user"""
    try:
        uid = get_jwt_identity()
        
        cursor = subtasks_col.find({'assigned_to': oid(uid)}).sort('due_date', 1)
        subtasks = []
        
        for subtask in cursor:
            subtask_dict = to_str_id(subtask)
            
            # Add task info
            if subtask.get('task_id'):
                task = tasks_col.find_one({'_id': oid(subtask['task_id'])})
                if task:
                    subtask_dict['task_title'] = task.get('title')
                    subtask_dict['task_description'] = task.get('description')
            
            # Add assigned by info
            if subtask.get('assigned_by'):
                manager = users_col.find_one({'_id': oid(subtask['assigned_by'])})
                if manager:
                    subtask_dict['manager_name'] = f"{manager.get('first_name', '')} {manager.get('last_name', '')}".strip()
            
            subtasks.append(subtask_dict)
        
        return jsonify({'subtasks': subtasks}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- UPDATE SUBTASK STATUS/PROGRESS ----------
@mongo_subtasks_bp.route('/subtasks/<subtask_id>', methods=['PATCH'])
@jwt_required()
def update_subtask(subtask_id):
    """Update subtask status, progress, or other fields"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        subtask = subtasks_col.find_one({'_id': oid(subtask_id)})
        if not subtask:
            return jsonify({'error': 'Subtask not found'}), 404
        
        # Check permissions
        is_assigned = str(subtask.get('assigned_to')) == uid or subtask.get('assigned_to') == oid(uid)
        is_manager = user.get('role') in ['project_manager', 'admin']
        
        if not (is_assigned or is_manager):
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.get_json() or {}
        update_fields = {}
        
        # Fields that can be updated
        for field in ['status', 'progress', 'description']:
            if field in data:
                update_fields[field] = data[field]
        
        if not update_fields:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        update_fields['updated_at'] = datetime.utcnow()
        
        subtasks_col.update_one({'_id': oid(subtask_id)}, {'$set': update_fields})
        updated = subtasks_col.find_one({'_id': oid(subtask_id)})
        
        # Create notifications and timeline
        if 'status' in update_fields:
            # Notify manager
            if subtask.get('assigned_by'):
                create_notification(
                    user_id=str(subtask['assigned_by']),
                    notification_type='subtask_updated',
                    title='Subtask Status Updated',
                    message=f'{user.get("username")} updated subtask status to: {update_fields["status"]}',
                    subtask_id=subtask_id
                )
            
            create_timeline_entry(
                user_id=uid,
                action_type='subtask_updated',
                description=f'Updated subtask status to: {update_fields["status"]}',
                subtask_id=subtask_id,
                metadata=update_fields
            )
        
        return jsonify({
            'message': 'Subtask updated successfully',
            'subtask': to_str_id(updated)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET ALL SUBTASKS (ADMIN/MANAGER VIEW) ----------
@mongo_subtasks_bp.route('/subtasks/all', methods=['GET'])
@jwt_required()
def get_all_subtasks():
    """Get all subtasks - admin/manager view"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') not in ['admin', 'project_manager']:
            return jsonify({'error': 'Admin or Manager access required'}), 403
        
        cursor = subtasks_col.find({}).sort('created_at', -1)
        subtasks = []
        
        for subtask in cursor:
            subtask_dict = to_str_id(subtask)
            
            # Add user info
            if subtask.get('assigned_to'):
                assigned_user = users_col.find_one({'_id': oid(subtask['assigned_to'])})
                if assigned_user:
                    subtask_dict['assigned_to_name'] = f"{assigned_user.get('first_name', '')} {assigned_user.get('last_name', '')}".strip()
            
            # Add task info
            if subtask.get('task_id'):
                task = tasks_col.find_one({'_id': oid(subtask['task_id'])})
                if task:
                    subtask_dict['task_title'] = task.get('title')
            
            subtasks.append(subtask_dict)
        
        return jsonify({'subtasks': subtasks}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
