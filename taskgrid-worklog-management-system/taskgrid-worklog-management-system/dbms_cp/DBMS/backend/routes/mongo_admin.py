"""
Enhanced Admin Dashboard Routes for TaskGrid
Provides comprehensive metrics, task assignments, and approval management for Admins
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from utils.mongo_db import (
    users_col, projects_col, tasks_col, subtasks_col,
    work_uploads_col, timeline_col, notifications_col,
    to_str_id, oid
)

mongo_admin_bp = Blueprint('mongo_admin', __name__)


# ---------- ADMIN DASHBOARD OVERVIEW ----------
@mongo_admin_bp.route('/admin/dashboard', methods=['GET'])
@jwt_required()
def get_admin_dashboard():
    """
    Get comprehensive admin dashboard with all metrics
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get all projects
        projects = list(projects_col.find({}))
        total_projects = len(projects)
        active_projects = len([p for p in projects if p.get('status') == 'active'])
        completed_projects = len([p for p in projects if p.get('status') == 'completed'])
        
        # Get all tasks
        tasks = list(tasks_col.find({}))
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.get('status') == 'completed'])
        in_progress_tasks = len([t for t in tasks if t.get('status') == 'in_progress'])
        pending_tasks = len([t for t in tasks if t.get('status') == 'todo'])
        
        # Get all subtasks
        subtasks = list(subtasks_col.find({}))
        total_subtasks = len(subtasks)
        submitted_subtasks = len([s for s in subtasks if s.get('status') == 'submitted'])
        approved_subtasks = len([s for s in subtasks if s.get('status') == 'approved'])
        
        # Get pending approvals
        pending_approvals = work_uploads_col.count_documents({'approval_status': 'pending'})
        
        # Get all users
        all_users = list(users_col.find({}))
        total_users = len(all_users)
        admins = len([u for u in all_users if u.get('role') == 'admin'])
        managers = len([u for u in all_users if u.get('role') == 'project_manager'])
        team_members = len([u for u in all_users if u.get('role') == 'team_member'])
        
        # Recent activities (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_activities = timeline_col.count_documents({'timestamp': {'$gte': seven_days_ago}})
        
        # Calculate progress percentages
        task_completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
        project_completion_rate = round((completed_projects / total_projects * 100) if total_projects > 0 else 0, 1)
        
        # Get task distribution by assignee
        task_distribution = {}
        for task in tasks:
            assigned_to = task.get('assigned_to')
            if assigned_to:
                assigned_user = users_col.find_one({'_id': oid(assigned_to)})
                if assigned_user:
                    user_name = f"{assigned_user.get('first_name', '')} {assigned_user.get('last_name', '')}".strip()
                    task_distribution[user_name] = task_distribution.get(user_name, 0) + 1
        
        # Get managers with their assigned projects
        managers_list = []
        for manager_user in [u for u in all_users if u.get('role') == 'project_manager']:
            manager_projects = projects_col.count_documents({'owner_id': manager_user['_id']})
            manager_tasks = tasks_col.count_documents({'created_by': manager_user['_id']})
            
            managers_list.append({
                'id': str(manager_user['_id']),
                'name': f"{manager_user.get('first_name', '')} {manager_user.get('last_name', '')}".strip(),
                'email': manager_user.get('email'),
                'projects': manager_projects,
                'tasks': manager_tasks
            })
        
        # Timeline updates (last 10)
        timeline_entries = list(timeline_col.find({}).sort('timestamp', -1).limit(10))
        timeline_updates = []
        for entry in timeline_entries:
            entry_dict = to_str_id(entry)
            if entry.get('user_id'):
                entry_user = users_col.find_one({'_id': oid(entry['user_id'])})
                if entry_user:
                    entry_dict['user_name'] = f"{entry_user.get('first_name', '')} {entry_user.get('last_name', '')}".strip()
            timeline_updates.append(entry_dict)
        
        dashboard_data = {
            'overview': {
                'total_projects': total_projects,
                'active_projects': active_projects,
                'completed_projects': completed_projects,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'in_progress_tasks': in_progress_tasks,
                'pending_tasks': pending_tasks,
                'total_subtasks': total_subtasks,
                'submitted_subtasks': submitted_subtasks,
                'approved_subtasks': approved_subtasks,
                'pending_approvals': pending_approvals,
                'total_users': total_users,
                'recent_activities': recent_activities
            },
            'users': {
                'total': total_users,
                'admins': admins,
                'managers': managers,
                'team_members': team_members
            },
            'progress': {
                'task_completion_rate': task_completion_rate,
                'project_completion_rate': project_completion_rate
            },
            'task_distribution': task_distribution,
            'managers': managers_list,
            'recent_timeline': timeline_updates
        }
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET ALL TASKS WITH DETAILS (ADMIN VIEW) ----------
@mongo_admin_bp.route('/admin/tasks', methods=['GET'])
@jwt_required()
def get_all_tasks_admin():
    """
    Get all tasks with full details including assignees and work uploads
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get query parameters
        status = request.args.get('status')
        assigned_to = request.args.get('assigned_to')
        
        query = {}
        if status:
            query['status'] = status
        if assigned_to:
            query['assigned_to'] = oid(assigned_to)
        
        tasks = list(tasks_col.find(query).sort('created_at', -1))
        tasks_with_details = []
        
        for task in tasks:
            task_dict = to_str_id(task)
            
            # Add assignee info
            if task.get('assigned_to'):
                assignee = users_col.find_one({'_id': oid(task['assigned_to'])})
                if assignee:
                    task_dict['assignee_name'] = f"{assignee.get('first_name', '')} {assignee.get('last_name', '')}".strip()
                    task_dict['assignee_email'] = assignee.get('email')
            
            # Add creator info
            if task.get('created_by'):
                creator = users_col.find_one({'_id': oid(task['created_by'])})
                if creator:
                    task_dict['creator_name'] = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            
            # Count subtasks
            task_dict['subtasks_count'] = subtasks_col.count_documents({'task_id': task['_id']})
            
            # Count work uploads
            task_dict['work_uploads_count'] = work_uploads_col.count_documents({'task_id': task['_id']})
            
            # Get pending work uploads
            task_dict['pending_approvals'] = work_uploads_col.count_documents({
                'task_id': task['_id'],
                'approval_status': 'pending'
            })
            
            tasks_with_details.append(task_dict)
        
        return jsonify({
            'tasks': tasks_with_details,
            'count': len(tasks_with_details)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- ASSIGN TASK TO MANAGER (ADMIN) ----------
@mongo_admin_bp.route('/admin/tasks/assign', methods=['POST'])
@jwt_required()
def assign_task_to_manager():
    """
    Admin creates and assigns a main task to a Project Manager
    Body: {
        "title": "Task title",
        "description": "Description",
        "assigned_to": "manager_user_id",
        "priority": "high",
        "start_date": "2024-01-01",
        "due_date": "2024-12-31",
        "estimated_hours": 100
    }
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json() or {}
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'error': 'Task title is required'}), 400
        
        if not data.get('assigned_to'):
            return jsonify({'error': 'assigned_to (manager user_id) is required'}), 400
        
        # Verify manager exists
        manager = users_col.find_one({'_id': oid(data['assigned_to'])})
        if not manager:
            return jsonify({'error': 'Manager not found'}), 404
        
        if manager.get('role') not in ['project_manager', 'admin']:
            return jsonify({'error': 'User must be a manager or admin'}), 400
        
        # Get or create project
        project_id = data.get('project_id')
        if not project_id:
            # Create default project if not specified
            project = {
                'name': f"Project for {data['title']}",
                'description': 'Auto-created project',
                'status': 'active',
                'owner_id': oid(data['assigned_to']),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            project_result = projects_col.insert_one(project)
            project_id = str(project_result.inserted_id)
        
        # Create task
        task = {
            'title': data['title'],
            'description': data.get('description', ''),
            'priority': data.get('priority', 'medium'),
            'project_id': oid(project_id),
            'assigned_to': oid(data['assigned_to']),
            'created_by': oid(uid),
            'estimated_hours': float(data.get('estimated_hours', 0)),
            'start_date': data.get('start_date'),
            'due_date': data.get('due_date'),
            'status': 'assigned',
            'progress': 0,
            'has_subtasks': False,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = tasks_col.insert_one(task)
        created_task = tasks_col.find_one({'_id': result.inserted_id})
        
        # Create notification for manager
        from routes.mongo_subtasks import create_notification, create_timeline_entry
        create_notification(
            user_id=data['assigned_to'],
            notification_type='task_assigned',
            title='New Task Assigned',
            message=f'Admin has assigned you a new task: {task["title"]}',
            task_id=str(result.inserted_id)
        )
        
        # Create timeline entry
        create_timeline_entry(
            user_id=uid,
            action_type='task_assigned',
            description=f'Assigned task "{task["title"]}" to {manager.get("username")}',
            task_id=str(result.inserted_id),
            metadata={'manager': manager.get('username')}
        )
        
        return jsonify({
            'message': 'Task assigned successfully',
            'task': to_str_id(created_task)
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET USER ACTIVITY SUMMARY ----------
@mongo_admin_bp.route('/admin/users/<user_id>/activity', methods=['GET'])
@jwt_required()
def get_user_activity(user_id):
    """Get activity summary for a specific user (Admin view)"""
    try:
        uid = get_jwt_identity()
        admin = users_col.find_one({'_id': oid(uid)})
        
        if not admin or admin.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get user
        target_user = users_col.find_one({'_id': oid(user_id)})
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get activity data
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Count activities
        tasks_created = tasks_col.count_documents({'created_by': oid(user_id)})
        tasks_assigned = tasks_col.count_documents({'assigned_to': oid(user_id)})
        subtasks_assigned = subtasks_col.count_documents({'assigned_to': oid(user_id)})
        work_uploads = work_uploads_col.count_documents({'user_id': oid(user_id)})
        timeline_entries = timeline_col.count_documents({
            'user_id': oid(user_id),
            'timestamp': {'$gte': start_date}
        })
        
        # Get recent timeline
        recent_timeline = list(timeline_col.find({
            'user_id': oid(user_id)
        }).sort('timestamp', -1).limit(20))
        
        activity_summary = {
            'user': {
                'id': str(target_user['_id']),
                'name': f"{target_user.get('first_name', '')} {target_user.get('last_name', '')}".strip(),
                'email': target_user.get('email'),
                'role': target_user.get('role')
            },
            'statistics': {
                'tasks_created': tasks_created,
                'tasks_assigned': tasks_assigned,
                'subtasks_assigned': subtasks_assigned,
                'work_uploads': work_uploads,
                'recent_activities': timeline_entries,
                'date_range_days': days
            },
            'recent_timeline': [to_str_id(entry) for entry in recent_timeline]
        }
        
        return jsonify(activity_summary), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET TEAM MEMBERS FOR ASSIGNMENT ----------
@mongo_admin_bp.route('/admin/team-members', methods=['GET'])
@jwt_required()
def get_team_members_for_assignment():
    """Get all team members available for task assignment"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') not in ['admin', 'project_manager']:
            return jsonify({'error': 'Admin or Manager access required'}), 403
        
        # Get all users
        all_users = list(users_col.find({'is_active': True}))
        
        team_members = []
        for u in all_users:
            # Count current assignments
            assigned_tasks = tasks_col.count_documents({'assigned_to': u['_id']})
            assigned_subtasks = subtasks_col.count_documents({'assigned_to': u['_id']})
            
            team_members.append({
                'id': str(u['_id']),
                'name': f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
                'username': u.get('username'),
                'email': u.get('email'),
                'role': u.get('role'),
                'assigned_tasks': assigned_tasks,
                'assigned_subtasks': assigned_subtasks,
                'total_assignments': assigned_tasks + assigned_subtasks
            })
        
        # Sort by role (managers first, then team members)
        team_members.sort(key=lambda x: (0 if x['role'] == 'project_manager' else 1 if x['role'] == 'team_member' else 2, x['total_assignments']))
        
        return jsonify({
            'team_members': team_members,
            'count': len(team_members)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
