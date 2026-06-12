"""群聊 & 共享文件"""
import os, uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from src.models import db, ChatMessage, SharedFile, P2PTransfer, User, Attendance
from datetime import date

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

# 在线心跳（内存字典）
import time as _time_module
_user_heartbeats = {}  # {user_id: timestamp}


# 通用文件服务（聊天图片/文件）
@chat_bp.route('/media/<path:filename>')
def media_file(filename):
    """提供聊天中的图片和文件"""
    from flask import send_from_directory
    chat_dir = os.path.join(_upload_dir(), 'chat')
    return send_from_directory(chat_dir, filename)


def _upload_dir():
    d = current_app.config.get('UPLOAD_DIR')
    os.makedirs(d, exist_ok=True)
    return d


# ═══════════════ 群聊 ═══════════════

@chat_bp.route('/')
@login_required
def index():
    # 最近200条消息
    messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).limit(200).all()
    messages.reverse()

    # 标记所有消息为已读
    if messages:
        try:
            latest = messages[-1]
            from src.models import UserSettings
            stg = UserSettings.query.filter_by(user_id=current_user.id).first()
            if not stg:
                stg = UserSettings(user_id=current_user.id)
                db.session.add(stg)
            stg.last_read_chat_id = latest.id
            db.session.commit()
        except Exception:
            db.session.rollback()

    return render_template('chat/index.html', messages=messages)


@chat_bp.route('/messages')
@login_required
def messages():
    """AJAX 拉取新消息"""
    since = request.args.get('since', type=int, default=0)
    from datetime import timedelta
    msgs = ChatMessage.query.filter(ChatMessage.id > since).order_by(ChatMessage.created_at.asc()).all()
    return jsonify([{
        'id': m.id, 'user': m.user.username, 'user_id': m.user_id,
        'content': m.content, 'msg_type': m.msg_type,
        'file_name': m.file_name, 'file_path': m.file_path,
        'time': int((m.created_at + timedelta(hours=8)).timestamp() * 1000),
        'time_str': (m.created_at + timedelta(hours=8)).strftime('%H:%M'),
        'avatar': m.user.avatar or '',
    } for m in msgs])


@chat_bp.route('/send', methods=['POST'])
@login_required
def send():
    content = request.form.get('content', '').strip()
    file = request.files.get('file')

    msg = ChatMessage(user_id=current_user.id, msg_type='text', content=content)

    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        chat_dir = os.path.join(_upload_dir(), 'chat')
        os.makedirs(chat_dir, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}{ext}"
        full_path = os.path.join(chat_dir, safe_name)

        CHUNK = 65536
        with open(full_path, 'wb') as dst:
            while True:
                chunk = file.stream.read(CHUNK)
                if not chunk: break
                dst.write(chunk)

        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'):
            msg.msg_type = 'image'
        else:
            msg.msg_type = 'file'
        msg.file_name = file.filename
        msg.file_path = safe_name

    if not msg.content and not msg.file_path:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'ok': False, 'error': 'empty'})
        return redirect(url_for('chat.index'))

    db.session.add(msg)
    db.session.commit()

    # AJAX request: return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'ok': True,
            'id': msg.id,
            'content': msg.content,
            'msg_type': msg.msg_type,
            'file_name': msg.file_name,
            'file_path': msg.file_path,
            'time_str': (msg.created_at + timedelta(hours=8)).strftime('%H:%M'),
        })
    return redirect(url_for('chat.index'))


@chat_bp.route('/unread')
@login_required
def unread_count():
    """返回当前用户的未读消息数 JSON"""
    from src.models import UserSettings
    stg = UserSettings.query.filter_by(user_id=current_user.id).first()
    last_id = stg.last_read_chat_id if stg else 0
    count = ChatMessage.query.filter(ChatMessage.id > last_id, ChatMessage.user_id != current_user.id).count()
    return jsonify({'count': count})


@chat_bp.route('/mark-read', methods=['POST'])
@login_required
def mark_read():
    """标记当前已读位置"""
    from src.models import UserSettings
    latest = ChatMessage.query.order_by(ChatMessage.id.desc()).first()
    if latest:
        stg = UserSettings.query.filter_by(user_id=current_user.id).first()
        if not stg:
            stg = UserSettings(user_id=current_user.id)
            db.session.add(stg)
        if latest.id > (stg.last_read_chat_id or 0):
            stg.last_read_chat_id = latest.id
            db.session.commit()
    return jsonify({'ok': True})


