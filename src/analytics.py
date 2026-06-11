""" 数据可视化页面 """
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, timedelta
from src.models import db, Equipment, StockRecord, Category

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/')
@login_required
def index():
    return render_template('analytics/index.html')


@analytics_bp.route('/api/overview')
@login_required
def api_overview():
    """概览数据"""
    total_equipment = Equipment.query.count()
    total_stock = db.session.query(func.sum(Equipment.stock_quantity)).scalar() or 0
    total_in = db.session.query(func.sum(StockRecord.quantity)).filter(StockRecord.type == 'in', StockRecord.undone == False).scalar() or 0
    total_out = db.session.query(func.sum(StockRecord.quantity)).filter(StockRecord.type == 'out', StockRecord.undone == False).scalar() or 0
    categories = Category.query.count()
    return jsonify({
        'total_equipment': total_equipment,
        'total_stock': total_stock,
        'total_in': total_in,
        'total_out': total_out,
        'categories': categories,
    })


@analytics_bp.route('/api/monthly-trend')
@login_required
def api_monthly_trend():
    """最近12个月出入库趋势"""
    data = {'labels': [], 'in_data': [], 'out_data': []}
    for i in range(11, -1, -1):
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        for _ in range(i):
            # go back i months
            month_start = (month_start.replace(day=1) - timedelta(days=1)).replace(day=1)
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

        label = month_start.strftime('%Y-%m')
        in_qty = db.session.query(func.sum(StockRecord.quantity)).filter(
            StockRecord.type == 'in',
            StockRecord.undone == False,
            StockRecord.created_at >= month_start,
            StockRecord.created_at <= month_end
        ).scalar() or 0
        out_qty = db.session.query(func.sum(StockRecord.quantity)).filter(
            StockRecord.type == 'out',
            StockRecord.undone == False,
            StockRecord.created_at >= month_start,
            StockRecord.created_at <= month_end
        ).scalar() or 0

        data['labels'].append(label)
        data['in_data'].append(in_qty)
        data['out_data'].append(out_qty)
    return jsonify(data)


@analytics_bp.route('/api/category-distribution')
@login_required
def api_category_distribution():
    """器材分类分布"""
    results = db.session.query(
        Category.name, func.count(Equipment.id)
    ).outerjoin(Equipment).group_by(Category.id).order_by(func.count(Equipment.id).desc()).all()
    return jsonify({
        'labels': [r[0] for r in results],
        'data': [r[1] for r in results],
    })


@analytics_bp.route('/api/top-equipment')
@login_required
def api_top_equipment():
    """出入库最频繁的器材 Top 10"""
    results = db.session.query(
        Equipment.name,
        func.count(StockRecord.id).label('cnt')
    ).join(StockRecord).filter(StockRecord.undone == False) \
     .group_by(Equipment.id).order_by(func.count(StockRecord.id).desc()).limit(10).all()
    return jsonify({
        'labels': [r[0] for r in results],
        'data': [r[1] for r in results],
    })


@analytics_bp.route('/api/user-activity')
@login_required
def api_user_activity():
    """用户操作活跃度"""
    from src.models import User
    results = db.session.query(
        User.username,
        func.count(StockRecord.id).label('cnt')
    ).join(StockRecord).filter(StockRecord.undone == False) \
     .group_by(User.id).order_by(func.count(StockRecord.id).desc()).limit(10).all()
    return jsonify({
        'labels': [r[0] for r in results],
        'data': [r[1] for r in results],
    })
