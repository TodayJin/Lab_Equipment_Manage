"""测试签到统计页面"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from src.app import create_app
from src.models import db, User, Attendance, AttendanceLog, UserSettings
from datetime import date, datetime, timedelta

app = create_app()

with app.app_context():
    # 创建测试数据
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(username='admin', role='admin')
        u.set_password('admin')
        db.session.add(u)
        db.session.commit()
        u = User.query.filter_by(username='admin').first()

    stg = UserSettings.query.filter_by(user_id=u.id).first()
    if not stg:
        stg = UserSettings(user_id=u.id)
        db.session.add(stg)
        db.session.commit()

    today = date.today()
    has_data = Attendance.query.filter_by(user_id=u.id).first()
    if not has_data:
        for days_ago in range(10):
            d = today - timedelta(days=days_ago)
            att = Attendance(user_id=u.id, date=d)
            db.session.add(att)
            db.session.flush()
            minutes = 60 + (9 - days_ago) * 30
            sign_in = datetime.now().replace(hour=9) - timedelta(days=days_ago)
            att_log = AttendanceLog(attendance_id=att.id, sign_in_time=sign_in, sign_out_time=sign_in + timedelta(minutes=minutes))
            db.session.add(att_log)
        db.session.commit()
        print("已创建测试签到数据")

with app.test_client() as client:
    # WTF CSRF 豁免
    app.config['WTF_CSRF_ENABLED'] = False

    # 登录
    resp = client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
    print(f"登录状态: {resp.status_code}, URL: {resp.request.path}")

    # 签到统计页面
    resp = client.get('/lab/checkin/stats')
    print(f"统计页面状态: {resp.status_code}")

    html = resp.data.decode('utf-8')

    # 检查关键元素
    checks = [
        ('fmtTime', 'fmtTime 函数存在'),
        ('ranking-card', '排名卡片 CSS 存在'),
        ('top-1', '第一名样式存在'),
        ('ranking-medal', '奖牌样式存在'),
        ('linear-gradient', '渐变背景存在'),
        ('font-weight:700', '粗体字体存在'),
        ('box-shadow', '阴影存在'),
        ('border-radius:12px', '圆角存在'),
        ('display:flex', 'Flex 布局存在'),
        ('modal fade', '模态框 fade (应该不存在)'),
    ]

    for keyword, desc in checks:
        found = keyword in html
        status = '✓' if found else ('⚠' if 'fade' in keyword else '✗')
        print(f"  {status} {desc}: {'存在' if found else '缺失'}")

    # 检查排名 CSS 内嵌
    if '<style>' in html and 'ranking-card' in html:
        # 找到 <style> 标签中有 ranking 相关 CSS
        style_start = html.find('<style>')
        style_end = html.find('</style>') + 8
        if style_start >= 0:
            style_content = html[style_start:style_end]
            print(f"\n内嵌样式: {len(style_content)} 字符")
            if 'ranking-card' in style_content:
                print("  ✓ 排名 CSS 已内嵌到页面")
            else:
                print("  ✗ 排名 CSS 未内嵌")
    else:
        print("\n  ✗ 未找到 <style> 内嵌样式")

    print("\n测试完成。")
