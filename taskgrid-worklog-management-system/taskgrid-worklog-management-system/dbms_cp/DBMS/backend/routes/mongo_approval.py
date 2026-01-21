"""
Enhanced Approval Workflow for TaskGrid
Handles the complete approval chain: Team Member → Manager → Admin
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from utils.mongo_db import (
    users_col, tasks_col, subtasks_col, work_uploads_col,
    notifications_col, timeline_col, to_str_id, oid
)

mongo_approval_bp = Blueprint('mongo_approval', __name__)


# ---------- MANAGER APPROVES SUBTASK WORK ----------
@mongo_approval_bp.route('/manager/approve/subtask/<subtask_id>', methods=['POST'])
@jwt_required()
def manager_approve_subtask(subtask_id):
    """
    Project Manager approves a subtask submitted by Team Member
    Automatically notifies Admin when all subtasks of a main task are approved
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') not in ['project_manager', 'admin']:
            return jsonify({'error': 'Manager or admin access required'}), 403
        
        data = request.get_json() or {}
        feedback = data.get('feedback', '')
        
        # Get subtask
        subtask = subtasks_col.find_one({'_id': oid(subtask_id)})
        if not subtask:
            return jsonify({'error': 'Subtask not found'}), 404
        
        if subtask.get('status') != 'submitted':
            return jsonify({'error': 'Subtask must be in submitted status'}), 400
        
        # Update subtask status
        subtasks_col.update_one(
            {'_id': oid(subtask_id)},
            {'$set': {
                'status': 'approved',
                'approved_by': oid(uid),
                'approved_at': datetime.utcnow(),
                'manager_feedback': feedback,
                'updated_at': datetime.utcnow()
            }}
        )
        
        # Notify team member
        team_member_id = subtask.get('assigned_to')
        if team_member_id:
            notification = {
                'user_id': oid(team_member_id),
                'type': 'subtask_approved',
                'title': '✅ Subtask Approved',
                'message': f'Your subtask "{subtask.get("title")}" has been approved by the Project Manager',
                'task_id': subtask.get('task_id'),
                'subtask_id': oid(subtask_id),
                'read': False,
                'timestamp': datetime.utcnow(),
                'created_at': datetime.utcnow()
            }
            notifications_col.insert_one(notification)
        
        # Create timeline entry
        timeline_entry = {
            'user_id': oid(uid),
            'action_type': 'subtask_approved',
            'description': f'Manager approved subtask "{subtask.get("title")}"',
            'task_id': subtask.get('task_id'),
            'subtask_id': oid(subtask_id),
            'metadata': {'feedback': feedback},
            'timestamp': datetime.utcnow(),
            'created_at': datetime.utcnow()
        }
        timeline_col.insert_one(timeline_entry)
        
        # Check if ALL subtasks of this main task are approved
        task_id = subtask.get('task_id')
        all_subtasks = list(subtasks_col.find({'task_id': task_id}))
        all_approved = all(s.get('status') == 'approved' for s in all_subtasks)
        
        if all_approved and len(all_subtasks) > 0:
            # Update main task status
            tasks_col.update_one(
                {'_id': task_id},
                {'$set': {
                    'status': 'ready_for_admin_approval',
                    'all_subtasks_approved': True,
                    'updated_at': datetime.utcnow()
                }}
            )
            
            # Notify ALL Admins
            admins = users_col.find({'role': 'admin', 'is_active': True})
            task = tasks_col.find_one({'_id': task_id})
            
            for admin in admins:
                notification = {
                    'user_id': admin['_id'],
                    'type': 'task_ready_for_approval',
                    'title': '🎯 Task Ready for Final Approval',
                    'message': f'All subtasks for "{task.get("title")}" have been approved by the Project Manager',
                    'task_id': task_id,
                    'read': False,
                    'timestamp': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                }
                notifications_col.insert_one(notification)
        
        return jsonify({
            'message': 'Subtask approved successfully',
            'all_subtasks_approved': all_approved if len(all_subtasks) > 0 else False
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- MANAGER REJECTS SUBTASK WORK ----------
@mongo_approval_bp.route('/manager/reject/subtask/<subtask_id>', methods=['POST'])
@jwt_required()
def manager_reject_subtask(subtask_id):
    """
    Project Manager rejects a subtask submitted by Team Member
    Team Member must resubmit the work
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') not in ['project_manager', 'admin']:
            return jsonify({'error': 'Manager access required'}), 403
        
        data = request.get_json() or {}
        feedback = data.get('feedback', '')
        
        if not feedback:
            return jsonify({'error': 'Feedback is required when rejecting work'}), 400
        
        # Get subtask
        subtask = subtasks_col.find_one({'_id': oid(subtask_id)})
        if not subtask:
            return jsonify({'error': 'Subtask not found'}), 404
        
        if subtask.get('status') != 'submitted':
            return jsonify({'error': 'Subtask must be in submitted status'}), 400
        
        # Update subtask status
        subtasks_col.update_one(
            {'_id': oid(subtask_id)},
            {'$set': {
                'status': 'rejected',
                'rejected_by': oid(uid),
                'rejected_at': datetime.utcnow(),
                'manager_feedback': feedback,
                'updated_at': datetime.utcnow()
            }}
        )
        
        # Notify team member
        team_member_id = subtask.get('assigned_to')
        if team_member_id:
            notification = {
                'user_id': oid(team_member_id),
                'type': 'subtask_rejected',
                'title': '❌ Subtask Needs Revision',
                'message': f'Your subtask "{subtask.get("title")}" needs revision. Feedback: {feedback}',
                'task_id': subtask.get('task_id'),
                'subtask_id': oid(subtask_id),
                'read': False,
                'timestamp': datetime.utcnow(),
                'created_at': datetime.utcnow()
            }
            notifications_col.insert_one(notification)
        
        # Create timeline entry
        timeline_entry = {
            'user_id': oid(uid),
            'action_type': 'subtask_rejected',
            'description': f'Manager rejected subtask "{subtask.get("title")}"',
            'task_id': subtask.get('task_id'),
            'subtask_id': oid(subtask_id),
            'metadata': {'feedback': feedback},
            'timestamp': datetime.utcnow(),
            'created_at': datetime.utcnow()
        }
        timeline_col.insert_one(timeline_entry)
        
        return jsonify({'message': 'Subtask rejected successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- ADMIN APPROVES FINAL TASK ----------
@mongo_approval_bp.route('/admin/approve/task/<task_id>', methods=['POST'])
@jwt_required()
def admin_approve_task(task_id):
    """
    Admin gives final approval to the entire task
    Notifies Project Manager and all Team Members involved
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json() or {}
        feedback = data.get('feedback', '')
        
        # Get task
        task = tasks_col.find_one({'_id': oid(task_id)})
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.get('status') != 'ready_for_admin_approval':
            return jsonify({'error': 'Task must be ready for admin approval'}), 400
        
        # Update task status
        tasks_col.update_one(
            {'_id': oid(task_id)},
            {'$set': {
                'status': 'completed',
                'approved_by_admin': oid(uid),
                'admin_approved_at': datetime.utcnow(),
                'admin_feedback': feedback,
                'updated_at': datetime.utcnow()
            }}
        )
        
        # Get all subtasks to find involved team members
        subtasks = list(subtasks_col.find({'task_id': oid(task_id)}))
        notified_users = set()
        
        # Notify all team members
        for subtask in subtasks:
            team_member_id = subtask.get('assigned_to')
            if team_member_id and str(team_member_id) not in notified_users:
                notification = {
                    'user_id': oid(team_member_id),
                    'type': 'task_completed',
                    'title': '🎉 Task Completed - Admin Approved',
                    'message': f'Admin has approved the final task "{task.get("title")}". Great work!',
                    'task_id': oid(task_id),
                    'read': False,
                    'timestamp': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                }
                notifications_col.insert_one(notification)
                notified_users.add(str(team_member_id))
        
        # Notify Project Manager who created subtasks
        for subtask in subtasks:
            manager_id = subtask.get('assigned_by')
            if manager_id and str(manager_id) not in notified_users:
                notification = {
                    'user_id': oid(manager_id),
                    'type': 'task_completed',
                    'title': '🎉 Task Completed - Admin Approved',
                    'message': f'Admin has approved the final task "{task.get("title")}"',
                    'task_id': oid(task_id),
                    'read': False,
                    'timestamp': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                }
                notifications_col.insert_one(notification)
                notified_users.add(str(manager_id))
        
        # Create timeline entry
        timeline_entry = {
            'user_id': oid(uid),
            'action_type': 'task_admin_approved',
            'description': f'Admin approved final task "{task.get("title")}"',
            'task_id': oid(task_id),
            'metadata': {
                'feedback': feedback,
                'team_members_notified': len(notified_users)
            },
            'timestamp': datetime.utcnow(),
            'created_at': datetime.utcnow()
        }
        timeline_col.insert_one(timeline_entry)
        
        return jsonify({
            'message': 'Task approved successfully by Admin',
            'users_notified': len(notified_users)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- ADMIN REJECTS FINAL TASK ----------
@mongo_approval_bp.route('/admin/reject/task/<task_id>', methods=['POST'])
@jwt_required()
def admin_reject_task(task_id):
    """
    Admin rejects the entire task
    All subtasks go back to revision status
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json() or {}
        feedback = data.get('feedback', '')
        
        if not feedback:
            return jsonify({'error': 'Feedback is required when rejecting work'}), 400
        
        # Get task
        task = tasks_col.find_one({'_id': oid(task_id)})
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Update task status
        tasks_col.update_one(
            {'_id': oid(task_id)},
            {'$set': {
                'status': 'needs_revision',
                'rejected_by_admin': oid(uid),
                'admin_rejected_at': datetime.utcnow(),
                'admin_feedback': feedback,
                'all_subtasks_approved': False,
                'updated_at': datetime.utcnow()
            }}
        )
        
        # Update all subtasks to need revision
        subtasks_col.update_many(
            {'task_id': oid(task_id), 'status': 'approved'},
            {'$set': {
                'status': 'needs_revision',
                'updated_at': datetime.utcnow()
            }}
        )
        
        # Get all involved users
        subtasks = list(subtasks_col.find({'task_id': oid(task_id)}))
        notified_users = set()
        
        # Notify all team members
        for subtask in subtasks:
            team_member_id = subtask.get('assigned_to')
            if team_member_id and str(team_member_id) not in notified_users:
                notification = {
                    'user_id': oid(team_member_id),
                    'type': 'task_rejected',
                    'title': '❌ Task Needs Revision',
                    'message': f'Admin requires revision for task "{task.get("title")}". Feedback: {feedback}',
                    'task_id': oid(task_id),
                    'read': False,
                    'timestamp': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                }
                notifications_col.insert_one(notification)
                notified_users.add(str(team_member_id))
            
            # Notify manager
            manager_id = subtask.get('assigned_by')
            if manager_id and str(manager_id) not in notified_users:
                notification = {
                    'user_id': oid(manager_id),
                    'type': 'task_rejected',
                    'title': '❌ Task Needs Revision',
                    'message': f'Admin requires revision for task "{task.get("title")}". Feedback: {feedback}',
                    'task_id': oid(task_id),
                    'read': False,
                    'timestamp': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                }
                notifications_col.insert_one(notification)
                notified_users.add(str(manager_id))
        
        # Create timeline entry
        timeline_entry = {
            'user_id': oid(uid),
            'action_type': 'task_admin_rejected',
            'description': f'Admin rejected task "{task.get("title")}" - needs revision',
            'task_id': oid(task_id),
            'metadata': {
                'feedback': feedback,
                'users_notified': len(notified_users)
            },
            'timestamp': datetime.utcnow(),
            'created_at': datetime.utcnow()
        }
        timeline_col.insert_one(timeline_entry)
        
        return jsonify({
            'message': 'Task rejected successfully by Admin',
            'users_notified': len(notified_users)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET PENDING APPROVALS FOR MANAGER ----------
@mongo_approval_bp.route('/manager/pending-approvals', methods=['GET'])
@jwt_required()
def get_manager_pending_approvals():
    """Get all subtasks pending manager approval"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') not in ['project_manager', 'admin']:
            return jsonify({'error': 'Manager access required'}), 403
        
        # Get all submitted subtasks
        pending_subtasks = list(subtasks_col.find({
            'status': 'submitted',
            'assigned_by': oid(uid)
        }).sort('updated_at', -1))
        
        subtasks_data = []
        for subtask in pending_subtasks:
            subtask_dict = to_str_id(subtask)
            
            # Get task info
            task = tasks_col.find_one({'_id': subtask.get('task_id')})
            if task:
                subtask_dict['task_title'] = task.get('title')
            
            # Get team member info
            team_member = users_col.find_one({'_id': subtask.get('assigned_to')})
            if team_member:
                subtask_dict['team_member_name'] = f"{team_member.get('first_name', '')} {team_member.get('last_name', '')}".strip()
            
            subtasks_data.append(subtask_dict)
        
        return jsonify({'pending_approvals': subtasks_data}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET PENDING APPROVALS FOR ADMIN ----------
@mongo_approval_bp.route('/admin/pending-approvals', methods=['GET'])
@jwt_required()
def get_admin_pending_approvals():
    """Get all tasks pending admin approval"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get all tasks ready for admin approval
        pending_tasks = list(tasks_col.find({
            'status': 'ready_for_admin_approval'
        }).sort('updated_at', -1))
        
        tasks_data = []
        for task in pending_tasks:
            task_dict = to_str_id(task)
            
            # Get subtasks info
            subtasks = list(subtasks_col.find({'task_id': task['_id']}))
            task_dict['subtasks'] = [to_str_id(s) for s in subtasks]
            task_dict['subtasks_count'] = len(subtasks)
            
            # Get creator info
            creator = users_col.find_one({'_id': task.get('created_by')})
            if creator:
                task_dict['creator_name'] = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            
            tasks_data.append(task_dict)
        
        return jsonify({'pending_approvals': tasks_data}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
