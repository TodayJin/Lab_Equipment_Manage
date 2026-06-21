""" 库存操作 — 入库/出库 + 撤销 """
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from src.models import db, Equipment, StockRecord, Category
from src.forms import StockInForm, StockOutForm
from src.helpers import log_operation, request_is_api

stock_bp = Blueprint('stock', __name__, url_prefix='/stock')


@stock_bp.route('/api/equipment/list')
@login_required
def api_equipment_list():
    """返回器材列表 JSON，供前端可搜索下拉组件使用"""
    equipments = Equipment.query.order_by(Equipment.name).all()
    categories = Category.query.order_by(Category.name).all()
    return jsonify({
        'equipments': [{
            'id': e.id,
            'name': e.name,
            'model': e.model or '',
            'packaging': e.packaging or '',
            'category_id': e.category_id,
            'category_name': e.category.name if e.category else '',
            'stock_quantity': e.stock_quantity,
            'alert_threshold': e.alert_threshold,
            'unit': e.unit or '个',
        } for e in equipments],
        'categories': [c.name for c in categories]
    })


def _get_equipment_choices():
    equipments = Equipment.query.order_by(Equipment.name).all()
    return [(e.id, f'{e.name} ({e.model or "无型号"}) — 库存: {e.stock_quantity}{e.unit}') for e in equipments]


@stock_bp.route('/in', methods=['GET', 'POST'])
@login_required
def stock_in():
    form = StockInForm()
    form.equipment_id.choices = _get_equipment_choices()

    if form.validate_on_submit():
        equipment = Equipment.query.get(form.equipment_id.data)
        if not equipment:
            flash('器材不存在。', 'danger')
            return redirect(url_for('stock.stock_in'))

        quantity = form.quantity.data
        before = equipment.stock_quantity
        after = before + quantity

        try:
            equipment.stock_quantity = after
            record = StockRecord(
                equipment_id=equipment.id,
                user_id=current_user.id,
                type='in',
                quantity=quantity,
                before_stock=before,
                after_stock=after,
                remark=form.remark.data
            )
            db.session.add(record)
            db.session.flush()
            log_operation('stock_in', 'stock_record', record.id, equipment.name,
                          {'quantity': quantity, 'before': before, 'after': after})
            db.session.commit()
            flash(f'入库成功！{equipment.name} {quantity}{equipment.unit}，库存 {before} → {after}。', 'success')
            return redirect(url_for('stock.stock_in'))
        except Exception:
            db.session.rollback()
            flash('入库操作失败，请重试。', 'danger')

    # Get recent stock actions for undo display
    recent = StockRecord.query.filter_by(user_id=current_user.id, undone=False) \
        .order_by(StockRecord.created_at.desc()).limit(10).all()

    return render_template('stock/in.html', form=form, recent_records=recent)


@stock_bp.route('/out', methods=['GET', 'POST'])
@login_required
def stock_out():
    form = StockOutForm()
    form.equipment_id.choices = _get_equipment_choices()

    if form.validate_on_submit():
        equipment = Equipment.query.get(form.equipment_id.data)
        if not equipment:
            flash('器材不存在。', 'danger')
            return redirect(url_for('stock.stock_out'))

        quantity = form.quantity.data

        if equipment.stock_quantity < quantity:
            flash(f'库存不足！当前库存: {equipment.stock_quantity}{equipment.unit}，需要: {quantity}{equipment.unit}。', 'danger')
            return render_template('stock/out.html', form=form, recent_records=[])

        before = equipment.stock_quantity
        after = before - quantity

        try:
            equipment.stock_quantity = after
            record = StockRecord(
                equipment_id=equipment.id,
                user_id=current_user.id,
                type='out',
                quantity=quantity,
                before_stock=before,
                after_stock=after,
                remark=form.remark.data
            )
            db.session.add(record)
            db.session.flush()
            log_operation('stock_out', 'stock_record', record.id, equipment.name,
                          {'quantity': quantity, 'before': before, 'after': after})
            db.session.commit()
            flash(f'出库成功！{equipment.name} {quantity}{equipment.unit}，库存 {before} → {after}。', 'success')
            return redirect(url_for('stock.stock_out'))
        except Exception:
            db.session.rollback()
            flash('出库操作失败，请重试。', 'danger')

    recent = StockRecord.query.filter_by(user_id=current_user.id, undone=False) \
        .order_by(StockRecord.created_at.desc()).limit(10).all()

    return render_template('stock/out.html', form=form, recent_records=recent)


@stock_bp.route('/undo/<int:record_id>', methods=['POST'])
@login_required
def undo(record_id):
    """撤销入库/出库操作"""
    record = StockRecord.query.get_or_404(record_id)

    # 只能撤销自己的，且只能撤销 5 分钟内的
    if record.user_id != current_user.id:
        msg = '只能撤销自己的操作。'
        if request_is_api(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    if record.undone:
        msg = '该操作已被撤销。'
        if request_is_api(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'warning')
        return redirect(request.referrer or url_for('dashboard.index'))

    from datetime import datetime, timedelta
    age = datetime.utcnow() - record.created_at
    if age > timedelta(minutes=5):
        msg = '该操作已超过 5 分钟，无法撤销。请通过反向操作来修正。'
        if request_is_api(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    equipment = Equipment.query.get(record.equipment_id)
    if not equipment:
        msg = '器材不存在。'
        if request_is_api(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    try:
        if record.type == 'in':
            if equipment.stock_quantity < record.quantity:
                msg = f'无法撤销：当前库存({equipment.stock_quantity})不足以回退。'
                if request_is_api(): return jsonify({'ok': False, 'message': msg})
                flash(msg, 'danger')
                return redirect(request.referrer or url_for('dashboard.index'))
            equipment.stock_quantity -= record.quantity
        else:
            equipment.stock_quantity += record.quantity

        record.undone = True
        log_operation('undo_stock', 'stock_record', record.id, equipment.name,
                      {'original_type': record.type, 'quantity': record.quantity})
        db.session.commit()
        msg = f'已撤销：{equipment.name} {record.type_display} {record.quantity}{equipment.unit}。'
        if request_is_api(): return jsonify({'ok': True, 'message': msg})
        flash(msg, 'success')
    except Exception:
        db.session.rollback()
        msg = '撤销失败，请重试。'
        if request_is_api(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('dashboard.index'))
