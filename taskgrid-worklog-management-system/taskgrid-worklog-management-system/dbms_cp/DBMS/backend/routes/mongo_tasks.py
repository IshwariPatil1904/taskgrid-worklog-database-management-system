from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from utils.mongo_db import tasks_col, users_col, to_str_id, oid, notifications_col
from utils.notification_helper import send_task_assigned_notification

mongo_tasks_bp = Blueprint('mongo_tasks', __name__)

# ---------- Helper ----------
def _task_public(doc):
    """Convert MongoDB document to JSON-safe dict"""
    return to_str_id(doc)

# ---------- DELETE TASK ----------
@mongo_tasks_bp.route('/tasks/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    try:
        uid = get_jwt_identity()
        user_oid = oid(uid)
        if not user_oid:
            return jsonify({'error': 'Invalid user identity'}), 401

        # Allow delete if current user is owner/creator/assignee
        q = {
            '_id': oid(task_id),
            '$or': [
                {'user_id': {'$in': [user_oid, uid]}},
                {'created_by': {'$in': [user_oid, uid]}},
                {'assigned_to': {'$in': [user_oid, uid]}},
                {'user_id_str': str(uid)},
                {'created_by_str': str(uid)},
                {'assigned_to_str': str(uid)},
            ]
        }
        res = tasks_col.delete_one(q)
        if res.deleted_count == 0:
            return jsonify({'error': 'Task not found or not permitted'}), 404
        return jsonify({'message': 'Task deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- CREATE TASK ----------
@mongo_tasks_bp.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        required = ['title', 'priority', 'start_date', 'due_date']
        for f in required:
            if not data.get(f):
                return jsonify({'error': f'{f} is required'}), 400

        # Normalize project_id and assigned_to to ObjectId when possible
        project_raw = data.get('project_id')
        project_oid = oid(project_raw) if project_raw else None

        assigned_raw = data.get('assigned_to') or data.get('assignee')
        assigned_oid = oid(assigned_raw) if assigned_raw else None

        # Build document for MongoDB
        doc = {
            'title': data['title'],
            'description': data.get('description', ''),
            'priority': data.get('priority', 'medium'),
            # store ObjectId when possible; keep raw otherwise
            'project_id': project_oid if project_oid else (project_raw if project_raw else None),
            'project_id_str': str(project_raw) if project_raw is not None else None,
            'estimated_hours': float(data.get('estimated_hours', 0) or 0),
            'start_date': data['start_date'],
            'due_date': data['due_date'],
            'status': data.get('status', 'todo'),
            'assignee': data.get('assignee') or user.get('username', 'Unknown'),
            'assigned_to': assigned_oid if assigned_oid else (assigned_raw if assigned_raw else None),
            'assigned_to_str': str(assigned_raw) if assigned_raw is not None else None,
            # store both ObjectId and string for user
            'user_id': oid(uid),
            'user_id_str': str(uid),
            'created_by': oid(uid),
            'created_by_str': str(uid),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        res = tasks_col.insert_one(doc)
        created = tasks_col.find_one({'_id': res.inserted_id})
        task_data = to_str_id(created)

        # Check if admin is creating the task
        user_role = user.get('role')
        
        if user_role == 'admin':
            # Admin task: Notify ALL project managers
            print(f"🎯 Admin created task '{doc['title']}' - notifying all project managers")
            managers = list(users_col.find({'role': 'project_manager', 'is_active': True}))
            
            for manager in managers:
                try:
                    # Create in-app notification
                    notifications_col.insert_one({
                        'user_id': manager['_id'],
                        'type': 'admin_task_assigned',
                        'title': '🎯 New Main Task Assigned by Admin',
                        'message': f'Admin has assigned you a main task: "{doc["title"]}"',
                        'task_id': res.inserted_id,
                        'read': False,
                        'timestamp': datetime.utcnow(),
                        'created_at': datetime.utcnow()
                    })
                    
                    # Send email only if enabled
                    import os
                    if os.getenv('ENABLE_EMAIL', 'false').lower() == 'true' and manager.get('email'):
                        try:
                            from flask_mail import Mail
                            mail = Mail(current_app)
                            manager_email = manager.get('email')
                            
                            print(f"📧 Attempting to send email to {manager_email}")
                            
                            send_task_assigned_notification(
                                mail=mail,
                                manager_user=manager,
                                task_title=doc['title'],
                                assigner_name=user.get('username', 'Admin')
                            )
                            
                            print(f"✅ Email sent successfully to {manager_email}")
                            
                        except Exception as email_err:
                            print(f"❌ Failed to send email to {manager.get('email')}: {email_err}")
                            import traceback
                            traceback.print_exc()
                            
                except Exception as notif_err:
                    print(f"Failed to notify manager {manager.get('_id')}: {notif_err}")
        
        elif assigned_oid and str(assigned_oid) != str(uid):
            # Regular task assignment: Notify specific assignee
            try:
                assigned_user = users_col.find_one({'_id': assigned_oid})
                if assigned_user:
                    # Create in-app notification
                    notifications_col.insert_one({
                        'user_id': assigned_oid,
                        'type': 'task_assigned',
                        'title': 'New Task Assigned',
                        'message': f'You have been assigned a new task: {doc["title"]}',
                        'task_id': res.inserted_id,
                        'read': False,
                        'timestamp': datetime.utcnow(),
                        'created_at': datetime.utcnow()
                    })
                    
                    # Send email only if enabled
                    import os
                    if os.getenv('ENABLE_EMAIL', 'false').lower() == 'true' and assigned_user.get('email'):
                        from flask_mail import Mail
                        mail = Mail(current_app)
                        send_task_assigned_notification(
                            mail=mail,
                            manager_user=assigned_user,
                            task_title=doc['title'],
                            assigner_name=user.get('username', 'Admin')
                        )
            except Exception as e:
                print(f"Failed to send task assignment notification: {e}")

        return jsonify({
            'message': 'Task created successfully',
            'task': task_data
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET TASKS ----------
@mongo_tasks_bp.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    try:
        uid = get_jwt_identity()
        user_oid = oid(uid)

        # Resolve username and role for matching
        username = None
        user_role = None
        if user_oid:
            user_doc = users_col.find_one({'_id': user_oid})
            if user_doc:
                username = user_doc.get('username')
                user_role = user_doc.get('role')

        # Build flexible $or query to catch both ObjectId and string representations
        ors = [
            {'user_id': {'$in': [user_oid, uid]}},
            {'created_by': {'$in': [user_oid, uid]}},
            {'assigned_to': {'$in': [user_oid, uid]}},
            {'user_id_str': str(uid)},
            {'created_by_str': str(uid)},
            {'assigned_to_str': str(uid)},
        ]

        # Also match by assignee username if present
        if username:
            ors.append({'assignee': username})
        
        # Project managers should see all tasks created by admin
        if user_role == 'project_manager':
            admin_users = list(users_col.find({'role': 'admin'}, {'_id': 1}))
            admin_ids = [admin['_id'] for admin in admin_users]
            admin_ids_str = [str(admin['_id']) for admin in admin_users]
            
            # Add condition to see tasks created by any admin
            ors.append({'created_by': {'$in': admin_ids}})
            ors.append({'created_by_str': {'$in': admin_ids_str}})
            ors.append({'user_id': {'$in': admin_ids}})
            ors.append({'user_id_str': {'$in': admin_ids_str}})

        # Query and sort by creation time (newest first)
        cursor = tasks_col.find({'$or': ors}).sort('created_at', -1)
        tasks = [to_str_id(t) for t in cursor]

        # For team members, also include their assigned subtasks
        # Convert subtasks to task-like format so they show in dashboard
        if user_role == 'team_member':
            from utils.mongo_db import subtasks_col
            
            print(f"🔍 Team member {username} (ID: {user_oid}) - Fetching subtasks")
            subtask_cursor = subtasks_col.find({'assigned_to': user_oid}).sort('due_date', 1)
            subtask_list = list(subtask_cursor)
            print(f"📋 Found {len(subtask_list)} subtasks for team member")
            
            for subtask in subtask_list:
                subtask_dict = to_str_id(subtask)
                
                # Get the subtask ID (to_str_id converts _id ObjectId to string but keeps it as _id)
                subtask_id_str = str(subtask['_id']) if subtask.get('_id') else None
                
                # Get parent task info
                parent_task = None
                if subtask.get('task_id'):
                    parent_task = tasks_col.find_one({'_id': oid(subtask['task_id'])})
                
                # Convert subtask to task format for dashboard display
                task_from_subtask = {
                    'id': subtask_id_str,  # Use the actual subtask _id converted to string
                    '_id': subtask_id_str,  # Also set _id for consistency
                    'title': f"[Subtask] {subtask_dict.get('title', 'Untitled')}",
                    'description': subtask_dict.get('description', ''),
                    'status': subtask_dict.get('status', 'pending'),
                    'priority': subtask_dict.get('priority', 'medium'),
                    'due_date': subtask_dict.get('due_date'),
                    'start_date': subtask_dict.get('created_at'),
                    'percentage': subtask_dict.get('percentage', 0),
                    'is_subtask': True,  # Flag to identify as subtask
                    'subtask_id': subtask_id_str,  # Use the actual subtask _id
                    'parent_task_id': str(subtask.get('task_id')) if subtask.get('task_id') else None,
                    'parent_task_title': parent_task.get('title') if parent_task else None,
                    'assigned_to': subtask_dict.get('assigned_to'),
                    'assigned_by': subtask_dict.get('assigned_by'),
                    'created_at': subtask_dict.get('created_at'),
                    'updated_at': subtask_dict.get('updated_at')
                }
                
                # Add manager info
                if subtask.get('assigned_by'):
                    manager = users_col.find_one({'_id': oid(subtask['assigned_by'])})
                    if manager:
                        task_from_subtask['manager_name'] = f"{manager.get('first_name', '')} {manager.get('last_name', '')}".strip()
                
                tasks.append(task_from_subtask)
                print(f"✅ Added subtask '{task_from_subtask['title']}' to tasks list")
        
        if user_role == 'team_member':
            print(f"📤 Returning {len(tasks)} total tasks (including {len(subtask_list)} subtasks)")

        return jsonify({'tasks': tasks}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------- UPDATE TASK ----------
@mongo_tasks_bp.route('/tasks/<task_id>', methods=['PATCH'])
@jwt_required()
def update_task(task_id):
    try:
        uid = get_jwt_identity()
        user_oid = oid(uid)
        data = request.get_json() or {}

        update_fields = {}
        for key in ['title', 'description', 'status', 'progress', 'priority', 'due_date', 'start_date']:
            if key in data:
                update_fields[key] = data[key]

        if not update_fields:
            return jsonify({'error': 'No valid fields to update'}), 400

        update_fields['updated_at'] = datetime.utcnow()
        # Broaden authorization like delete: allow owner/creator/assignee and legacy *_str fields
        auth_q = {
            '_id': oid(task_id),
            '$or': [
                {'user_id': {'$in': [user_oid, uid]}},
                {'created_by': {'$in': [user_oid, uid]}},
                {'assigned_to': {'$in': [user_oid, uid]}},
                {'user_id_str': str(uid)},
                {'created_by_str': str(uid)},
                {'assigned_to_str': str(uid)},
            ]
        }
        res = tasks_col.update_one(auth_q, {'$set': update_fields})

        if res.modified_count == 0 and res.matched_count == 0:
            return jsonify({'error': 'Task not found or not permitted'}), 404

        updated = tasks_col.find_one({'_id': oid(task_id)})
        return jsonify({'message': 'Task updated', 'task': to_str_id(updated)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------- COMPATIBILITY ALIAS ----------
@mongo_tasks_bp.route('/data/tasks', methods=['GET', 'POST'])
@jwt_required()
def alias_tasks_data():
    """Alias for /tasks endpoint"""
    if request.method == 'GET':
        return get_tasks()
    return create_task()


