"""账户管理 — 头像上传等"""
import os, uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from src.models import db

ALLOWED_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.webp')

account_bp = Blueprint('account', __name__, url_prefix='/account')


@account_bp.route('/')
@login_required
def index():
    return render_template('account/index.html')


@account_bp.route('/avatar-img/<filename>')
def avatar_img(filename):
    """提供头像文件"""
    from flask import send_from_directory, current_app
    return send_from_directory(current_app.config['UPLOAD_DIR'], filename)


@account_bp.route('/avatar', methods=['POST'])
@login_required
def upload_avatar():
    file = request.files.get('avatar')
    if not file or file.filename == '':
        flash('请选择图片。', 'warning')
        return redirect(url_for('account.index'))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        flash('仅支持 PNG/JPG/GIF/WEBP 格式。', 'danger')
        return redirect(url_for('account.index'))

    upload_dir = current_app.config.get('UPLOAD_DIR')
    os.makedirs(upload_dir, exist_ok=True)

    if current_user.avatar:
        old_path = os.path.join(upload_dir, current_user.avatar)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except: pass

    filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    file.save(os.path.join(upload_dir, filename))
    current_user.avatar = filename
    db.session.commit()
    flash('头像已更新！', 'success')
    return redirect(url_for('account.index'))


@account_bp.route('/avatar/clear', methods=['POST'])
@login_required
def clear_avatar():
    if current_user.avatar:
        upload_dir = current_app.config.get('UPLOAD_DIR')
        old_path = os.path.join(upload_dir, current_user.avatar)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except: pass
        current_user.avatar = ''
        db.session.commit()
    flash('头像已移除。', 'info')
    return redirect(url_for('account.index'))
