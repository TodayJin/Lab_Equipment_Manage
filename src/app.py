import os, sys
from datetime import datetime
from flask import Flask
from flask_login import LoginManager
from src.config import Config
from src.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录后再访问。'


def create_app():
    # exe 打包时用 sys._MEIPASS 找模板/静态文件
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        instance_dir = os.path.join(os.path.dirname(sys.executable), "instance")
    else:
        base_path = os.path.join(os.path.dirname(__file__), "..")
        instance_dir = os.path.join(base_path, "instance")

    app = Flask(
        __name__,
        template_folder=os.path.join(base_path, "templates"),
        static_folder=os.path.join(base_path, "static"),
        instance_path=instance_dir,
    )
    app.config.from_object(Config)

    # Ensure instance directory exists
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    # 全局缓存头：静态资源缓存 1 年，HTML 不缓存
    @app.after_request
    def add_cache_headers(response):
        ct = response.content_type or ''
        if ct.startswith('text/html'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        elif ct.startswith(('text/css', 'application/javascript')):
            response.headers['Cache-Control'] = 'no-cache, must-revalidate'
        elif ct.startswith('image/'):
            response.headers['Cache-Control'] = 'public, max-age=86400'
        return response

    # 全局错误处理
    import sqlalchemy as sa
    @app.errorhandler(sa.exc.OperationalError)
    def handle_db_error(e):
        db.session.rollback()
        from flask import flash, redirect, url_for, request
        flash('数据库操作失败，请重试。', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    @app.errorhandler(413)
    def handle_too_large(e):
        from flask import flash, redirect, url_for, request
        flash('文件太大（最大 100MB）。', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    # 上下文处理器：注入签到状态到所有模板
    from flask_login import current_user
    from datetime import date as _date

    @app.context_processor
    def inject_checkin():
        try:
            from flask_login import current_user as _cu
            if _cu.is_authenticated:
                from src.models import Attendance
                rec = Attendance.query.filter_by(user_id=_cu.id, date=_date.today()).first()
                if rec and rec.is_checked_in:
                    logs = rec.logs.all()
                    if logs:
                        rec.last_signin = logs[-1].sign_in_time
                    return {'checkin_status': rec}
        except Exception:
            pass
        return {'checkin_status': None}

    # Jinja2 filter: UTC -> local time (+8h)
    @app.template_filter('localtime')
    def localtime_filter(dt):
        if dt is None:
            return ''
        from datetime import timedelta
        return (dt + timedelta(hours=8)).strftime('%H:%M')

    @app.template_filter('localdate')
    def localdate_filter(dt):
        if dt is None:
            return ''
        from datetime import timedelta
        return (dt + timedelta(hours=8)).strftime('%m-%d %H:%M')

    @app.context_processor
    def inject_avatar():
        from flask_login import current_user as _cu
        if _cu.is_authenticated and _cu.avatar:
            return {'avatar_url': '/account/avatar-img/' + _cu.avatar}
        return {'avatar_url': ''}

    @app.context_processor
    def inject_unread():
        try:
            from flask_login import current_user as _cu
            if _cu.is_authenticated:
                from src.models import UserSettings, ChatMessage
                stg = UserSettings.query.filter_by(user_id=_cu.id).first()
                last_id = stg.last_read_chat_id if stg else 0
                count = ChatMessage.query.filter(ChatMessage.id > last_id, ChatMessage.user_id != _cu.id).count()
                return {'unread_count': count}
        except Exception:
            pass
        return {'unread_count': 0}

    from src.auth import auth_bp
    from src.equipment import equipment_bp
    from src.stock import stock_bp
    from src.records import records_bp
    from src.dashboard import dashboard_bp
    from src.categories import categories_bp
    from src.admin_web import admin_web_bp
    from src.analytics import analytics_bp
    from src.settings_routes import settings_bp
    from src.about import about_bp
    from src.lab import lab_bp
    from src.account import account_bp
    from src.chat import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(admin_web_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(about_bp)
    app.register_blueprint(lab_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(chat_bp)

    # 上传目录
    if getattr(sys, "frozen", False):
        upload_dir = os.path.join(os.path.dirname(sys.executable), "static", "uploads")
    else:
        upload_dir = os.path.join(base_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    app.config['UPLOAD_DIR'] = upload_dir

    with app.app_context():
        db.create_all()
        # 数据库迁移
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        cols_att = [c['name'] for c in inspector.get_columns('attendance_logs')]
        if 'renew_deadline' not in cols_att:
            try:
                db.session.execute(db.text("ALTER TABLE attendance_logs ADD COLUMN renew_deadline DATETIME"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        cols_usr = [c['name'] for c in inspector.get_columns('user_settings')]
        if 'last_read_chat_id' not in cols_usr:
            try:
                db.session.execute(db.text("ALTER TABLE user_settings ADD COLUMN last_read_chat_id INTEGER DEFAULT 0"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        # 为旧活跃签到设置续签截止时间为当前时间（强制签退）
        try:
            from src.models import AttendanceLog
            now = datetime.utcnow()
            AttendanceLog.query.filter(
                AttendanceLog.sign_out_time == None,
                AttendanceLog.renew_deadline == None,
            ).update(
                {AttendanceLog.renew_deadline: now},
                synchronize_session='fetch'
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

    # 后台线程：每30秒检查续签过期自动签退
    import threading
    def _renewal_checker(app_ctx):
        with app_ctx:
            while True:
                try:
                    from src.lab import _auto_signout_renewal_expired
                    _auto_signout_renewal_expired()
                except Exception:
                    db.session.rollback()
                import time
                time.sleep(30)

    t = threading.Thread(target=_renewal_checker, args=(app.app_context(),), daemon=True)
    t.start()

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
