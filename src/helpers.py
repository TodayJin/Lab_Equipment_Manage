""" 权限管理和通用工具 """

from functools import wraps
from flask import abort, jsonify, request
from flask_login import current_user
import json
from datetime import datetime


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            if request_is_api():
                return jsonify({"error": "需要管理员权限"}), 403
            abort(403)
        return f(*args, **kwargs)
    return decorated


def request_is_api():
    """判断是否为 API 请求"""
    return request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def log_operation(action, target_type, target_id=None, target_name=None, detail=None):
    """写入操作日志，延迟导入避免循环"""
    from src.models import db, OperationLog
    log = OperationLog(
        user_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        detail=json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail,
        created_at=datetime.utcnow()
    )
    db.session.add(log)


def log_operation_sync(user_id, action, target_type, target_id=None, target_name=None, detail=None):
    """同步写入操作日志（用于撤销等场景）"""
    from src.models import db, OperationLog
    log = OperationLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        detail=json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail,
        created_at=datetime.utcnow()
    )
    db.session.add(log)
