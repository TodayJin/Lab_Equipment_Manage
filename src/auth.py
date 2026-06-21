from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from src.models import db, User, UserSettings
from src.forms import LoginForm, RegisterForm, ChangePasswordForm
from src.helpers import admin_required, log_operation

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('登录成功！', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home.index'))
        flash('用户名或密码错误。', 'danger')
    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('用户名已存在。', 'danger')
        else:
            user = User(username=form.username.data)
            user.set_password(form.password.data)

            # 第一个注册的用户自动成为管理员
            if User.query.count() == 0:
                user.role = 'admin'

            db.session.add(user)
            db.session.flush()
            # 为新用户创建默认设置
            db.session.add(UserSettings(user_id=user.id))
            db.session.commit()
            flash('注册成功！请登录。', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('已退出登录。', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('当前密码错误。', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            log_operation('change_password', 'user', current_user.id, current_user.username)
            db.session.commit()
            flash('密码修改成功！', 'success')
            return redirect(url_for('home.index'))
    return render_template('auth/change_password.html', form=form)
