"""
Admin Task Management Routes for TaskGrid
Handles admin-only task creation with auto-notification to all Project Managers
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from utils.mongo_db import (
    users_col, tasks_col, notifications_col, timeline_col,
    to_str_id, oid
)
from utils.notification_helper import send_admin_task_notification

mongo_admin_tasks_bp = Blueprint('mongo_admin_tasks', __name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg', 'gif', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- CREATE ADMIN MAIN TASK ----------
@mongo_admin_tasks_bp.route('/admin/tasks', methods=['POST'])
@jwt_required()
def create_admin_main_task():
    """
    Admin creates a main task that will be visible to ALL Project Managers
    Body (multipart/form-data):
        - title: Task title (required)
        - description: Task description (required)
        - due_date: Deadline (required)
        - priority: high/medium/low (default: high)
        - project_id: Optional project ID
        - files: Multiple file uploads (optional)
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        # Verify admin role
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Only admins can create main tasks'}), 403
        
        # Get form data
        title = request.form.get('title')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority', 'high')
        project_id = request.form.get('project_id')
        start_date = request.form.get('start_date', datetime.utcnow().strftime('%Y-%m-%d'))
        
        # Validation
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not description:
            return jsonify({'error': 'Description is required'}), 400
        if not due_date:
            return jsonify({'error': 'Due date is required'}), 400
        
        # Handle file uploads
        uploaded_files = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            upload_dir = os.path.join(current_app.root_path, 'uploads', 'admin_tasks')
            os.makedirs(upload_dir, exist_ok=True)
            
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    filepath = os.path.join(upload_dir, unique_filename)
                    file.save(filepath)
                    
                    uploaded_files.append({
                        'original_filename': filename,
                        'stored_filename': unique_filename,
                        'filepath': filepath,
                        'uploaded_at': datetime.utcnow()
                    })
        
        # Create main task document
        task_doc = {
            'title': title,
            'description': description,
            'priority': priority,
            'start_date': start_date,
            'due_date': due_date,
            'project_id': oid(project_id) if project_id else None,
            'project_id_str': str(project_id) if project_id else None,
            'status': 'assigned',  # assigned to managers
            'task_type': 'admin_main_task',  # Flag as admin-created main task
            'created_by': oid(uid),
            'created_by_str': str(uid),
            'user_id': oid(uid),
            'user_id_str': str(uid),
            'attachments': uploaded_files,
            'has_subtasks': False,
            'subtasks_count': 0,
            'assigned_to_all_managers': True,  # Flag that all managers should see this
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Insert task
        result = tasks_col.insert_one(task_doc)
        created_task = tasks_col.find_one({'_id': result.inserted_id})
        task_data = to_str_id(created_task)
        
        # Get ALL Project Managers
        managers = list(users_col.find({'role': 'project_manager', 'is_active': True}))
        
        # Send notifications to ALL Project Managers
        notified_managers = []
        for manager in managers:
            try:
                # Create in-app notification
                notification = {
                    'user_id': manager['_id'],
                    'type': 'admin_task_assigned',
                    'title': '🎯 New Main Task Assigned by Admin',
                    'message': f'Admin has assigned you a main task: "{title}"',
                    'task_id': result.inserted_id,
                    'read': False,
                    'timestamp': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                }
                notifications_col.insert_one(notification)
                
                # Send email notification
                if os.getenv('ENABLE_EMAIL', 'false').lower() == 'true':
                    try:
                        from flask_mail import Mail
                        mail = Mail(current_app)
                        admin_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get('username', 'Admin')
                        manager_email = manager.get('email')
                        
                        print(f"📧 Attempting to send email to {manager_email}")
                        
                        send_admin_task_notification(
                            mail=mail,
                            manager=manager,
                            task_title=title,
                            task_description=description,
                            due_date=due_date,
                            admin_name=admin_name
                        )
                        
                        print(f"✅ Email sent successfully to {manager_email}")
                        
                    except Exception as email_err:
                        print(f"❌ Failed to send email to {manager.get('email')}: {email_err}")
                        import traceback
                        traceback.print_exc()
                
                notified_managers.append({
                    'id': str(manager['_id']),
                    'name': f"{manager.get('first_name', '')} {manager.get('last_name', '')}".strip(),
                    'email': manager.get('email')
                })
                
            except Exception as notif_err:
                print(f"Failed to notify manager {manager.get('_id')}: {notif_err}")
        
        # Create timeline entry
        timeline_entry = {
            'user_id': oid(uid),
            'action_type': 'admin_task_created',
            'description': f'Admin created main task "{title}" and notified {len(notified_managers)} project managers',
            'task_id': result.inserted_id,
            'metadata': {
                'managers_notified': len(notified_managers),
                'has_attachments': len(uploaded_files) > 0,
                'priority': priority
            },
            'timestamp': datetime.utcnow(),
            'created_at': datetime.utcnow()
        }
        timeline_col.insert_one(timeline_entry)
        
        return jsonify({
            'message': 'Main task created successfully and all project managers notified',
            'task': task_data,
            'managers_notified': notified_managers,
            'attachments_uploaded': len(uploaded_files)
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET ADMIN TASKS ----------
@mongo_admin_tasks_bp.route('/admin/tasks', methods=['GET'])
@jwt_required()
def get_admin_tasks():
    """Get all admin-created main tasks"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get all admin main tasks
        tasks = list(tasks_col.find({
            'task_type': 'admin_main_task'
        }).sort('created_at', -1))
        
        tasks_data = []
        for task in tasks:
            task_dict = to_str_id(task)
            
            # Get subtasks count
            subtasks_count = 0
            if task.get('has_subtasks'):
                from utils.mongo_db import subtasks_col
                subtasks_count = subtasks_col.count_documents({'task_id': task['_id']})
            
            task_dict['subtasks_count'] = subtasks_count
            tasks_data.append(task_dict)
        
        return jsonify({'tasks': tasks_data}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET MANAGER TASKS (Tasks visible to managers) ----------
@mongo_admin_tasks_bp.route('/manager/tasks', methods=['GET'])
@jwt_required()
def get_manager_tasks():
    """Get all main tasks assigned to project managers"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') not in ['project_manager', 'admin']:
            return jsonify({'error': 'Manager access required'}), 403
        
        # Get all admin main tasks (visible to all managers)
        tasks = list(tasks_col.find({
            'task_type': 'admin_main_task',
            'assigned_to_all_managers': True
        }).sort('created_at', -1))
        
        # Also get tasks specifically assigned to this manager
        assigned_tasks = list(tasks_col.find({
            '$or': [
                {'assigned_to': oid(uid)},
                {'created_by': oid(uid)}
            ],
            'task_type': {'$ne': 'admin_main_task'}
        }).sort('created_at', -1))
        
        all_tasks = tasks + assigned_tasks
        
        tasks_data = []
        for task in all_tasks:
            task_dict = to_str_id(task)
            
            # Get subtasks if any
            from utils.mongo_db import subtasks_col
            subtasks = list(subtasks_col.find({'task_id': task['_id']}))
            task_dict['subtasks'] = [to_str_id(s) for s in subtasks]
            task_dict['subtasks_count'] = len(subtasks)
            
            # Get creator info
            creator = users_col.find_one({'_id': task.get('created_by')})
            if creator:
                task_dict['creator_name'] = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            
            tasks_data.append(task_dict)
        
        return jsonify({'tasks': tasks_data}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
