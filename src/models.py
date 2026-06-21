from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='member')  # 'admin' or 'member'
    avatar = db.Column(db.String(200), default='')       # 头像文件名
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stock_records = db.relationship('StockRecord', backref='user', lazy='dynamic')
    settings = db.relationship('UserSettings', backref='user', uselist=False, lazy=True)
    operation_logs = db.relationship('OperationLog', backref='user', lazy='dynamic')

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def dark_mode_enabled(self):
        """直接查 UserSettings 表的 dark_mode"""
        try:
            stg = UserSettings.query.filter_by(user_id=self.id).first()
            return stg.dark_mode if stg else False
        except Exception:
            return False

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class UserSettings(db.Model):
    """每个用户的个性化设置"""
    __tablename__ = 'user_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    dark_mode = db.Column(db.Boolean, default=False)
    items_per_page = db.Column(db.Integer, default=15)
    last_read_chat_id = db.Column(db.Integer, default=0)
    color_theme = db.Column(db.String(20), default='purple')  # purple / blue / green / orange / rose
    quick_links = db.Column(db.Text, default='[]')  # JSON: [{"name":"...","url":"..."},...]

    def to_dict(self):
        return {
            'dark_mode': self.dark_mode,
            'items_per_page': self.items_per_page,
        }


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    equipments = db.relationship('Equipment', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Equipment(db.Model):
    __tablename__ = 'equipments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    model = db.Column(db.String(200))
    packaging = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    stock_quantity = db.Column(db.Integer, default=0)
    alert_threshold = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(50), default='个')
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock_records = db.relationship('StockRecord', backref='equipment', lazy='dynamic')

    @property
    def is_low_stock(self):
        return self.alert_threshold > 0 and self.stock_quantity <= self.alert_threshold

    def __repr__(self):
        return f'<Equipment {self.name}>'


class StockRecord(db.Model):
    __tablename__ = 'stock_records'

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipments.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(10), nullable=False, index=True)  # 'in' / 'out'
    quantity = db.Column(db.Integer, nullable=False)
    before_stock = db.Column(db.Integer, nullable=False)
    after_stock = db.Column(db.Integer, nullable=False)
    remark = db.Column(db.Text)
    undone = db.Column(db.Boolean, default=False, index=True)  # 是否已撤销
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def type_display(self):
        return '入库' if self.type == 'in' else '出库'

    def __repr__(self):
        return f'<StockRecord {self.type} {self.quantity}>'


class OperationLog(db.Model):
    """增强操作日志：记录所有管理操作"""
    __tablename__ = 'operation_logs'
    __table_args__ = (db.Index('ix_operation_logs_target', 'target_type', 'target_id'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)      # create_equipment, edit_equipment, delete_equipment,
                                                             # create_category, edit_category, delete_category,
                                                             # create_user, delete_user, change_role,
                                                             # change_password, undo_stock
    target_type = db.Column(db.String(50))                  # equipment, category, user, stock_record
    target_id = db.Column(db.Integer)
    target_name = db.Column(db.String(200))                 # 人类可读的目标名
    detail = db.Column(db.Text)                             # 变更详情 JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Notice(db.Model):
    """公告板"""
    __tablename__ = 'notices'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)   # 是否置顶
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='notices')


class DutyDay(db.Model):
    """值日排班：每周几，哪些人值日"""
    __tablename__ = 'duty_days'

    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False, unique=True)  # 0=周一..6=周日
    user_ids = db.Column(db.String(500), default='')  # "1,3,5" 多个用户ID逗号分隔
    remark = db.Column(db.String(200))

    @property
    def users_list(self):
        if not self.user_ids:
            return []
        ids = [int(x) for x in self.user_ids.split(',') if x.strip().isdigit()]
        return User.query.filter(User.id.in_(ids)).all() if ids else []


class Attendance(db.Model):
    """实验室成员每日签到"""
    __tablename__ = 'attendances'
    __table_args__ = (db.Index('ix_attendances_user_date', 'user_id', 'date'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.utcnow().date())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='attendances')
    logs = db.relationship('AttendanceLog', backref='attendance', lazy='dynamic', order_by='AttendanceLog.sign_in_time')

    @property
    def total_duration(self):
        total = 0
        for log in self.logs:
            if log.sign_out_time:
                total += (log.sign_out_time - log.sign_in_time).total_seconds()
        return round(total / 60)

    @property
    def is_checked_in(self):
        for log in self.logs:
            if log.sign_out_time is None:
                return True
        return False


class AttendanceLog(db.Model):
    """签到/签退事件"""
    __tablename__ = 'attendance_logs'

    id = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(db.Integer, db.ForeignKey('attendances.id'), nullable=False, index=True)
    sign_in_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sign_out_time = db.Column(db.DateTime)
    renew_deadline = db.Column(db.DateTime)  # 续签截止时间，超时自动签退

    @property
    def duration_minutes(self):
        if self.sign_out_time:
            return round((self.sign_out_time - self.sign_in_time).total_seconds() / 60)
        return round((datetime.utcnow() - self.sign_in_time).total_seconds() / 60)


class ChatMessage(db.Model):
    """群聊消息"""
    __tablename__ = 'chat_messages'
    __table_args__ = (db.Index('ix_chat_messages_id_user', 'id', 'user_id'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, default='')
    msg_type = db.Column(db.String(10), default='text')  # text / image / file
    file_name = db.Column(db.String(300))
    file_path = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='chat_messages')


class SharedFile(db.Model):
    """共享文件 — 固定到服务器的文件"""
    __tablename__ = 'shared_files'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(300), nullable=False)
    size = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, default='')
    is_fixed = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='shared_files')


class P2PTransfer(db.Model):
    """点对点文件传输"""
    __tablename__ = 'p2p_transfers'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    original_name = db.Column(db.String(300), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    size = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending / downloaded
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_files')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_files')
