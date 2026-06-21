""" 首页 — Bing 搜索 + 快捷链接 """
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from src.models import db

home_bp = Blueprint('home', __name__, url_prefix='/')

@home_bp.route('/home')
@login_required
def home_redirect():
    return redirect(url_for('home.index'))


@home_bp.route('/')
@login_required
def index():
    return render_template('home/index.html')


@home_bp.route('/links', methods=['GET'])
@login_required
def get_links():
    """获取当前用户的快捷链接"""
    from src.models import UserSettings
    stg = UserSettings.query.filter_by(user_id=current_user.id).first()
    links = []
    if stg and stg.quick_links:
        import json
        try:
            links = json.loads(stg.quick_links)
        except Exception:
            links = []
    return jsonify({'links': links})


@home_bp.route('/links', methods=['POST'])
@login_required
def save_links():
    """保存快捷链接"""
    from src.models import UserSettings
    stg = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not stg:
        stg = UserSettings(user_id=current_user.id)
        db.session.add(stg)
    data = request.get_json(force=True, silent=True) or {}
    import json
    stg.quick_links = json.dumps(data.get('links', []), ensure_ascii=False)
    db.session.commit()
    return jsonify({'ok': True})
