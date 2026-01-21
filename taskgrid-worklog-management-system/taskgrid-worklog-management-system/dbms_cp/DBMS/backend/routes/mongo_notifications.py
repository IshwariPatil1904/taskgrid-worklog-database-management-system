from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.mongo_db import notifications_col, oid, to_str_id

mongo_notifications_bp = Blueprint('mongo_notifications', __name__)

@mongo_notifications_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Fetch all reminders/notifications for the logged-in user"""
    try:
        uid = get_jwt_identity()
        cursor = notifications_col.find({"user_id": oid(uid)}).sort("timestamp", -1)
        notifications = [to_str_id(n) for n in cursor]
        return jsonify({"notifications": notifications}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
