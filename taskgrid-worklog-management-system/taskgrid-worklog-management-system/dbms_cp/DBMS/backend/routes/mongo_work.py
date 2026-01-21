"""
Work Upload and Approval Routes for TaskGrid
Handles file uploads, work submissions, and admin approval/rejection workflow
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from utils.mongo_db import subtasks_col, tasks_col, users_col, work_uploads_col, timeline_col, notifications_col, to_str_id, oid
from utils.notification_helper import send_work_reviewed_notification

mongo_work_bp = Blueprint('mongo_work', __name__)

# Configuration for file uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', 'py', 'js', 'html', 'css'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_notification(user_id, notification_type, title, message, task_id=None, subtask_id=None, work_id=None):
    """Create a notification for a user and send email"""
    notification = {
        'user_id': oid(user_id),
        'type': notification_type,
        'title': title,
        'message': message,
        'task_id': oid(task_id) if task_id else None,
        'subtask_id': oid(subtask_id) if subtask_id else None,
        'work_id': oid(work_id) if work_id else None,
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
                if notification_type == 'work_submitted':
                    task = tasks_col.find_one({'_id': oid(task_id)}) if task_id else None
                    submitter = users_col.find_one({'_id': notification.get('user_id')})
                    send_work_submitted_notification(
                        mail=mail,
                        admin_user=user,
                        task_title=task.get('title', 'Task') if task else 'Task',
                        submitter_name=submitter.get('username', 'Team Member') if submitter else 'Team Member'
                    )
                elif notification_type in ['work_approved', 'work_rejected']:
                    status = 'approved' if notification_type == 'work_approved' else 'rejected'
                    reviewer = users_col.find_one({'_id': notification.get('reviewed_by')}) if notification.get('reviewed_by') else None
                    send_work_reviewed_notification(
                        mail=mail,
                        team_member=user,
                        status=status,
                        task_title=message.split(':')[-1].strip() if ':' in message else 'Task',
                        reviewer_name=reviewer.get('username', 'Admin') if reviewer else 'Admin',
                        feedback=notification.get('feedback', '')
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


# ---------- UPLOAD WORK (TEAM MEMBER) ----------
@mongo_work_bp.route('/work-uploads', methods=['POST'])
@jwt_required()
def upload_work():
    """
    Team member uploads work for a task or subtask
    Multipart form data with:
    - task_id or subtask_id
    - description (text)
    - files (optional)
    - progress (percentage)
    """
    try:
        print("📤 Work upload endpoint hit!")
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            print(f"❌ User not found: {uid}")
            return jsonify({'error': 'User not found'}), 404
        
        # Get form data
        task_id = request.form.get('task_id')
        subtask_id = request.form.get('subtask_id')
        description = request.form.get('description', '')
        progress = request.form.get('progress', 0)
        
        print(f"📝 Form data - task_id: {task_id}, subtask_id: {subtask_id}, description: {description[:50]}..., progress: {progress}")
        
        if not task_id and not subtask_id:
            print("❌ Neither task_id nor subtask_id provided")
            return jsonify({'error': 'Either task_id or subtask_id is required'}), 400
        
        # Verify assignment
        if subtask_id:
            print(f"🔍 Looking for subtask with ID: {subtask_id}")
            subtask = subtasks_col.find_one({'_id': oid(subtask_id)})
            if not subtask:
                print(f"❌ Subtask not found in database: {subtask_id}")
                return jsonify({'error': f'Subtask not found: {subtask_id}'}), 404
            
            if str(subtask.get('assigned_to')) != uid and subtask.get('assigned_to') != oid(uid):
                return jsonify({'error': 'You are not assigned to this subtask'}), 403
            
            task_id = str(subtask.get('task_id'))
        
        if task_id:
            task = tasks_col.find_one({'_id': oid(task_id)})
            if not task:
                return jsonify({'error': 'Task not found'}), 404
        
        # Handle file uploads
        uploaded_files = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            print(f"📎 Found {len(files)} files to upload")
            
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{uid}_{timestamp}_{filename}"
                    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                    
                    print(f"💾 Saving file: {filename} -> {filepath}")
                    file.save(filepath)
                    
                    if os.path.exists(filepath):
                        print(f"✅ File saved successfully: {filepath}")
                    else:
                        print(f"❌ File NOT saved: {filepath}")
                    
                    uploaded_files.append({
                        'original_name': filename,
                        'stored_name': unique_filename,
                        'path': filepath,  # Use 'path' key for consistency
                        'file_path': filepath,  # Keep for backward compatibility
                        'file_size': os.path.getsize(filepath),
                        'uploaded_at': datetime.utcnow()
                    })
                else:
                    print(f"⚠️ File rejected: {file.filename if file else 'No filename'}")
        
        # Create work upload record
        work_upload = {
            'user_id': oid(uid),
            'task_id': oid(task_id) if task_id else None,
            'subtask_id': oid(subtask_id) if subtask_id else None,
            'description': description,
            'progress': float(progress),
            'files': uploaded_files,
            'status': 'submitted',  # submitted, approved, rejected
            'approval_status': 'pending',
            'submitted_at': datetime.utcnow(),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = work_uploads_col.insert_one(work_upload)
        created = work_uploads_col.find_one({'_id': result.inserted_id})
        
        # Update subtask status if applicable
        if subtask_id:
            subtasks_col.update_one(
                {'_id': oid(subtask_id)},
                {'$set': {
                    'status': 'submitted',
                    'progress': float(progress),
                    'updated_at': datetime.utcnow()
                }}
            )
            
            # Notify manager
            if subtask.get('assigned_by'):
                create_notification(
                    user_id=str(subtask['assigned_by']),
                    notification_type='work_submitted',
                    title='Work Submitted',
                    message=f'{user.get("username")} submitted work for subtask',
                    subtask_id=subtask_id,
                    work_id=str(result.inserted_id)
                )
        
        # Update task progress
        if task_id:
            tasks_col.update_one(
                {'_id': oid(task_id)},
                {'$set': {
                    'progress': float(progress),
                    'updated_at': datetime.utcnow()
                }}
            )
            
            # Notify admin and project manager
            task = tasks_col.find_one({'_id': oid(task_id)})
            if task.get('created_by'):
                create_notification(
                    user_id=str(task['created_by']),
                    notification_type='work_submitted',
                    title='Work Submitted',
                    message=f'{user.get("username")} submitted work for task: {task.get("title")}',
                    task_id=task_id,
                    work_id=str(result.inserted_id)
                )
        
        # Create timeline entry
        create_timeline_entry(
            user_id=uid,
            action_type='work_uploaded',
            description=f'Uploaded work with {len(uploaded_files)} file(s) - Progress: {progress}%',
            task_id=task_id,
            subtask_id=subtask_id,
            metadata={'file_count': len(uploaded_files), 'progress': progress}
        )
        
        return jsonify({
            'message': 'Work uploaded successfully',
            'work_upload': to_str_id(created),
            'files_uploaded': len(uploaded_files)
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET WORK UPLOADS ----------
@mongo_work_bp.route('/work-uploads', methods=['GET'])
@jwt_required()
def get_work_uploads():
    """Get work uploads (filtered by role)"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        task_id = request.args.get('task_id')
        subtask_id = request.args.get('subtask_id')
        status = request.args.get('status')
        
        query = {}
        
        # Role-based filtering
        if user.get('role') == 'team_member':
            # Team members see only their own uploads
            query['user_id'] = oid(uid)
        elif user.get('role') in ['admin', 'project_manager']:
            # Admin/Manager see all uploads
            pass
        
        # Filter by task or subtask
        if task_id:
            query['task_id'] = oid(task_id)
        if subtask_id:
            query['subtask_id'] = oid(subtask_id)
        if status:
            query['approval_status'] = status
        
        cursor = work_uploads_col.find(query).sort('submitted_at', -1)
        uploads = []
        
        for upload in cursor:
            upload_dict = to_str_id(upload)
            
            # Add user info
            if upload.get('user_id'):
                uploader = users_col.find_one({'_id': oid(upload['user_id'])})
                if uploader:
                    upload_dict['uploader_name'] = f"{uploader.get('first_name', '')} {uploader.get('last_name', '')}".strip()
                    upload_dict['uploader_email'] = uploader.get('email')
            
            # Add task info
            if upload.get('task_id'):
                task = tasks_col.find_one({'_id': oid(upload['task_id'])})
                if task:
                    upload_dict['task_title'] = task.get('title')
            
            # Add subtask info
            if upload.get('subtask_id'):
                subtask = subtasks_col.find_one({'_id': oid(upload['subtask_id'])})
                if subtask:
                    upload_dict['subtask_title'] = subtask.get('title')
            
            uploads.append(upload_dict)
        
        return jsonify({'work_uploads': uploads}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- APPROVE/REJECT WORK (ADMIN/PM) ----------
@mongo_work_bp.route('/work-uploads/<work_id>/approve', methods=['POST'])
@jwt_required()
def approve_reject_work(work_id):
    """
    Admin/PM approves or rejects submitted work
    Body: {
        "action": "approve" or "reject",
        "feedback": "optional feedback message"
    }
    """
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is admin or project_manager
        if user.get('role') not in ['admin', 'project_manager']:
            return jsonify({'error': 'Only admins and project managers can approve/reject work'}), 403
        
        work_upload = work_uploads_col.find_one({'_id': oid(work_id)})
        if not work_upload:
            return jsonify({'error': 'Work upload not found'}), 404
        
        data = request.get_json() or {}
        action = data.get('action')  # 'approve' or 'reject'
        feedback = data.get('feedback', '')
        
        if action not in ['approve', 'reject']:
            return jsonify({'error': 'Action must be "approve" or "reject"'}), 400
        
        # Update work upload
        update_fields = {
            'approval_status': 'approved' if action == 'approve' else 'rejected',
            'reviewed_by': oid(uid),
            'review_feedback': feedback,
            'reviewed_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        work_uploads_col.update_one({'_id': oid(work_id)}, {'$set': update_fields})
        
        # Update subtask status if applicable
        if work_upload.get('subtask_id'):
            new_status = 'approved' if action == 'approve' else 'rejected'
            subtasks_col.update_one(
                {'_id': oid(work_upload['subtask_id'])},
                {'$set': {
                    'status': new_status,
                    'updated_at': datetime.utcnow()
                }}
            )
        
        # Notify the team member who submitted the work
        reviewer_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get('username', 'Admin')
        
        if work_upload.get('user_id'):
            create_notification(
                user_id=str(work_upload['user_id']),
                notification_type='work_reviewed',
                title=f'Work {action.capitalize()}d',
                message=f'{reviewer_name} has {action}d your work submission. {feedback}',
                task_id=str(work_upload.get('task_id')) if work_upload.get('task_id') else None,
                subtask_id=str(work_upload.get('subtask_id')) if work_upload.get('subtask_id') else None,
                work_id=work_id
            )
            
            # Send email notification
            submitter = users_col.find_one({'_id': work_upload.get('user_id')})
            if submitter and submitter.get('email'):
                try:
                    from flask_mail import Mail
                    mail = Mail(current_app)
                    
                    # Get task title
                    task_title = 'Your work'
                    if work_upload.get('subtask_id'):
                        subtask = subtasks_col.find_one({'_id': work_upload.get('subtask_id')})
                        if subtask:
                            task_title = subtask.get('title', 'Subtask')
                    elif work_upload.get('task_id'):
                        task = tasks_col.find_one({'_id': work_upload.get('task_id')})
                        if task:
                            task_title = task.get('title', 'Task')
                    
                    send_work_reviewed_notification(mail, submitter, action, feedback, task_title)
                    print(f"✅ Email sent to {submitter.get('email')} for work {action}")
                except Exception as e:
                    print(f"❌ Failed to send email: {e}")
        
        # Notify all PMs and Admins (except the reviewer)
        all_pms_admins = users_col.find({
            'role': {'$in': ['admin', 'project_manager']},
            '_id': {'$ne': oid(uid)}  # Don't notify the reviewer themselves
        })
        
        submitter = users_col.find_one({'_id': work_upload.get('user_id')})
        submitter_name = f"{submitter.get('first_name', '')} {submitter.get('last_name', '')}".strip() if submitter else 'Team member'
        
        # Get task/subtask title for context
        work_title = 'Work submission'
        if work_upload.get('subtask_id'):
            subtask = subtasks_col.find_one({'_id': oid(work_upload['subtask_id'])})
            if subtask:
                work_title = f"Subtask: {subtask.get('title', 'Untitled')}"
        elif work_upload.get('task_id'):
            task = tasks_col.find_one({'_id': oid(work_upload['task_id'])})
            if task:
                work_title = f"Task: {task.get('title', 'Untitled')}"
        
        for pm_admin in all_pms_admins:
            create_notification(
                user_id=str(pm_admin['_id']),
                notification_type='work_reviewed',
                title=f'Work {action.capitalize()}d by {reviewer_name}',
                message=f'{reviewer_name} {action}d {submitter_name}\'s work on {work_title}. Feedback: {feedback}',
                task_id=str(work_upload.get('task_id')) if work_upload.get('task_id') else None,
                subtask_id=str(work_upload.get('subtask_id')) if work_upload.get('subtask_id') else None,
                work_id=work_id
            )
        
        # Create timeline entry
        create_timeline_entry(
            user_id=uid,
            action_type=f'work_{action}d',
            description=f'{action.capitalize()}d work submission with feedback: {feedback[:50]}',
            task_id=str(work_upload.get('task_id')) if work_upload.get('task_id') else None,
            subtask_id=str(work_upload.get('subtask_id')) if work_upload.get('subtask_id') else None,
            metadata={'action': action, 'feedback': feedback}
        )
        
        updated = work_uploads_col.find_one({'_id': oid(work_id)})
        
        return jsonify({
            'message': f'Work {action}d successfully',
            'work_upload': to_str_id(updated)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- REJECT WORK (ADMIN/PM) ----------
@mongo_work_bp.route('/work-uploads/<work_id>/reject', methods=['POST'])
@jwt_required()
def reject_work(work_id):
    """Admin/PM rejects submitted work with feedback"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is admin or project_manager
        if user.get('role') not in ['admin', 'project_manager']:
            return jsonify({'error': 'Only admins and project managers can reject work'}), 403
        
        work_upload = work_uploads_col.find_one({'_id': oid(work_id)})
        if not work_upload:
            return jsonify({'error': 'Work upload not found'}), 404
        
        data = request.get_json() or {}
        feedback = data.get('feedback', 'Work needs revision')
        
        # Update work upload
        update_fields = {
            'approval_status': 'rejected',
            'reviewed_by': oid(uid),
            'review_feedback': feedback,
            'reviewed_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        work_uploads_col.update_one({'_id': oid(work_id)}, {'$set': update_fields})
        
        # Update subtask status if applicable
        if work_upload.get('subtask_id'):
            subtasks_col.update_one(
                {'_id': oid(work_upload['subtask_id'])},
                {'$set': {
                    'status': 'rejected',
                    'updated_at': datetime.utcnow()
                }}
            )
        
        # Notify the team member who submitted the work
        reviewer_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get('username', 'Admin')
        
        if work_upload.get('user_id'):
            create_notification(
                user_id=str(work_upload['user_id']),
                notification_type='work_rejected',
                title='Work Rejected',
                message=f'{reviewer_name} has rejected your work submission. Feedback: {feedback}',
                task_id=str(work_upload.get('task_id')) if work_upload.get('task_id') else None,
                subtask_id=str(work_upload.get('subtask_id')) if work_upload.get('subtask_id') else None,
                work_id=work_id
            )
            
            # Send email notification
            submitter = users_col.find_one({'_id': work_upload.get('user_id')})
            if submitter and submitter.get('email'):
                try:
                    from flask_mail import Mail
                    mail = Mail(current_app)
                    
                    # Get task title
                    task_title = 'Your work'
                    if work_upload.get('subtask_id'):
                        subtask = subtasks_col.find_one({'_id': work_upload.get('subtask_id')})
                        if subtask:
                            task_title = subtask.get('title', 'Subtask')
                    elif work_upload.get('task_id'):
                        task = tasks_col.find_one({'_id': work_upload.get('task_id')})
                        if task:
                            task_title = task.get('title', 'Task')
                    
                    send_work_reviewed_notification(mail, submitter, 'reject', feedback, task_title)
                    print(f"✅ Email sent to {submitter.get('email')} for work rejection")
                except Exception as e:
                    print(f"❌ Failed to send email: {e}")
        
        # Notify all PMs and Admins (except the reviewer)
        all_pms_admins = users_col.find({
            'role': {'$in': ['admin', 'project_manager']},
            '_id': {'$ne': oid(uid)}  # Don't notify the reviewer themselves
        })
        
        submitter = users_col.find_one({'_id': work_upload.get('user_id')})
        submitter_name = f"{submitter.get('first_name', '')} {submitter.get('last_name', '')}".strip() if submitter else 'Team member'
        
        # Get task/subtask title for context
        work_title = 'Work submission'
        if work_upload.get('subtask_id'):
            subtask = subtasks_col.find_one({'_id': oid(work_upload['subtask_id'])})
            if subtask:
                work_title = f"Subtask: {subtask.get('title', 'Untitled')}"
        elif work_upload.get('task_id'):
            task = tasks_col.find_one({'_id': oid(work_upload['task_id'])})
            if task:
                work_title = f"Task: {task.get('title', 'Untitled')}"
        
        for pm_admin in all_pms_admins:
            create_notification(
                user_id=str(pm_admin['_id']),
                notification_type='work_rejected',
                title=f'Work Rejected by {reviewer_name}',
                message=f'{reviewer_name} rejected {submitter_name}\'s work on {work_title}. Feedback: {feedback}',
                task_id=str(work_upload.get('task_id')) if work_upload.get('task_id') else None,
                subtask_id=str(work_upload.get('subtask_id')) if work_upload.get('subtask_id') else None,
                work_id=work_id
            )
        
        # Create timeline entry
        create_timeline_entry(
            user_id=uid,
            action_type='work_rejected',
            description=f'Rejected work submission with feedback: {feedback[:50]}',
            task_id=str(work_upload.get('task_id')) if work_upload.get('task_id') else None,
            subtask_id=str(work_upload.get('subtask_id')) if work_upload.get('subtask_id') else None,
            metadata={'feedback': feedback}
        )
        
        updated = work_uploads_col.find_one({'_id': oid(work_id)})
        
        return jsonify({
            'message': 'Work rejected successfully',
            'work_upload': to_str_id(updated)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET MY WORK UPLOADS (TEAM MEMBER) ----------
@mongo_work_bp.route('/my-work-uploads', methods=['GET'])
@jwt_required()
def get_my_work_uploads():
    """Get all work uploads by current user"""
    try:
        uid = get_jwt_identity()
        
        cursor = work_uploads_col.find({'user_id': oid(uid)}).sort('submitted_at', -1)
        uploads = []
        
        for upload in cursor:
            upload_dict = to_str_id(upload)
            
            # Add task info
            if upload.get('task_id'):
                task = tasks_col.find_one({'_id': oid(upload['task_id'])})
                if task:
                    upload_dict['task_title'] = task.get('title')
            
            # Add subtask info
            if upload.get('subtask_id'):
                subtask = subtasks_col.find_one({'_id': oid(upload['subtask_id'])})
                if subtask:
                    upload_dict['subtask_title'] = subtask.get('title')
            
            # Add reviewer info if reviewed
            if upload.get('reviewed_by'):
                reviewer = users_col.find_one({'_id': oid(upload['reviewed_by'])})
                if reviewer:
                    upload_dict['reviewer_name'] = f"{reviewer.get('first_name', '')} {reviewer.get('last_name', '')}".strip()
            
            uploads.append(upload_dict)
        
        return jsonify({'work_uploads': uploads}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- GET PENDING APPROVALS (ADMIN) ----------
@mongo_work_bp.route('/work-uploads/pending', methods=['GET'])
@jwt_required()
def get_pending_approvals():
    """Get all work uploads pending approval (Admin only)"""
    try:
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        cursor = work_uploads_col.find({'approval_status': 'pending'}).sort('submitted_at', 1)
        uploads = []
        
        for upload in cursor:
            upload_dict = to_str_id(upload)
            
            # Add user info
            if upload.get('user_id'):
                uploader = users_col.find_one({'_id': oid(upload['user_id'])})
                if uploader:
                    upload_dict['uploader_name'] = f"{uploader.get('first_name', '')} {uploader.get('last_name', '')}".strip()
                    upload_dict['uploader_email'] = uploader.get('email')
            
            # Add task info
            if upload.get('task_id'):
                task = tasks_col.find_one({'_id': oid(upload['task_id'])})
                if task:
                    upload_dict['task_title'] = task.get('title')
            
            uploads.append(upload_dict)
        
        return jsonify({
            'pending_approvals': uploads,
            'count': len(uploads)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- DOWNLOAD WORK FILE ----------
@mongo_work_bp.route('/work-uploads/<work_id>/files/<file_index>', methods=['GET'])
@jwt_required()
def download_work_file(work_id, file_index):
    """Download a specific file from a work submission"""
    try:
        from flask import send_file
        import os
        
        uid = get_jwt_identity()
        user = users_col.find_one({'_id': oid(uid)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        work_upload = work_uploads_col.find_one({'_id': oid(work_id)})
        if not work_upload:
            return jsonify({'error': 'Work upload not found'}), 404
        
        # Check permissions: admin, PM, or the uploader themselves
        is_authorized = (
            user.get('role') in ['admin', 'project_manager'] or
            work_upload.get('user_id') == oid(uid)
        )
        
        if not is_authorized:
            return jsonify({'error': 'Unauthorized to access this file'}), 403
        
        files = work_upload.get('files', [])
        try:
            file_idx = int(file_index)
            if file_idx < 0 or file_idx >= len(files):
                return jsonify({'error': 'File index out of range'}), 404
        except ValueError:
            return jsonify({'error': 'Invalid file index'}), 400
        
        file_info = files[file_idx]
        file_path = file_info.get('path') or file_info.get('file_path')  # Try both keys
        original_name = file_info.get('original_name', 'download')
        
        print(f"📂 Attempting to download file: {original_name}")
        print(f"📍 File path: {file_path}")
        print(f"✓ File exists: {os.path.exists(file_path) if file_path else False}")
        
        if not file_path:
            return jsonify({'error': 'File path not found in database'}), 404
            
        if not os.path.exists(file_path):
            return jsonify({'error': f'File not found on server: {file_path}'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=original_name
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
