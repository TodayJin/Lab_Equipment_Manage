""" 器材管理 — CRUD + 排序 + 快捷搜索 """
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from src.models import db, Equipment, Category, OperationLog
from src.forms import EquipmentForm
from src.helpers import log_operation, admin_required, request_is_api

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')

# 允许排序的列
SORT_COLUMNS = {
    'name': Equipment.name,
    'model': Equipment.model,
    'packaging': Equipment.packaging,
    'category': 'category_name',
    'stock': Equipment.stock_quantity,
    'threshold': Equipment.alert_threshold,
    'updated': Equipment.updated_at,
}


@equipment_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category_id', 0, type=int)
    sort_by = request.args.get('sort', 'updated')
    sort_dir = request.args.get('dir', 'desc')

    query = Equipment.query

    if search:
        query = query.filter(
            db.or_(
                Equipment.name.contains(search),
                Equipment.model.contains(search),
                Equipment.packaging.contains(search)
            )
        )
    if category_id:
        query = query.filter(Equipment.category_id == category_id)

    # Join category for sorting by category name
    if sort_by == 'category':
        query = query.join(Category, Equipment.category_id == Category.id)
        col = Category.name
    else:
        col = SORT_COLUMNS.get(sort_by, Equipment.updated_at)

    if sort_dir == 'asc':
        query = query.order_by(col.asc())
    else:
        query = query.order_by(col.desc())

    equipments = query.paginate(page=page, per_page=15, error_out=False)
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        'equipment/index.html',
        equipments=equipments,
        categories=categories,
        search=search,
        current_category=category_id,
        current_sort=sort_by,
        current_dir=sort_dir,
    )


@equipment_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    form = EquipmentForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]

    if form.validate_on_submit():
        equipment = Equipment(
            name=form.name.data,
            model=form.model.data,
            packaging=form.packaging.data,
            category_id=form.category_id.data,
            stock_quantity=0,  # 新增器材库存为0，通过入库增加
            alert_threshold=form.alert_threshold.data or 0,
            unit=form.unit.data or '个',
            remark=form.remark.data
        )
        db.session.add(equipment)
        db.session.flush()
        log_operation('create_equipment', 'equipment', equipment.id, equipment.name)
        db.session.commit()
        flash('器材添加成功！', 'success')
        return redirect(url_for('equipment.index'))
    return render_template('equipment/form.html', form=form, title='新增器材')


@equipment_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    equipment = Equipment.query.get_or_404(id)
    form = EquipmentForm(obj=equipment)
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]

    if form.validate_on_submit():
        old_data = {'name': equipment.name, 'model': equipment.model, 'stock': equipment.stock_quantity}
        equipment.name = form.name.data
        equipment.model = form.model.data
        equipment.packaging = form.packaging.data
        equipment.category_id = form.category_id.data
        # 库存只能通过入库/出库修改，编辑时不改库存
        equipment.alert_threshold = form.alert_threshold.data or 0
        equipment.unit = form.unit.data or '个'
        equipment.remark = form.remark.data
        log_operation('edit_equipment', 'equipment', equipment.id, equipment.name,
                      {'before': old_data, 'after': {'name': equipment.name, 'stock': equipment.stock_quantity}})
        db.session.commit()
        flash('器材更新成功！', 'success')
        return redirect(url_for('equipment.index'))
    return render_template('equipment/form.html', form=form, title='编辑器材', equipment=equipment)


@equipment_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    equipment = Equipment.query.get_or_404(id)
    name = equipment.name

    # Count related records for logging
    stock_count = equipment.stock_records.count()
    op_count = 0

    if stock_count > 0:
        # Cascade-delete all related stock records (list() to avoid mutation during iteration)
        for rec in list(equipment.stock_records):
            # Delete related operation logs
            ops = OperationLog.query.filter_by(target_type='stock_record', target_id=rec.id).all()
            op_count += len(ops)
            for op in ops:
                db.session.delete(op)
            db.session.delete(rec)

    # Delete operation logs directly referencing this equipment
    eq_ops = OperationLog.query.filter_by(target_type='equipment', target_id=equipment.id).all()
    op_count += len(eq_ops)
    for op in eq_ops:
        db.session.delete(op)

    db.session.delete(equipment)
    log_operation('delete_equipment_cascade', 'equipment', None, name,
                  {'stock_records_deleted': stock_count, 'operation_logs_deleted': op_count})
    db.session.commit()
    msg = f'已删除器材「{name}」及关联的 {stock_count} 条出入库记录、{op_count} 条操作日志。'
    if request_is_api(): return jsonify({'ok': True, 'message': msg})
    flash(msg, 'info')
    return redirect(url_for('equipment.index'))
