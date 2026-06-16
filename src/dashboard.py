from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import datetime
from src.models import db, Equipment, StockRecord, Notice, DutyDay

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    total_equipment = Equipment.query.count()
    total_stock = db.session.query(func.sum(Equipment.stock_quantity)).scalar() or 0

    this_month_in = db.session.query(func.sum(StockRecord.quantity)).filter(
        StockRecord.type == 'in',
        StockRecord.created_at >= func.date('now', 'start of month')
    ).scalar() or 0

    this_month_out = db.session.query(func.sum(StockRecord.quantity)).filter(
        StockRecord.type == 'out',
        StockRecord.created_at >= func.date('now', 'start of month')
    ).scalar() or 0

    low_stock_items = Equipment.query.filter(
        Equipment.alert_threshold > 0,
        Equipment.stock_quantity <= Equipment.alert_threshold
    ).order_by(Equipment.stock_quantity).all()

    recent_records = StockRecord.query.options(
        joinedload(StockRecord.equipment),
        joinedload(StockRecord.user)
    ).order_by(StockRecord.created_at.desc()).limit(10).all()

    # 公告
    notices = Notice.query.order_by(Notice.is_pinned.desc(), Notice.created_at.desc()).limit(5).all()

    # 今日值日（周一=0, 周日=6）
    today_duty = None
    try:
        dow = datetime.utcnow().weekday()  # 0=MON
        today_duty = DutyDay.query.filter_by(day_of_week=dow).first()
    except Exception:
        pass
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    all_duties = {d.day_of_week: d for d in DutyDay.query.all()}

    return render_template(
        'dashboard/index.html',
        total_equipment=total_equipment,
        total_stock=total_stock,
        this_month_in=this_month_in,
        this_month_out=this_month_out,
        low_stock_items=low_stock_items,
        recent_records=recent_records,
        notices=notices,
        today_duty=today_duty,
        all_duties=all_duties,
        weekdays=weekdays,
    )