# ═══════════════ 共享文件 ═══════════════

@chat_bp.route('/files')
@login_required
def files_list():
    _cleanup_old_p2p()

    files = SharedFile.query.order_by(SharedFile.created_at.desc()).all()
    online = _get_online_users()
    # 我的 P2P 文件（待接收 + 已下载）
    pending = P2PTransfer.query.filter_by(receiver_id=current_user.id).filter(
        P2PTransfer.status.in_(['pending', 'downloaded'])
    ).order_by(P2PTransfer.created_at.desc()).all()
    return render_template('chat/files.html', files=files, online=online, pending=pending)


def _get_online_users():
    """获取心跳在90秒内的用户"""
    now = _time_module.time()
    online_ids = [uid for uid, ts in _user_heartbeats.items() if now - ts < 90]
    if not online_ids:
        return []
    users = User.query.filter(User.id.in_(online_ids)).all()
    return users


def _cleanup_old_p2p():
    """删除超过1天的P2P传输记录和文件"""
    cutoff = datetime.utcnow() - timedelta(days=1)
    old = P2PTransfer.query.filter(P2PTransfer.created_at < cutoff).all()
    for t in old:
        p2p_dir = os.path.join(_upload_dir(), 'p2p')
        fp = os.path.join(p2p_dir, t.filename)
        if os.path.exists(fp):
            try: os.remove(fp)
            except: pass
        db.session.delete(t)
    if old:
        db.session.commit()


@chat_bp.route('/p2p/pending')
@login_required
def p2p_pending():
    """返回待接收的P2P文件列表 JSON"""
    _cleanup_old_p2p()  # Clean up expired transfers on every poll

    if request.args.get('init') == '1':
        # Return just the latest ID for baseline
        latest = P2PTransfer.query.filter_by(receiver_id=current_user.id).order_by(P2PTransfer.id.desc()).first()
        return jsonify({'max_id': latest.id if latest else 0})

    since = request.args.get('since', type=int, default=0)
    transfers = P2PTransfer.query.filter_by(receiver_id=current_user.id).filter(
        P2PTransfer.status.in_(['pending', 'downloaded']),
        P2PTransfer.id > since
    ).order_by(P2PTransfer.created_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'sender': t.sender.username,
        'original_name': t.original_name,
        'size': t.size,
        'status': t.status,
    } for t in transfers])


# ═══════════════ 心跳 ═══════════════

@chat_bp.route('/heartbeat', methods=['POST'])
@login_required
def heartbeat():
    """浏览器每30秒发一次，标记在线"""
    _user_heartbeats[current_user.id] = _time_module.time()
    return jsonify({'ok': True})


