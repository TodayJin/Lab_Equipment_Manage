from datetime import datetime
from flask import Blueprint, render_template, request, Response, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from src.models import db, StockRecord, Equipment, User, Category
from src.helpers import admin_required, log_operation, request_is_api

records_bp = Blueprint('records', __name__, url_prefix='/records')


@records_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_record(id):
    """管理员删除单条出入库记录，回退库存"""
    record = StockRecord.query.get_or_404(id)
    equipment = Equipment.query.get(record.equipment_id)

    try:
        # Reverse the stock change
        if equipment:
            if record.type == 'in':
                equipment.stock_quantity = max(0, equipment.stock_quantity - record.quantity)
            else:
                equipment.stock_quantity += record.quantity

        # Log before delete
        log_operation('admin_delete_record', 'stock_record', record.id, equipment.name if equipment else 'unknown',
                      {'type': record.type, 'quantity': record.quantity, 'user': record.user.username,
                       'before_stock': record.before_stock, 'after_stock': record.after_stock})
        db.session.delete(record)
        db.session.commit()
        msg = f'已删除 {record.user.username} 的{record.type_display}记录：{equipment.name if equipment else "?"} ×{record.quantity}，库存已回退。'
        if request_is_api(): return jsonify({'ok': True, 'message': msg})
        flash(msg, 'info')
    except Exception:
        db.session.rollback()
        flash('删除失败，请重试。', 'danger')

    return redirect(request.referrer or url_for('records.index'))


def _build_query():
    user_id = request.args.get('user_id', 0, type=int)
    record_type = request.args.get('type', '')
    equipment_id = request.args.get('equipment_id', 0, type=int)
    category_id = request.args.get('category_id', 0, type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = StockRecord.query.options(
        joinedload(StockRecord.equipment),
        joinedload(StockRecord.user)
    )

    if user_id:
        query = query.filter(StockRecord.user_id == user_id)
    if record_type in ('in', 'out'):
        query = query.filter(StockRecord.type == record_type)
    if equipment_id:
        query = query.filter(StockRecord.equipment_id == equipment_id)
    if category_id:
        query = query.join(StockRecord.equipment).filter(Equipment.category_id == category_id)
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(StockRecord.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(StockRecord.created_at <= dt_to)
        except ValueError:
            pass

    return query, {
        'user_id': user_id, 'type': record_type, 'equipment_id': equipment_id,
        'category_id': category_id, 'date_from': date_from, 'date_to': date_to
    }


@records_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    query, filters = _build_query()
    query = query.order_by(StockRecord.created_at.desc())
    records = query.paginate(page=page, per_page=20, error_out=False)

    users = User.query.order_by(User.username).all()
    equipments = Equipment.query.order_by(Equipment.name).all()
    categories_ = Category.query.order_by(Category.name).all()

    return render_template(
        'records/index.html',
        records=records, users=users, equipments=equipments,
        categories=categories_, filters=filters
    )


@records_bp.route('/export')
@login_required
def export():
    """导出查询结果为 CSV"""
    query, filters = _build_query()
    query = query.order_by(StockRecord.created_at.desc())
    records = query.limit(10000).all()

    import csv, io

    output = io.StringIO()
    output.write('\uFEFF')  # BOM for Excel UTF-8
    writer = csv.writer(output)

    writer.writerow(['时间', '类型', '器材名称', '型号', '数量', '操作前库存', '操作后库存',
                     '操作人', '备注', '是否撤销'])
    for r in records:
        writer.writerow([
            r.created_at.strftime('%Y-%m-%d %H:%M'),
            r.type_display,
            r.equipment.name,
            r.equipment.model or '',
            r.quantity,
            r.before_stock,
            r.after_stock,
            r.user.username,
            r.remark or '',
            '是' if r.undone else '',
        ])

    filename = f'lab_records_{datetime.utcnow().strftime("%Y%m%d_%H%M")}.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
