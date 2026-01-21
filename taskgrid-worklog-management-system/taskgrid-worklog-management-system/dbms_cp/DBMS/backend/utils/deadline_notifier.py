# utils/deadline_notifier.py
from datetime import datetime, timedelta
from flask_mail import Message
from bson import ObjectId
import traceback
import os

def parse_maybe_datetime(v):
    """Return a datetime object if v is datetime or ISO string. Otherwise None."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    # if it's a string attempt to parse common ISO formats
    try:
        # strip timezone Z if present
        s = str(v)
        if s.endswith('Z'):
            s = s[:-1]
        # Try parsing common formats
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except:
                pass
    except Exception:
        pass
    return None

def send_deadline_alerts(app, db, mail):
    """
    Send email reminders for tasks due within 24 hours and create notification documents.
    Safe: tolerant of due_date types, avoids duplicate notifications within 24h.
    """
    with app.app_context():
        try:
            now = datetime.utcnow()
            next_24h = now + timedelta(hours=24)
            yesterday = now - timedelta(hours=24)
            
            print(f"\n🔍 Checking for tasks due between {yesterday.strftime('%Y-%m-%d %H:%M')} and {next_24h.strftime('%Y-%m-%d %H:%M')}")

            # Build a query that finds tasks with due_date - including overdue and upcoming
            cursor = db.tasks.find({"due_date": {"$exists": True}, "status": {"$ne": "completed"}})
            
            # Fetch all recently sent notifications at once for faster lookup
            recent_notifications = {}
            twelve_hours_ago = datetime.utcnow() - timedelta(hours=12)
            for notif in db.notifications.find({
                "type": "deadline",
                "created_at": {"$gte": twelve_hours_ago}
            }):
                recent_notifications[str(notif.get("task_id"))] = True
            
            task_count = 0
            notified_count = 0

            for task in cursor:
                try:
                    task_count += 1
                    due_raw = task.get("due_date")
                    due_dt = parse_maybe_datetime(due_raw)
                    if due_dt is None:
                        # skip tasks with invalid dates
                        print(f"⚠️ Task {task.get('_id')} has invalid due_date: {due_raw}")
                        continue

                    # Accept tasks where due is within 24 hours past or future
                    # This covers overdue tasks (up to 24h ago) and upcoming tasks (next 24h)
                    if not (yesterday <= due_dt <= next_24h):
                        continue
                    
                    print(f"📋 Found task: {task.get('title')} due {due_dt.strftime('%Y-%m-%d %H:%M')}")
                    
                    notified_count += 1

                    # Find the assigned user first, then fallback to creator/owner
                    user_id = task.get("assigned_to") or task.get("user_id") or task.get("owner_id") or task.get("created_by")
                    if not user_id:
                        # no user - skip
                        continue

                    # ensure ObjectId lookup
                    user_obj = None
                    try:
                        if isinstance(user_id, ObjectId):
                            user_obj = db.users.find_one({"_id": user_id})
                        else:
                            user_obj = db.users.find_one({"_id": ObjectId(user_id)})
                    except Exception:
                        # maybe user_id is a string or already an ObjectId
                        try:
                            user_obj = db.users.find_one({"_id": user_id})
                        except:
                            pass

                    if not user_obj:
                        app.logger.warning(f"User not found for task {task.get('_id')}, user_id: {user_id}")
                        continue
                    
                    user_email = user_obj.get("email")
                    if not user_email:
                        app.logger.warning(f"No email found for user {user_obj.get('_id')}")
                        continue

                    task_name = task.get("title", "Untitled Task")
                    due_str = due_dt.strftime("%Y-%m-%d %H:%M UTC")
                    user_name = user_obj.get("first_name", "") or user_obj.get("username", "User")

                    # Check if already notified recently (using pre-fetched data)
                    if str(task["_id"]) in recent_notifications:
                        # already notified recently
                        continue

                    # Send email only if enabled (send immediately without waiting)
                    email_sent = False
                    if os.getenv('ENABLE_EMAIL', 'false').lower() == 'true':
                        subject = "⏰ TaskGrid Reminder: Task Deadline Approaching"
                        body = (f"Hello {user_name},\n\n"
                                f"This is a reminder that your task '{task_name}' is due on {due_str}.\n\n"
                                f"Please log in to TaskGrid to update your progress:\n"
                                f"{os.getenv('APP_URL', 'http://localhost:5000')}/dashboard\n\n"
                                f"Task Details:\n"
                                f"- Title: {task_name}\n"
                                f"- Due Date: {due_str}\n"
                                f"- Status: {task.get('status', 'In Progress')}\n\n"
                                "Best regards,\n"
                                "TaskGrid Team")

                        msg = Message(subject=subject, recipients=[user_email], body=body)
                        try:
                            mail.send(msg)
                            email_sent = True
                            print(f"📧 Email sent to {user_email} for task: {task_name}")
                        except Exception as e:
                            app.logger.error(f"❌ Failed to send email to {user_email}: {e}")
                            print(f"⚠️ Email failed to {user_email}: {e}")

                    # Log notification in DB (only if email was sent or email is disabled)
                    if email_sent or os.getenv('ENABLE_EMAIL', 'false').lower() != 'true':
                        db.notifications.insert_one({
                            "user_id": ObjectId(user_obj["_id"]) if not isinstance(user_obj["_id"], ObjectId) else user_obj["_id"],
                            "task_id": task["_id"],
                            "message": f"⏰ Task '{task_name}' is due on {due_str}",
                            "timestamp": datetime.utcnow(),
                            "type": "deadline",
                            "status": "unread",
                            "created_at": datetime.utcnow(),
                            "user_email": user_email,
                            "user_name": user_name
                        })
                        # Mark this task as notified in our cache
                        recent_notifications[str(task["_id"])] = True

                except Exception as task_e:
                    app.logger.error(f"Error processing task {task.get('_id')}: {task_e}\n{traceback.format_exc()}")

            print(f"✅ Deadline check complete: {task_count} tasks checked, {notified_count} notifications sent")
            app.logger.info(f"Deadline notifier: scan finished. Checked {task_count} tasks, sent {notified_count} notifications.")
        except Exception as e:
            app.logger.error(f"send_deadline_alerts failed: {e}\n{traceback.format_exc()}")
            print(f"❌ Deadline notifier error: {e}")
