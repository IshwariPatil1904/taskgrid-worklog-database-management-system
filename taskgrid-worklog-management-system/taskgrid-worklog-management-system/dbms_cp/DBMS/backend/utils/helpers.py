from datetime import datetime, date, timedelta
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from models.user_model import User
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def manager_or_admin_required(f):
    """Decorator to require manager or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from models.user_model import User
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or user.role not in ['admin', 'manager']:
            return jsonify({'error': 'Manager or admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def format_date(date_obj):
    """Format date object to string"""
    if date_obj:
        return date_obj.isoformat()
    return None

def format_datetime(datetime_obj):
    """Format datetime object to string"""
    if datetime_obj:
        return datetime_obj.isoformat()
    return None

def parse_date(date_string):
    """Parse date string to date object"""
    if date_string:
        try:
            return datetime.strptime(date_string, '%Y-%m-%d').date()
        except ValueError:
            return None
    return None

def parse_datetime(datetime_string):
    """Parse datetime string to datetime object"""
    if datetime_string:
        try:
            return datetime.fromisoformat(datetime_string)
        except ValueError:
            return None
    return None

def get_week_start_end(target_date=None):
    """Get start and end dates of the week for a given date"""
    if not target_date:
        target_date = date.today()
    
    # Monday is 0, Sunday is 6
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    return week_start, week_end

def get_month_start_end(target_date=None):
    """Get start and end dates of the month for a given date"""
    if not target_date:
        target_date = date.today()
    
    month_start = target_date.replace(day=1)
    
    # Get last day of month
    if target_date.month == 12:
        next_month = target_date.replace(year=target_date.year + 1, month=1, day=1)
    else:
        next_month = target_date.replace(month=target_date.month + 1, day=1)
    
    month_end = next_month - timedelta(days=1)
    
    return month_start, month_end

def calculate_business_days(start_date, end_date):
    """Calculate number of business days between two dates"""
    if not start_date or not end_date:
        return 0
    
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Monday is 0, Sunday is 6
        if current_date.weekday() < 5:  # Monday to Friday
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days

def format_duration(hours):
    """Format hours into human-readable duration"""
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes} minutes"
    elif hours < 24:
        return f"{hours:.1f} hours"
    else:
        days = int(hours // 24)
        remaining_hours = hours % 24
        if remaining_hours > 0:
            return f"{days} days, {remaining_hours:.1f} hours"
        else:
            return f"{days} days"

def paginate_query(query, page=1, per_page=20):
    """Paginate a SQLAlchemy query"""
    try:
        page = int(page) if page else 1
        per_page = int(per_page) if per_page else 20
        
        # Ensure reasonable limits
        per_page = min(per_page, 100)  # Max 100 items per page
        page = max(page, 1)  # Min page 1
        
        paginated = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return {
            'items': paginated.items,
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page,
            'per_page': per_page,
            'has_next': paginated.has_next,
            'has_prev': paginated.has_prev
        }
    except Exception:
        return {
            'items': [],
            'total': 0,
            'pages': 0,
            'current_page': 1,
            'per_page': per_page,
            'has_next': False,
            'has_prev': False
        }

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert value to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default