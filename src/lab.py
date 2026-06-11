"""公告 & 值日 & 签到 & 数据备份"""
import os, io, zipfile
from datetime import datetime, date, timedelta
from collections import defaultdict
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from src.models import db, Notice, DutyDay, Attendance, AttendanceLog, User
from src.helpers import admin_required

lab_bp = Blueprint('lab', __name__, url_prefix='/lab')
WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


# ═══════════════ 公告 ═══════════════

@lab_bp.route('/notices')
@login_required
def notices():
    notices = Notice.query.order_by(Notice.is_pinned.desc(), Notice.created_at.desc()).all()
    return render_template('lab/notices.html', notices=notices)

@lab_bp.route('/notices/new', methods=['POST'])
@login_required
@admin_required
def new_notice():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    pinned = request.form.get('is_pinned') == 'on'
    if title and content:
        db.session.add(Notice(title=title, content=content, is_pinned=pinned, user_id=current_user.id))
        db.session.commit()
        flash('公告已发布。', 'success')
    return redirect(url_for('lab.notices'))

@lab_bp.route('/notices/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_notice(id):
    db.session.delete(Notice.query.get_or_404(id))
    db.session.commit()
    flash('公告已删除。', 'info')
    return redirect(url_for('lab.notices'))


# ═══════════════ 值日 ═══════════════

@lab_bp.route('/duty')
@login_required
def duty():
    existing = {d.day_of_week: d for d in DutyDay.query.all()}
    users = User.query.order_by(User.username).all()
    return render_template('lab/duty.html', weekdays=WEEKDAYS, existing=existing, users=users)

@lab_bp.route('/duty/save', methods=['POST'])
@login_required
@admin_required
def save_duty():
    for i in range(7):
        uids = request.form.getlist(f'users_{i}')
        remark = request.form.get(f'remark_{i}', '').strip()
        existing = DutyDay.query.filter_by(day_of_week=i).first()
        ids_str = ','.join(uids) if uids else ''
        if ids_str:
            if existing:
                existing.user_ids = ids_str
                existing.remark = remark
            else:
                db.session.add(DutyDay(day_of_week=i, user_ids=ids_str, remark=remark))
        elif existing:
            db.session.delete(existing)
    db.session.commit()
    flash('值日排班已保存。', 'success')
    return redirect(url_for('lab.duty'))


# ═══════════════ 签到 ═══════════════

MAX_SIGNIN_HOURS = 12  # 单次签到最大时长
AUTO_SIGNOUT_AFK_MINUTES = 60  # 无操作自动签退提醒


def _auto_signout_expired():
    """自动签退超过12小时的活跃签到，返回签退人数"""
    cutoff = datetime.utcnow() - timedelta(hours=MAX_SIGNIN_HOURS)
    expired_logs = AttendanceLog.query.filter(
        AttendanceLog.sign_out_time == None,
        AttendanceLog.sign_in_time < cutoff
    ).all()
    count = 0
    for log in expired_logs:
        log.sign_out_time = log.sign_in_time + timedelta(hours=MAX_SIGNIN_HOURS)
        count += 1
    if count:
        db.session.commit()
    return count


@lab_bp.route('/checkin')
@login_required
def checkin():
    today = date.today()
    _auto_signout_expired()  # Auto-signout any expired sessions
    today_records = Attendance.query.filter_by(date=today).order_by(Attendance.created_at.desc()).all()
    all_users = User.query.order_by(User.username).all()
    return render_template('lab/checkin.html', today=today, today_records=today_records, users=all_users)


@lab_bp.route('/checkin/status')
@login_required
def checkin_status():
    """返回当前用户签到状态（供前端轮询）"""
    today = date.today()
    rec = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    if not rec or not rec.is_checked_in:
        return jsonify({'checked_in': False})

    log = rec.logs.filter(AttendanceLog.sign_out_time == None).order_by(AttendanceLog.sign_in_time.desc()).first()
    if not log:
        return jsonify({'checked_in': False})

    now = datetime.utcnow()
    duration_minutes = round((now - log.sign_in_time).total_seconds() / 60)
    hours_remaining = max(0, MAX_SIGNIN_HOURS * 60 - duration_minutes)
    # 3h/6h/9h 需要续签确认，12h 硬性签退
    renew_at = [3*60, 6*60, 9*60]
    need_renew = None
    for n in renew_at:
        if duration_minutes >= n and duration_minutes < n + 5:  # 5分钟窗口
            need_renew = n // 60
            break

    return jsonify({
        'checked_in': True,
        'sign_in_time': (log.sign_in_time + timedelta(hours=8)).strftime('%H:%M'),
        'duration_minutes': duration_minutes,
        'hours_remaining': hours_remaining,
        'need_renew': need_renew,  # 3/6/9 需要续签确认
    })


@lab_bp.route('/checkin/signin', methods=['POST'])
@login_required
def do_signin():
    today = date.today()
    uid = request.form.get('user_id', type=int)
    if not uid:
        uid = current_user.id
    record = Attendance.query.filter_by(user_id=uid, date=today).first()
    if not record:
        record = Attendance(user_id=uid, date=today)
        db.session.add(record)
        db.session.commit()
    if record.is_checked_in:
        flash(f'请先签退再签到。', 'warning')
    else:
        db.session.add(AttendanceLog(attendance_id=record.id, sign_in_time=datetime.utcnow()))
        db.session.commit()
        user = db.session.get(User, uid)
        flash(f'{user.username} 签到成功！', 'success')
    return redirect(url_for('lab.checkin'))


@lab_bp.route('/checkin/<int:id>/signout', methods=['POST'])
@login_required
def do_signout(id):
    record = Attendance.query.get_or_404(id)
    if not record.is_checked_in:
        flash('未签到，无需签退。', 'warning')
    else:
        log = record.logs.filter(AttendanceLog.sign_out_time == None).order_by(AttendanceLog.sign_in_time.desc()).first()
        if log:
            log.sign_out_time = datetime.utcnow()
            db.session.commit()
            flash(f'{record.user.username} 签退成功（{log.duration_minutes} 分钟）。', 'success')
    return redirect(url_for('lab.checkin'))


@lab_bp.route('/checkin/auto-signout', methods=['POST'])
@login_required
def auto_signout():
    """自动签退（12h到期或AFK超时触发）"""
    today = date.today()
    rec = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    if not rec or not rec.is_checked_in:
        return jsonify({'ok': True, 'message': 'not checked in'})

    log = rec.logs.filter(AttendanceLog.sign_out_time == None).order_by(AttendanceLog.sign_in_time.desc()).first()
    if log:
        log.sign_out_time = datetime.utcnow()
        db.session.commit()
        return jsonify({'ok': True, 'duration': log.duration_minutes})
    return jsonify({'ok': True, 'message': 'no active log'})


@lab_bp.route('/checkin/stats')
@login_required
def checkin_stats():
    json_api = request.args.get('json', '')
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    user_name = request.args.get('name', '').strip()
    view = request.args.get('view', 'overview')

    today_val = date.today()
    if date_from:
        try: dt_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except: dt_from = today_val - timedelta(days=30)
    else:
        dt_from = today_val - timedelta(days=30)
    if date_to:
        try: dt_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except: dt_to = today_val
    else:
        dt_to = today_val

    if json_api == 'chart':
        return _chart_data(dt_from, dt_to, user_name)

    if json_api == 'ranking':
        return _ranking_data(dt_from, dt_to)

    query = AttendanceLog.query.join(Attendance).filter(
        Attendance.date >= dt_from, Attendance.date <= dt_to
    )
    if user_name:
        query = query.join(User).filter(User.username.contains(user_name))

    logs = query.order_by(AttendanceLog.sign_in_time.desc()).limit(300).all()

    person_stats = defaultdict(lambda: {'days': set(), 'total_min': 0, 'count': 0, 'user_id': 0})
    for log in logs:
        key = log.attendance.user.username
        person_stats[key]['days'].add(log.attendance.date)
        person_stats[key]['total_min'] += log.duration_minutes
        person_stats[key]['count'] += 1
        person_stats[key]['user_id'] = log.attendance.user.id

    # Convert sets to counts and compute avg
    for k in person_stats:
        person_stats[k]['days'] = len(person_stats[k]['days'])
        person_stats[k]['avg_min'] = round(person_stats[k]['total_min'] / max(person_stats[k]['days'], 1))

    all_days = set(); total_min_all = 0; total_sessions = 0
    for log in logs:
        all_days.add(log.attendance.date)
        total_min_all += log.duration_minutes
        total_sessions += 1
    avg_daily = round(total_min_all / max(len(all_days), 1))
    avg_per_person = round(total_min_all / max(len(person_stats), 1))

    users_list = User.query.order_by(User.username).all()
    user_map = {u.username: u.id for u in users_list}

    # Pre-compute ranking
    ranking = []
    for name, data in sorted(person_stats.items(), key=lambda x: x[1]['total_min'], reverse=True):
        ranking.append({
            'username': name,
            'user_id': data.get('user_id', user_map.get(name, 0)),
            'total_minutes': data['total_min'],
            'days': data['days'],
            'sessions': data['count'],
            'avg_minutes': data['avg_min'],
        })

    # Pre-compute member daily details
    all_user_ids = set(data.get('user_id', 0) for data in person_stats.values())
    all_user_ids.discard(0)
    member_details = {}
    for uid in all_user_ids:
        ulogs = AttendanceLog.query.join(Attendance).filter(
            Attendance.user_id == uid,
            Attendance.date >= dt_from, Attendance.date <= dt_to
        ).order_by(Attendance.date.desc(), AttendanceLog.sign_in_time.desc()).limit(60).all()
        udays = set(); utotal = 0
        udaily = []
        for l in ulogs:
            udays.add(l.attendance.date)
            utotal += l.duration_minutes
            udaily.append({
                'date': l.attendance.date.isoformat(),
                'sign_in': (l.sign_in_time + timedelta(hours=8)).strftime('%H:%M'),
                'sign_out': (l.sign_out_time + timedelta(hours=8)).strftime('%H:%M') if l.sign_out_time else None,
                'minutes': l.duration_minutes,
                'is_active': l.sign_out_time is None,
            })
        u = db.session.get(User, uid)
        member_details[str(uid)] = {
            'username': u.username if u else '?',
            'days': len(udays),
            'total_minutes': utotal,
            'avg_minutes': round(utotal / max(len(udays), 1)),
            'daily': udaily,
        }

    return render_template('lab/checkin_stats.html',
        logs=logs, person_stats=dict(person_stats),
        date_from=dt_from, date_to=dt_to, user_name=user_name,
        total_days=len(all_days), total_min=total_min_all,
        total_sessions=total_sessions, avg_daily=avg_daily, avg_per_person=avg_per_person,
        view=view, users_list=users_list, user_map=user_map,
        ranking_json=ranking, member_details_json=member_details)


@lab_bp.route('/checkin/user/<int:user_id>/detail')
@login_required
def user_checkin_detail(user_id):
    """返回单个成员的每日签到明细 JSON"""
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    today_val = date.today()
    if date_from:
        try: dt_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except: dt_from = today_val - timedelta(days=30)
    else:
        dt_from = today_val - timedelta(days=30)
    if date_to:
        try: dt_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except: dt_to = today_val
    else:
        dt_to = today_val

    try:
        logs = AttendanceLog.query.join(Attendance).filter(
            Attendance.user_id == user_id,
            Attendance.date >= dt_from, Attendance.date <= dt_to
        ).order_by(Attendance.date.desc(), AttendanceLog.sign_in_time.desc()).limit(60).all()

        user = db.session.get(User, user_id)
        days = set(); total_min = 0
        daily_data = []
        for log in logs:
            days.add(log.attendance.date)
            total_min += log.duration_minutes
            daily_data.append({
                'date': log.attendance.date.isoformat(),
                'sign_in': (log.sign_in_time + timedelta(hours=8)).strftime('%H:%M'),
                'sign_out': (log.sign_out_time + timedelta(hours=8)).strftime('%H:%M') if log.sign_out_time else None,
                'minutes': log.duration_minutes,
                'is_active': log.sign_out_time is None,
            })

        return jsonify({
            'username': user.username if user else '?',
            'avatar': user.avatar if user else '',
            'days': len(days),
            'total_minutes': total_min,
            'avg_minutes': round(total_min / max(len(days), 1)),
            'daily': daily_data,
        })
    except Exception as e:
        return jsonify({'username': '?', 'days': 0, 'total_minutes': 0, 'avg_minutes': 0, 'daily': [], 'error': str(e)}), 500


def _ranking_data(dt_from, dt_to):
    """返回排名 JSON"""
    try:
        logs = AttendanceLog.query.join(Attendance).filter(
            Attendance.date >= dt_from, Attendance.date <= dt_to
        ).all()

        person_totals = defaultdict(lambda: {'total_min': 0, 'days': set(), 'sessions': 0})
        for log in logs:
            name = log.attendance.user.username
            person_totals[name]['total_min'] += log.duration_minutes
            person_totals[name]['days'].add(log.attendance.date)
            person_totals[name]['sessions'] += 1

        all_users = User.query.all()
        name_to_id = {u.username: u.id for u in all_users}

        ranking = []
        for name, data in sorted(person_totals.items(), key=lambda x: x[1]['total_min'], reverse=True):
            ranking.append({
                'username': name,
                'user_id': name_to_id.get(name, 0),
                'total_minutes': data['total_min'],
                'days': len(data['days']),
                'sessions': data['sessions'],
                'avg_minutes': round(data['total_min'] / max(len(data['days']), 1)),
            })

        return jsonify({'ranking': ranking, 'period': {'from': dt_from.isoformat(), 'to': dt_to.isoformat()}})
    except Exception as e:
        return jsonify({'ranking': [], 'error': str(e)}), 500


def _chart_data(dt_from, dt_to, user_name):
    from collections import OrderedDict

    query = AttendanceLog.query.join(Attendance).filter(
        Attendance.date >= dt_from, Attendance.date <= dt_to
    )
    if user_name:
        query = query.join(User).filter(User.username.contains(user_name))

    logs = query.order_by(AttendanceLog.sign_in_time.asc()).all()

    daily_totals = OrderedDict()
    for log in logs:
        d = log.attendance.date.isoformat()
        daily_totals[d] = daily_totals.get(d, 0) + log.duration_minutes

    person_totals = defaultdict(int)
    for log in logs:
        person_totals[log.attendance.user.username] += log.duration_minutes

    from flask import jsonify
    return jsonify({
        'daily': {'labels': list(daily_totals.keys()), 'data': list(daily_totals.values())},
        'person': {'labels': list(person_totals.keys()), 'data': list(person_totals.values())},
    })


# ═══════════════ 备份恢复 ═══════════════

@lab_bp.route('/backup')
@login_required
@admin_required
def backup_page():
    return render_template('lab/backup.html')

@lab_bp.route('/backup/download')
@login_required
@admin_required
def backup_download():
    from src.config import Config
    from src import settings as app_settings
    db_path = Config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = app_settings.get_default_db_path()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(db_path):
            zf.write(db_path, 'lab.db')
        sp = os.path.join(os.path.dirname(db_path) or '.', 'settings.json')
        if os.path.exists(sp):
            zf.write(sp, 'settings.json')

    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'lab_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M")}.zip')

