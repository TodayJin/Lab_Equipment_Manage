""" 网页端管理后台 — 用户管理、权限管理、操作日志 """
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from src.models import db, User, OperationLog, UserSettings
from src.forms import AdminChangePasswordForm
from src.helpers import admin_required, log_operation

admin_web_bp = Blueprint('admin_web', __name__, url_prefix='/admin')


@admin_web_bp.route('/')
@login_required
@admin_required
def index():
    """管理后台首页"""
    users = User.query.order_by(User.created_at.desc()).all()
    total_users = len(users)
    admin_count = sum(1 for u in users if u.is_admin)
    return render_template('admin/index.html', users=users, total_users=total_users, admin_count=admin_count)


@admin_web_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('不能修改自己的权限。', 'danger')
        return redirect(url_for('admin_web.index'))

    new_role = request.form.get('role', 'member')
    if new_role not in ('admin', 'member'):
        flash('无效的权限。', 'danger')
        return redirect(url_for('admin_web.index'))

    old_role = user.role
    user.role = new_role
    log_operation('change_role', 'user', user.id, user.username,
                  {'from': old_role, 'to': new_role})
    db.session.commit()
    flash(f'已将 {user.username} 的权限改为 {new_role}。', 'success')
    return redirect(url_for('admin_web.index'))


@admin_web_bp.route('/users/<int:user_id>/password', methods=['POST'])
@login_required
@admin_required
def change_user_password(user_id):
    user = User.query.get_or_404(user_id)
    new_pw = request.form.get('new_password', '').strip()
    if len(new_pw) < 4:
        flash('密码至少需要 4 位。', 'danger')
        return redirect(url_for('admin_web.index'))

    user.set_password(new_pw)
    log_operation('change_password', 'user', user.id, user.username,
                  {'by_admin': current_user.username})
    db.session.commit()
    flash(f'已重置 {user.username} 的密码。', 'success')
    return redirect(url_for('admin_web.index'))


@admin_web_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('不能删除自己。', 'danger')
        return redirect(url_for('admin_web.index'))

    if user.stock_records.count() > 0:
        flash(f'{user.username} 有操作记录，无法删除。可以先禁用其权限。', 'danger')
        return redirect(url_for('admin_web.index'))

    name = user.username
    # 清理 settings
    if user.settings:
        db.session.delete(user.settings)
    db.session.delete(user)
    log_operation('delete_user', 'user', None, name)
    db.session.commit()
    flash(f'已删除用户 {name}。', 'success')
    return redirect(url_for('admin_web.index'))


@admin_web_bp.route('/logs')
@login_required
@admin_required
def logs():
    """操作日志"""
    page = request.args.get('page', 1, type=int)
    logs = OperationLog.query.order_by(OperationLog.created_at.desc()) \
        .paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/logs.html', logs=logs)


@admin_web_bp.route('/logs/<int:log_id>')
@login_required
@admin_required
def log_detail(log_id):
    log = OperationLog.query.get_or_404(log_id)
    return render_template('admin/log_detail.html', log=log)
