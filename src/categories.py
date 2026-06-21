from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from src.models import db, Category
from src.forms import CategoryForm
from src.helpers import log_operation, admin_required, request_is_api

categories_bp = Blueprint('categories', __name__, url_prefix='/categories')


@categories_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category(name=form.name.data, description=form.description.data)
        db.session.add(category)
        db.session.flush()
        log_operation('create_category', 'category', category.id, category.name)
        db.session.commit()
        msg = '分类添加成功！'
        if request_is_api(): return jsonify({'ok': True, 'message': msg, 'id': category.id, 'name': category.name})
        flash(msg, 'success')
        return redirect(url_for('categories.index'))

    categories = Category.query.order_by(Category.name).all()
    return render_template('categories/index.html', categories=categories, form=form)


@categories_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    category = Category.query.get_or_404(id)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        old_name = category.name
        category.name = form.name.data
        category.description = form.description.data
        log_operation('edit_category', 'category', category.id, category.name,
                      {'old_name': old_name})
        db.session.commit()
        flash('分类更新成功！', 'success')
        return redirect(url_for('categories.index'))
    return render_template('categories/form.html', form=form, category=category)


@categories_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    category = Category.query.get_or_404(id)
    if category.equipments.count() > 0:
        msg = '该分类下还有器材，无法删除。'
        if request_is_api(): return jsonify({'ok': False, 'message': msg})
        flash(msg, 'danger')
    else:
        name = category.name
        db.session.delete(category)
        log_operation('delete_category', 'category', None, name)
        db.session.commit()
        msg = '分类已删除。'
        if request_is_api(): return jsonify({'ok': True, 'message': msg})
        flash(msg, 'info')
    return redirect(url_for('categories.index'))
