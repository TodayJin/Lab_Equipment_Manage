""" 设置管理 — 读写 settings.json """

import json, os, sys


def _settings_path():
    """获取 settings.json 的路径：exe 同级目录 / 项目根目录"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "settings.json")


def _default_db_dir():
    """默认数据库目录：exe 同级 / 项目根目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


DEFAULTS = {
    "db_path": "",
    "port": 5000,
    "items_per_page": 15,
    "auto_start_server": False,   # 开机自启时自动启动服务器
    "minimize_to_tray": True,      # 关闭窗口最小化到系统托盘
}


def load():
    """读取设置，缺失的用默认值"""
    path = _settings_path()
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    settings = dict(DEFAULTS)
    for k in DEFAULTS:
        if k in data:
            settings[k] = data[k]
    return settings


def save(settings: dict):
    """保存设置"""
    path = _settings_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_default_db_path():
    """默认数据库路径：exe 同级 / 项目根 instance/ 下"""
    return os.path.join(_default_db_dir(), "instance", "lab.db")


def get_db_uri(db_path=""):
    """根据设置生成数据库连接字符串"""
    if not db_path:
        db_path = get_default_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite:///{db_path}"