@chat_bp.route('/files/upload', methods=['POST'])
@login_required
def files_upload():
    file = request.files.get('file')
    if not file or not file.filename:
        flash('请选择文件。', 'warning')
        return redirect(url_for('chat.files_list'))

    ext = os.path.splitext(file.filename)[1]
    fdir = os.path.join(_upload_dir(), 'shared')
    os.makedirs(fdir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(fdir, safe_name)

    CHUNK = 65536
    total = 0
    with open(full_path, 'wb') as dst:
        while True:
            chunk = file.stream.read(CHUNK)
            if not chunk: break
            dst.write(chunk)
            total += len(chunk)

    desc = request.form.get('description', '').strip()

    sf = SharedFile(user_id=current_user.id, filename=safe_name,
                    original_name=file.filename, size=total,
                    description=desc, is_fixed=True)
    db.session.add(sf)
    db.session.commit()
    flash(f'{file.filename} ({total / 1048576:.1f} MB) 上传成功！', 'success')
    return redirect(url_for('chat.files_list'))


@chat_bp.route('/files/<int:id>/download')
@login_required
def files_download(id):
    sf = SharedFile.query.get_or_404(id)
    fdir = os.path.join(_upload_dir(), 'shared')
    path = os.path.join(fdir, sf.filename)
    if not os.path.exists(path):
        flash('文件不存在。', 'danger')
        return redirect(url_for('chat.files_list'))
    return send_file(path, as_attachment=True, download_name=sf.original_name)


@chat_bp.route('/files/<int:id>/delete', methods=['POST'])
@login_required
def files_delete(id):
    sf = SharedFile.query.get_or_404(id)
    fdir = os.path.join(_upload_dir(), 'shared')
    path = os.path.join(fdir, sf.filename)
    if os.path.exists(path):
        try: os.remove(path)
        except: pass
    db.session.delete(sf)
    db.session.commit()
    flash('文件已删除。', 'info')
    return redirect(url_for('chat.files_list'))


# ═══════════════ 分片上传（大文件） ═══════════════

@chat_bp.route('/chunk-upload', methods=['POST'])
@login_required
def chunk_upload():
    """分片上传端点，文件切成小块逐片发送后在服务端拼合"""
    upload_id = request.form.get('upload_id', '').strip()
    chunk_index = request.form.get('chunk_index', 0, type=int)
    total_chunks = request.form.get('total_chunks', 1, type=int)
    original_name = request.form.get('original_name', 'file')
    target_type = request.form.get('target_type', 'p2p')  # 'p2p' or 'shared'
    receiver_id = request.form.get('receiver_id', 0, type=int)
    description = request.form.get('description', '').strip()
    file_chunk = request.files.get('file')

    if not upload_id or not file_chunk:
        return jsonify({'ok': False, 'error': 'missing upload_id or file chunk'}), 400

    # Security: only allow UUID-like upload_ids
    upload_id = ''.join(c for c in upload_id if c.isalnum() or c == '-')
    if len(upload_id) < 8:
        return jsonify({'ok': False, 'error': 'invalid upload_id'}), 400

    tmp_dir = os.path.join(_upload_dir(), 'tmp', upload_id)
    os.makedirs(tmp_dir, exist_ok=True)

    # Save this chunk
    chunk_path = os.path.join(tmp_dir, f'chunk_{chunk_index:06d}')
    file_chunk.save(chunk_path)

    # Check if all chunks received
    received = len([f for f in os.listdir(tmp_dir) if f.startswith('chunk_')])

    if received < total_chunks:
        return jsonify({'ok': True, 'status': 'chunk_ok', 'received': received, 'total': total_chunks})

    # All chunks received — reassemble
    ext = os.path.splitext(original_name)[1]
    if target_type == 'shared':
        dest_dir = os.path.join(_upload_dir(), 'shared')
        os.makedirs(dest_dir, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = os.path.join(dest_dir, safe_name)
    else:
        dest_dir = os.path.join(_upload_dir(), 'p2p')
        os.makedirs(dest_dir, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = os.path.join(dest_dir, safe_name)

    total_size = 0
    with open(dest_path, 'wb') as dst:
        for i in range(total_chunks):
            cp = os.path.join(tmp_dir, f'chunk_{i:06d}')
            with open(cp, 'rb') as src:
                while True:
                    data = src.read(65536)
                    if not data: break
                    dst.write(data)
                    total_size += len(data)
            os.remove(cp)

    # Cleanup tmp dir
    try: os.rmdir(tmp_dir)
    except: pass

    # Create DB record
    if target_type == 'shared':
        sf = SharedFile(user_id=current_user.id, filename=safe_name,
                        original_name=original_name, size=total_size,
                        description=description, is_fixed=True)
        db.session.add(sf)
        db.session.commit()
        return jsonify({'ok': True, 'status': 'complete', 'size': total_size, 'type': 'shared'})

    else:  # p2p
        receiver = db.session.get(User, receiver_id)
        if not receiver:
            os.remove(dest_path)
            return jsonify({'ok': False, 'error': 'receiver not found'}), 400

        # Keep at most 5 pending transfers for this receiver
        existing = P2PTransfer.query.filter_by(receiver_id=receiver_id).filter(
            P2PTransfer.status.in_(['pending', 'downloaded'])
        ).order_by(P2PTransfer.created_at.asc()).all()
        # Delete oldest if >= 5
        while len(existing) >= 5:
            oldest = existing.pop(0)
            old_path = os.path.join(dest_dir, oldest.filename)
            if os.path.exists(old_path):
                try: os.remove(old_path)
                except: pass
            db.session.delete(oldest)

        transfer = P2PTransfer(
            sender_id=current_user.id, receiver_id=receiver_id,
            original_name=original_name, filename=safe_name, size=total_size
        )
        db.session.add(transfer)
        db.session.commit()
        return jsonify({'ok': True, 'status': 'complete', 'size': total_size, 'type': 'p2p',
                        'receiver': receiver.username})


@chat_bp.route('/cancel-upload', methods=['POST'])
@login_required
def cancel_upload():
    """清理取消上传的临时分片"""
    upload_id = request.args.get('upload_id', '').strip()
    upload_id = ''.join(c for c in upload_id if c.isalnum() or c == '-')
    if upload_id:
        import shutil
        tmp_dir = os.path.join(_upload_dir(), 'tmp', upload_id)
        if os.path.exists(tmp_dir):
            try: shutil.rmtree(tmp_dir)
            except: pass
    return jsonify({'ok': True})


# ═══════════════ P2P 传输 ═══════════════

@chat_bp.route('/p2p/send', methods=['POST'])
@login_required
def p2p_send():
    """保留：小文件直接用此端点（不分片）"""
    file = request.files.get('p2p_file')
    receiver_id = request.form.get('receiver_id', type=int)
    if not file or not file.filename or not receiver_id:
        flash('请选择文件和接收人。', 'warning')
        return redirect(url_for('chat.files_list'))

    receiver = db.session.get(User, receiver_id)
    if not receiver:
        flash('接收用户不存在。', 'danger')
        return redirect(url_for('chat.files_list'))

    ext = os.path.splitext(file.filename)[1]
    p2p_dir = os.path.join(_upload_dir(), 'p2p')
    os.makedirs(p2p_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(p2p_dir, safe_name)

    CHUNK = 65536
    total = 0
    with open(full_path, 'wb') as dst:
        while True:
            chunk = file.stream.read(CHUNK)
            if not chunk: break
            dst.write(chunk)
            total += len(chunk)

    # Keep at most 5 pending transfers for this receiver
    existing = P2PTransfer.query.filter_by(receiver_id=receiver_id).filter(
        P2PTransfer.status.in_(['pending', 'downloaded'])
    ).order_by(P2PTransfer.created_at.asc()).all()
    while len(existing) >= 5:
        oldest = existing.pop(0)
        old_path = os.path.join(p2p_dir, oldest.filename)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except: pass
        db.session.delete(oldest)

    transfer = P2PTransfer(
        sender_id=current_user.id, receiver_id=receiver_id,
        original_name=file.filename, filename=safe_name, size=total
    )
    db.session.add(transfer)
    db.session.commit()
    flash(f'已发送 {file.filename} ({total / 1048576:.1f} MB) 给 {receiver.username}', 'success')
    return redirect(url_for('chat.files_list'))


@chat_bp.route('/p2p/<int:id>/download')
@login_required
def p2p_download(id):
    transfer = P2PTransfer.query.get_or_404(id)
    if transfer.receiver_id != current_user.id and transfer.sender_id != current_user.id:
        flash('无权下载。', 'danger')
        return redirect(url_for('chat.files_list'))

    p2p_dir = os.path.join(_upload_dir(), 'p2p')
    path = os.path.join(p2p_dir, transfer.filename)
    if not os.path.exists(path):
        flash('文件已过期。', 'danger')
        return redirect(url_for('chat.files_list'))

    if transfer.receiver_id == current_user.id:
        transfer.status = 'downloaded'
        db.session.commit()

    return send_file(path, as_attachment=True, download_name=transfer.original_name)


@chat_bp.route('/p2p/<int:id>/delete', methods=['POST'])
@login_required
def p2p_delete(id):
    transfer = P2PTransfer.query.get_or_404(id)
    if transfer.sender_id != current_user.id:
        flash('只能删除自己发送的文件。', 'danger')
        return redirect(url_for('chat.files_list'))
    p2p_dir = os.path.join(_upload_dir(), 'p2p')
    path = os.path.join(p2p_dir, transfer.filename)
    if os.path.exists(path):
        try: os.remove(path)
        except: pass
    db.session.delete(transfer)
    db.session.commit()
    flash('已移除。', 'info')
    return redirect(url_for('chat.files_list'))