@lab_bp.route('/backup/restore', methods=['POST'])
@login_required
@admin_required
def backup_restore():
    file = request.files.get('backup_file')
    if not file or not file.filename.endswith('.zip'):
        flash('请选择 .zip 备份文件。', 'danger')
        return redirect(url_for('lab.backup_page'))

    from src.config import Config
    from src import settings as app_settings

    raw_uri = Config.SQLALCHEMY_DATABASE_URI
    if raw_uri.startswith('sqlite:///'):
        db_path = raw_uri[10:]
    else:
        db_path = app_settings.get_default_db_path()
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    tmp_path = db_path + '.restore'
    try:
        with zipfile.ZipFile(file, 'r') as zf:
            if 'lab.db' not in zf.namelist():
                flash('备份文件中未找到数据库。', 'danger')
                return redirect(url_for('lab.backup_page'))

            with zf.open('lab.db') as src, open(tmp_path, 'wb') as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk: break
                    dst.write(chunk)

            import sqlite3
            conn = sqlite3.connect(tmp_path)
            cur = conn.execute("PRAGMA integrity_check")
            result = cur.fetchone()[0]
            conn.close()
            if result != 'ok':
                os.unlink(tmp_path)
                flash(f'备份文件数据损坏（{result}），恢复已取消。', 'danger')
                return redirect(url_for('lab.backup_page'))

            if os.path.exists(db_path):
                os.replace(db_path, db_path + '.old')
            os.replace(tmp_path, db_path)
            if os.path.exists(db_path + '.old'):
                try: os.unlink(db_path + '.old')
                except: pass

            if 'settings.json' in zf.namelist():
                zf.extract('settings.json', os.path.dirname(db_path))

        flash('数据库恢复成功！请重启服务器以生效。', 'success')
    except zipfile.BadZipFile:
        flash('备份文件已损坏（不是有效的 ZIP 文件）。', 'danger')
        if os.path.exists(tmp_path): os.unlink(tmp_path)
    except sqlite3.DatabaseError:
        flash('备份文件不是有效的 SQLite 数据库。', 'danger')
        if os.path.exists(tmp_path): os.unlink(tmp_path)
    except OSError as e:
        flash(f'文件操作失败：{e}。请检查磁盘空间。', 'danger')
        if os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except: pass
    except Exception as e:
        flash(f'恢复失败：{e}', 'danger')
        if os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except: pass
