# TaskGrid Flask Application (MongoDB version)
from flask import Flask, jsonify, render_template, redirect, url_for, request, current_app
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, verify_jwt_in_request, get_jwt_identity
)
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Custom imports
from utils.deadline_notifier import send_deadline_alerts
from routes.mongo_auth import mongo_auth_bp
from routes.mongo_data import mongo_data_bp
from routes.mongo_tasks import mongo_tasks_bp
from utils.mongo_db import init_mongo

# Flask extensions
mail = Mail()

def get_mail_instance():
    """Helper to get mail instance from app context"""
    return mail


def create_app():
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates"
    )

    # Enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})

    # JWT Config
    app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
    app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production'
    jwt = JWTManager(app)

    # Initialize MongoDB
    db = init_mongo()
    if db is None:
        raise RuntimeError("❌ MongoDB initialization failed.")
    print(f"✅ MongoDB connected: {db.name}")

    # -------------------------------
    # Email Configuration (using environment variables)
    # -------------------------------
    app.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),       # e.g. taskgridd@gmail.com
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),       # your Google App Password
        MAIL_DEFAULT_SENDER=('TaskGrid', os.getenv('MAIL_USERNAME'))
    )

    mail.init_app(app)

    # -------------------------------
    # Automated Deadline Email Check (every 1 hour)
    # -------------------------------
    scheduler = BackgroundScheduler(daemon=True)

    def run_email_job():
        try:
            send_deadline_alerts(app, db, mail)
        except Exception as e:
            print(f"⚠️ Error running email alert job: {e}")

    scheduler.add_job(run_email_job, trigger='interval', minutes=1)  # Check every minute
    scheduler.start()
    print("⏰ Deadline notifier scheduler started (checks every minute).")
    
    # Run immediately on startup
    try:
        print("🔔 Running initial notification check...")
        run_email_job()
    except Exception as e:
        print(f"⚠️ Initial notification check failed: {e}")

    # -------------------------------
    # Register Blueprints
    # -------------------------------
    app.register_blueprint(mongo_auth_bp, url_prefix="/auth")
    app.register_blueprint(mongo_data_bp, url_prefix="/data")
    app.register_blueprint(mongo_tasks_bp, url_prefix="/data")
    
    # ✅ Register new enhanced feature blueprints
    from routes.mongo_subtasks import mongo_subtasks_bp
    from routes.mongo_work import mongo_work_bp
    from routes.mongo_timeline import mongo_timeline_bp
    from routes.mongo_admin import mongo_admin_bp
    from routes.mongo_notifications import mongo_notifications_bp
    from routes.mongo_admin_tasks import mongo_admin_tasks_bp  # NEW: Admin task workflow
    from routes.mongo_approval import mongo_approval_bp  # NEW: Complete approval workflow
    
    app.register_blueprint(mongo_subtasks_bp, url_prefix="/data")
    app.register_blueprint(mongo_work_bp, url_prefix="/data")
    app.register_blueprint(mongo_timeline_bp, url_prefix="/data")
    app.register_blueprint(mongo_admin_bp, url_prefix="/data")
    app.register_blueprint(mongo_notifications_bp, url_prefix="/data")
    app.register_blueprint(mongo_admin_tasks_bp, url_prefix="/data")  # NEW: Admin task workflow
    app.register_blueprint(mongo_approval_bp, url_prefix="/data")  # NEW: Complete approval workflow

    # -------------------------------
    # FRONTEND ROUTES
    # -------------------------------
    @app.route('/')
    def serve_landing():
        return render_template('landing_page/2-working.html')

    @app.route('/login')
    def serve_login():
        return redirect(url_for('serve_landing'))

    @app.route('/signup')
    def serve_signup():
        return render_template('signup/signup.html')

    @app.route('/register')
    def serve_register():
        return render_template('register.html')

    @app.route('/dashboard')
    def serve_dashboard():
        # Let the frontend handle authentication via localStorage token
        # The dashboard HTML will check for token and redirect if not found
        return render_template('dashboard/dashboard-functional.html')

    # ✅ Dashboard subpaths
    @app.route('/dashboard/<path:subpath>')
    def serve_dashboard_subpath(subpath):
        return render_template('dashboard/dashboard-functional.html')

    @app.route('/dashboard/dashboard-functional.html')
    def dashboard_redirect_fix():
        return redirect(url_for('serve_dashboard'))

    # ✅ Reports Page
    @app.route('/reports/analysis')
    def serve_reports():
        return render_template('reports/analysis.html')
    
    # ✅ Subtask Creation Page (for Project Managers)
    @app.route('/subtasks/create')
    def serve_create_subtasks():
        return render_template('subtasks/create_subtasks.html')
    
    # ✅ Project Details Page (for Admins to view and approve work)
    @app.route('/projects/details')
    def serve_project_details():
        return render_template('projects/project_details.html')

    # ✅ Notifications Page
    @app.route('/notifications')
    def serve_notifications():
        return render_template('notification.html')

    # ✅ API endpoint to fetch stored notifications
    @app.route('/data/notifications', methods=['GET'])
    def get_notifications():
        """Return stored notifications from MongoDB"""
        notifs = list(db.notifications.find().sort("timestamp", -1))
        for n in notifs:
            n["_id"] = str(n["_id"])
            n["user_id"] = str(n.get("user_id", ""))
            n["task_id"] = str(n.get("task_id", ""))
        return jsonify({"notifications": notifs}), 200

    # ✅ 404 handler
    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    # ✅ Health check
    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy', 'message': 'TaskGrid API is running'}), 200
    
    # ✅ Manual notification trigger (for testing)
    @app.route('/test/notifications', methods=['GET'])
    def test_notifications():
        """Manually trigger notification check"""
        try:
            run_email_job()
            return jsonify({'status': 'success', 'message': 'Notification check triggered'}), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization token is required'}), 401

    # ✅ TEST EMAIL ROUTE (for debugging only)
    @app.route('/test-email')
    def test_email():
        """Send a test email to verify Flask-Mail setup"""
        import os
        if os.getenv('ENABLE_EMAIL', 'false').lower() != 'true':
            return jsonify({"error": "Email is disabled. Set ENABLE_EMAIL=true in .env to enable email notifications."}), 400
        
        from flask_mail import Message
        to = request.args.get("to")
        if not to:
            return jsonify({"error": "Please provide ?to=email@example.com"}), 400

        try:
            msg = Message(
                subject="✅ TaskGrid Email Test Successful",
                recipients=[to],
                body="Hello from TaskGrid! 🎉\n\nYour email configuration is working correctly."
            )
            mail.send(msg)
            print(f"✅ Test email sent to {to}")
            return jsonify({"message": f"Test email sent successfully to {to}!"}), 200
        except Exception as e:
            print(f"❌ Failed to send email: {str(e)}")
            return jsonify({"error": f"Failed to send email: {str(e)}"}), 500




    return app


# -------------------------------------------------------------
# RUN SERVER
# -------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    print("🚀 TaskGrid Flask app with frontend + MongoDB is running...")
    app.run(debug=True, host="0.0.0.0", port=5000)