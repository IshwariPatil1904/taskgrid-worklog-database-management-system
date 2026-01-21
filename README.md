# TaskGrid - Worklog Management System

A comprehensive worklog and task management system built with Flask and MongoDB, designed to streamline project tracking, task assignment, and team collaboration.

## 🚀 Features

- **User Authentication & Authorization**
  - Secure JWT-based authentication
  - Role-based access control (Admin, User)
  - User registration and login

- **Task Management**
  - Create, update, and delete tasks
  - Assign tasks to team members
  - Set task priorities and deadlines
  - Track task status and progress
  - Subtask creation and management

- **Admin Dashboard**
  - Comprehensive project overview
  - User management
  - Task approval workflow
  - Analytics and reporting

- **Notifications**
  - Automated deadline alerts
  - Real-time notification system
  - Email notifications via Flask-Mail

- **Timeline & Work Tracking**
  - Visual timeline representation
  - Work log entries
  - Progress tracking

- **Reports & Analytics**
  - Performance analysis
  - Task completion metrics
  - Data visualization with charts

## 🛠️ Tech Stack

### Backend
- **Framework:** Flask 3.1.1
- **Database:** MongoDB (PyMongo 4.8.0)
- **Authentication:** Flask-JWT-Extended
- **Email:** Flask-Mail
- **Scheduling:** APScheduler
- **API:** Flask-RESTful

### Frontend
- HTML5, CSS3, JavaScript
- Responsive design
- Interactive dashboards

## 📋 Prerequisites

- Python 3.8 or higher
- MongoDB instance (local or cloud)
- pip package manager

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/IshwariPatil1904/taskgrid-worklog-database-management-system.git
   cd taskgrid-worklog-database-management-system
   ```

2. **Navigate to the backend directory**
   ```bash
   cd taskgrid-worklog-management-system/dbms_cp/DBMS/backend
   ```

3. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**
   
   Create a `.env` file in the backend directory based on `.env.example`:
   ```env
   MONGO_URI=your_mongodb_connection_string
   JWT_SECRET_KEY=your_secret_key
   MAIL_SERVER=your_mail_server
   MAIL_PORT=587
   MAIL_USERNAME=your_email
   MAIL_PASSWORD=your_email_password
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

```
taskgrid-worklog-management-system/
├── dbms_cp/
│   └── DBMS/
│       ├── backend/
│       │   ├── app.py              # Main application file
│       │   ├── requirements.txt     # Python dependencies
│       │   ├── render.yaml          # Deployment configuration
│       │   ├── routes/              # API route handlers
│       │   │   ├── mongo_auth.py
│       │   │   ├── mongo_tasks.py
│       │   │   ├── mongo_admin.py
│       │   │   ├── mongo_notifications.py
│       │   │   ├── mongo_subtasks.py
│       │   │   └── ...
│       │   ├── utils/               # Utility functions
│       │   │   ├── mongo_db.py
│       │   │   ├── helpers.py
│       │   │   ├── validators.py
│       │   │   └── deadline_notifier.py
│       │   ├── templates/           # HTML templates
│       │   │   ├── dashboard/
│       │   │   ├── signup/
│       │   │   ├── projects/
│       │   │   └── ...
│       │   └── static/              # Static assets
│       │       └── js/
│       └── frontend/
│           └── js/
└── README.md
```

## 🔑 Key Dependencies

- **Flask** - Web framework
- **PyMongo** - MongoDB driver
- **Flask-JWT-Extended** - JWT authentication
- **APScheduler** - Background task scheduling
- **Flask-CORS** - Cross-Origin Resource Sharing
- **scikit-learn** - Machine learning utilities
- **matplotlib** - Data visualization
- **gunicorn** - Production WSGI server

## 🚀 Deployment

The application is configured for deployment on Render using the included `render.yaml` file.

### Deploy to Render:

1. Push your code to GitHub
2. Connect your GitHub repository to Render
3. Configure environment variables in Render dashboard
4. Deploy!

## 📝 API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout

### Tasks
- `GET /tasks` - Get all tasks
- `POST /tasks` - Create new task
- `PUT /tasks/<id>` - Update task
- `DELETE /tasks/<id>` - Delete task

### Admin
- `GET /admin/users` - Get all users
- `POST /admin/approve` - Approve task
- `GET /admin/analytics` - Get analytics data

### Notifications
- `GET /notifications` - Get user notifications
- `POST /notifications/mark-read` - Mark notification as read

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👨‍💻 Author

**Ishwari Patil**
- GitHub: [@IshwariPatil1904](https://github.com/IshwariPatil1904)

## 🙏 Acknowledgments

- Flask documentation and community
- MongoDB documentation
- All contributors and supporters

## 📧 Contact

For any queries or suggestions, please open an issue or contact through GitHub.

---

**Note:** Make sure to keep your `.env` file secure and never commit it to version control.
