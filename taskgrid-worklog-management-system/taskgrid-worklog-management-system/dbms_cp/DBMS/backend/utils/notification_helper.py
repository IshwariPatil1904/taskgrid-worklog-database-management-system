"""
Enhanced Notification System for TaskGrid
Handles email and in-app notifications for all events
"""
from flask_mail import Message
from datetime import datetime
from utils.mongo_db import notifications_col, users_col, oid
import os


def send_email_notification(mail, recipient_email, subject, body, html_body=None):
    """
    Send email notification
    Args:
        mail: Flask-Mail instance
        recipient_email: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            body=body,
            html=html_body
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send email to {recipient_email}: {e}")
        return False


def create_notification(user_id, notification_type, title, message, task_id=None, subtask_id=None, work_id=None):
    """
    Create an in-app notification
    """
    try:
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
        result = notifications_col.insert_one(notification)
        print(f"✅ Notification created for user {user_id}: {title}")
        return True
    except Exception as e:
        print(f"❌ Failed to create notification: {e}")
        return False


def send_task_assigned_notification(mail, manager_user, task_title, assigner_name):
    """Send notification when a task is assigned to a manager"""
    subject = "🎯 New Task Assigned - TaskGrid"
    
    body = f"""Hello {manager_user.get('first_name', 'User')},

You have been assigned a new task on TaskGrid:

Task: {task_title}
Assigned by: {assigner_name}

Please log in to TaskGrid to view details and create subtasks for your team.

Dashboard: {os.getenv('APP_URL', 'http://localhost:5000')}/dashboard

Best regards,
TaskGrid Team
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
            <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #06d7ff; margin-top: 0;">🎯 New Task Assigned</h2>
                <p>Hello {manager_user.get('first_name', 'User')},</p>
                <p>You have been assigned a new task on TaskGrid:</p>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #06d7ff; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Task:</strong> {task_title}</p>
                    <p style="margin: 5px 0;"><strong>Assigned by:</strong> {assigner_name}</p>
                </div>
                
                <p>Please log in to TaskGrid to view details and create subtasks for your team.</p>
                
                <a href="{os.getenv('APP_URL', 'http://localhost:5000')}/dashboard" 
                   style="display: inline-block; padding: 12px 24px; background-color: #06d7ff; color: white; 
                          text-decoration: none; border-radius: 5px; margin-top: 20px;">
                    View Dashboard
                </a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    TaskGrid Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_notification(mail, manager_user.get('email'), subject, body, html_body)


def send_subtask_assigned_notification(mail, team_member, subtask_title, percentage, manager_name):
    """Send notification when a subtask is assigned to a team member"""
    subject = "📋 New Subtask Assigned - TaskGrid"
    
    body = f"""Hello {team_member.get('first_name', 'User')},

You have been assigned a new subtask on TaskGrid:

Subtask: {subtask_title}
Your Share: {percentage}%
Assigned by: {manager_name}

Please log in to TaskGrid to view details and start working on your subtask.

Dashboard: {os.getenv('APP_URL', 'http://localhost:5000')}/dashboard

Best regards,
TaskGrid Team
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
            <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #7b2cff; margin-top: 0;">📋 New Subtask Assigned</h2>
                <p>Hello {team_member.get('first_name', 'User')},</p>
                <p>You have been assigned a new subtask on TaskGrid:</p>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #7b2cff; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Subtask:</strong> {subtask_title}</p>
                    <p style="margin: 5px 0;"><strong>Your Share:</strong> {percentage}%</p>
                    <p style="margin: 5px 0;"><strong>Assigned by:</strong> {manager_name}</p>
                </div>
                
                <p>Please log in to TaskGrid to view details and start working on your subtask.</p>
                
                <a href="{os.getenv('APP_URL', 'http://localhost:5000')}/dashboard" 
                   style="display: inline-block; padding: 12px 24px; background-color: #7b2cff; color: white; 
                          text-decoration: none; border-radius: 5px; margin-top: 20px;">
                    View Dashboard
                </a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    TaskGrid Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_notification(mail, team_member.get('email'), subject, body, html_body)


def send_work_submitted_notification(mail, recipient, submitter_name, task_title):
    """Send notification when work is submitted"""
    subject = "📤 Work Submitted for Review - TaskGrid"
    
    body = f"""Hello,

{submitter_name} has submitted work for review on TaskGrid:

Task: {task_title}

Please log in to TaskGrid to review and approve/reject the submission.

Dashboard: {os.getenv('APP_URL', 'http://localhost:5000')}/dashboard

Best regards,
TaskGrid Team
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
            <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #2ad39a; margin-top: 0;">📤 Work Submitted for Review</h2>
                <p>Hello,</p>
                <p>{submitter_name} has submitted work for review on TaskGrid:</p>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #2ad39a; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Task:</strong> {task_title}</p>
                    <p style="margin: 5px 0;"><strong>Submitted by:</strong> {submitter_name}</p>
                </div>
                
                <p>Please log in to TaskGrid to review and approve/reject the submission.</p>
                
                <a href="{os.getenv('APP_URL', 'http://localhost:5000')}/dashboard" 
                   style="display: inline-block; padding: 12px 24px; background-color: #2ad39a; color: white; 
                          text-decoration: none; border-radius: 5px; margin-top: 20px;">
                    Review Submission
                </a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    TaskGrid Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_notification(mail, recipient.get('email'), subject, body, html_body)


