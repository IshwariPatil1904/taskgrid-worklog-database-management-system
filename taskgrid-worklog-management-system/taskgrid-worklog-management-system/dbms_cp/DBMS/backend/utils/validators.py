import re
from datetime import datetime

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    return True, "Password is valid"

def validate_date_format(date_string):
    """Validate date format (YYYY-MM-DD)"""
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_time_format(time_string):
    """Validate time format (HH:MM:SS)"""
    try:
        datetime.strptime(time_string, '%H:%M:%S')
        return True
    except ValueError:
        return False

def validate_user_role(role):
    """Validate user role"""
    valid_roles = ['admin', 'manager', 'team_member']
    return role in valid_roles

def validate_project_status(status):
    """Validate project status"""
    valid_statuses = ['active', 'completed', 'on_hold', 'cancelled']
    return status in valid_statuses

def validate_task_status(status):
    """Validate task status"""
    valid_statuses = ['todo', 'in_progress', 'completed', 'cancelled']
    return status in valid_statuses

def validate_priority(priority):
    """Validate priority level"""
    valid_priorities = ['low', 'medium', 'high', 'urgent']
    return priority in valid_priorities

def validate_required_fields(data, required_fields):
    """Validate that all required fields are present and not empty"""
    missing_fields = []
    for field in required_fields:
        if field not in data or not data[field]:
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, "All required fields present"