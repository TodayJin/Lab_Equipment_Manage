""" 用户设置路由 """
from flask import Blueprint, request, jsonify, redirect, url_for, flash, render_template
from flask_login import login_required, current_user
from src.models import db, UserSettings

settings_bp = Blueprint('settings_routes', __name__, url_prefix='/settings')


def _get_or_create_settings():
    """获取或创建当前用户的设置"""
    from src.models import UserSettings as US
    stg = US.query.filter_by(user_id=current_user.id).first()
    if stg is None:
        stg = US(user_id=current_user.id)
        db.session.add(stg)
        db.session.commit()
    return stg


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    stg = _get_or_create_settings()

    if request.method == 'POST':
        stg.dark_mode = request.form.get('dark_mode') == 'on'
        stg.items_per_page = int(request.form.get('items_per_page', 15))
        db.session.commit()
        flash('设置已保存。', 'success')
        return redirect(url_for('settings_routes.index'))

    return render_template('settings/user.html', dark_mode=stg.dark_mode,
                           items_per_page=stg.items_per_page)


@settings_bp.route('/api', methods=['POST'])
@login_required
def api_save():
    """AJAX 即时保存（深色模式切换）"""
    stg = _get_or_create_settings()
    data = request.get_json(force=True, silent=True) or {}
    if 'dark_mode' in data:
        stg.dark_mode = bool(data['dark_mode'])
        db.session.commit()
    return jsonify({'ok': True, 'dark_mode': stg.dark_mode})