def send_work_reviewed_notification(mail, team_member, action, feedback, task_title):
    """Send notification when work is approved/rejected"""
    action_emoji = "✅" if action == "approve" else "❌"
    action_text = "Approved" if action == "approve" else "Rejected"
    action_color = "#2ad39a" if action == "approve" else "#ff5d6c"
    
    subject = f"{action_emoji} Work {action_text} - TaskGrid"
    
    body = f"""Hello {team_member.get('first_name', 'User')},

Your work submission has been {action}d by the admin:

Task: {task_title}
Status: {action_text}
Feedback: {feedback}

Please log in to TaskGrid to view details.

Dashboard: {os.getenv('APP_URL', 'http://localhost:5000')}/dashboard

Best regards,
TaskGrid Team
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
            <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: {action_color}; margin-top: 0;">{action_emoji} Work {action_text}</h2>
                <p>Hello {team_member.get('first_name', 'User')},</p>
                <p>Your work submission has been {action}d by the admin:</p>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid {action_color}; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Task:</strong> {task_title}</p>
                    <p style="margin: 5px 0;"><strong>Status:</strong> <span style="color: {action_color};">{action_text}</span></p>
                    {f'<p style="margin: 5px 0;"><strong>Feedback:</strong> {feedback}</p>' if feedback else ''}
                </div>
                
                <p>Please log in to TaskGrid to view details.</p>
                
                <a href="{os.getenv('APP_URL', 'http://localhost:5000')}/dashboard" 
                   style="display: inline-block; padding: 12px 24px; background-color: {action_color}; color: white; 
                          text-decoration: none; border-radius: 5px; margin-top: 20px;">
                    View Dashboard
                </a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    TaskGrid Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_notification(mail, team_member.get('email'), subject, body, html_body)


def send_deadline_reminder_notification(mail, user, task_title, due_date):
    """Send deadline reminder notification"""
    subject = "⏰ Task Deadline Reminder - TaskGrid"
    
    body = f"""Hello {user.get('first_name', 'User')},

This is a reminder that your task deadline is approaching:

Task: {task_title}
Due Date: {due_date}

Please log in to TaskGrid to update your progress.

Dashboard: {os.getenv('APP_URL', 'http://localhost:5000')}/dashboard

Best regards,
TaskGrid Team
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
            <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #ffb020; margin-top: 0;">⏰ Task Deadline Reminder</h2>
                <p>Hello {user.get('first_name', 'User')},</p>
                <p>This is a reminder that your task deadline is approaching:</p>
                
                <div style="background-color: #fff8e8; padding: 15px; border-left: 4px solid #ffb020; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Task:</strong> {task_title}</p>
                    <p style="margin: 5px 0;"><strong>Due Date:</strong> {due_date}</p>
                </div>
                
                <p>Please log in to TaskGrid to update your progress.</p>
                
                <a href="{os.getenv('APP_URL', 'http://localhost:5000')}/dashboard" 
                   style="display: inline-block; padding: 12px 24px; background-color: #ffb020; color: white; 
                          text-decoration: none; border-radius: 5px; margin-top: 20px;">
                    Update Progress
                </a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    TaskGrid Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_notification(mail, user.get('email'), subject, body, html_body)


def send_admin_task_notification(mail, manager, task_title, task_description, due_date, admin_name):
    """Send notification when Admin creates a main task for all Project Managers"""
    subject = "🎯 New Main Task Assigned by Admin - TaskGrid"
    
    body = f"""Hello {manager.get('first_name', 'Project Manager')},

A new main task has been assigned to you by Admin on TaskGrid:

Task: {task_title}
Description: {task_description}
Deadline: {due_date}
Assigned by: {admin_name}

Action Required:
1. Review the task details
2. Create subtasks for your team members
3. Assign percentage allocation to each subtask
4. Set individual deadlines for team members

Please log in to TaskGrid to begin creating subtasks and assigning work.

Dashboard: {os.getenv('APP_URL', 'http://localhost:5000')}/dashboard

Best regards,
TaskGrid Team
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4;">
            <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #06d7ff; margin-top: 0;">🎯 New Main Task Assigned by Admin</h2>
                <p>Hello {manager.get('first_name', 'Project Manager')},</p>
                <p>A new main task has been assigned to you by Admin on TaskGrid:</p>
                
                <div style="background-color: #f0f9ff; padding: 20px; border-left: 4px solid #06d7ff; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Task:</strong> {task_title}</p>
                    <p style="margin: 10px 0;"><strong>Description:</strong> {task_description[:200]}{'...' if len(task_description) > 200 else ''}</p>
                    <p style="margin: 5px 0;"><strong>Deadline:</strong> {due_date}</p>
                    <p style="margin: 5px 0;"><strong>Assigned by:</strong> {admin_name}</p>
                </div>
                
                <div style="background-color: #fff8e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #ff9900;">📋 Action Required:</h3>
                    <ol style="margin: 10px 0; padding-left: 20px;">
                        <li>Review the task details</li>
                        <li>Create subtasks for your team members</li>
                        <li>Assign percentage allocation to each subtask (total must be 100%)</li>
                        <li>Set individual deadlines for team members</li>
                    </ol>
                </div>
                
                <p>Please log in to TaskGrid to begin creating subtasks and assigning work to your team.</p>
                
                <a href="{os.getenv('APP_URL', 'http://localhost:5000')}/dashboard" 
                   style="display: inline-block; padding: 12px 24px; background-color: #06d7ff; color: white; 
                          text-decoration: none; border-radius: 5px; margin-top: 20px;">
                    View Task & Create Subtasks
                </a>
                
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    Best regards,<br>
                    TaskGrid Team
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_notification(mail, manager.get('email'), subject, body, html_body)
