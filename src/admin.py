"""
电子技术创新实验室 - 服务器管理面板
双击启动 — 环境检测、服务启停、日志、开机自启、系统托盘。
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import socket
import threading
import sys
import os
import queue
import webbrowser
import json
import urllib.request
import urllib.error
import tempfile
import time
from pathlib import Path
from PIL import Image, ImageDraw

from src.settings import load as load_settings, save as save_settings, DEFAULTS as SETTING_DEFAULTS, get_default_db_path

# 版本和更新配置
CURRENT_VERSION = "v3.2.2"
GITHUB_REPO = "TodayJin/Lab_Equipment_Manage"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# 判断是否打包成 exe
IS_FROZEN = getattr(sys, "frozen", False)
BASE_DIR = Path(sys.executable).parent if IS_FROZEN else Path(__file__).parent.parent
PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"
PYTHONW = BASE_DIR / "venv" / "Scripts" / "pythonw.exe"
RUN_PY = BASE_DIR / "run.py"
TASK_NAME = "LabManagerServer"
REQ_TXT = BASE_DIR / "requirements.txt"

if IS_FROZEN:
    sys.path.insert(0, str(BASE_DIR))

try:
    import pystray as _pystray_mod
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "无法获取"


class ServerManager:
    def __init__(self, root):
        self.root = root
        self.root.title("电子技术创新实验室 - 服务器管理")
        self.root.geometry("720x600")
        self.root.resizable(True, True)
        self.root.minsize(620, 420)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._boot_mode = 'auto' if '--auto' in sys.argv else 'normal'

        # 手动启动才做单实例检测，开机自启不检测（因为它是第一个实例）
        if self._boot_mode != 'auto':
            self._is_primary = self._acquire_lock()
            if not self._is_primary:
                self._notify_existing()
                self.root.destroy()
                return

        self.process = None
        self.log_queue = queue.Queue()
        self.running = False
        self.autostart_enabled = None
        self.env_ok = False
        self._stg = load_settings()
        self._shutdown_event = threading.Event()
        self._tray_icon = None
        self._tray_running = False

        self._build_ui()
        self._poll_queue()
        self.root.after(400, self._run_env_check)
        self.root.after(1000, self._update_stats)
        self._check_restore_signal()

        # 系统托盘图标常驻
        if TRAY_AVAILABLE:
            self.root.after(500, self._show_tray)

        # 开机模式强制自动启服务和托盘
        if self._boot_mode == 'auto':
            self._append_log("[系统] 开机自启模式\n")
            self.root.after(2500, self._auto_start_server)
            self.root.after(3500, self._hide_to_tray)

    def _auto_start_server(self):
        """开机自启时轮询直到环境就绪再启动"""
        if self.running:
            return
        if self.env_ok:
            self._append_log("[系统] 开机自动启动服务器\n")
            self.start_server()
            return
        # 环境还没检测完，等1秒再试
        self._append_log("[系统] 等待环境就绪...\n")
        self.root.after(1000, self._auto_start_server)

    def _get_port(self):
        return int(self._stg.get("port", 5000))

    def _acquire_lock(self):
        """单实例检测：pid 文件 + 端口双重"""
        # 1. 同 session pid 文件检测
        self._pid_path = os.path.join(os.environ.get('TEMP', '.'), '.labmanager_pid')
        try:
            if os.path.exists(self._pid_path):
                with open(self._pid_path, 'r') as f:
                    old_pid = int(f.read().strip())
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.OpenProcess(0x0400, False, old_pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        return False
                except Exception:
                    pass
        except Exception:
            pass

        # 2. 跨 session 端口检测（服务器在跑 = 已有实例）
        try:
            stg = load_settings()
            port = stg.get("port", 5000)
        except Exception:
            port = 5000
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            s.connect(('127.0.0.1', port))
            s.close()
            return False
        except (OSError, socket.timeout):
            pass

        # 写新 pid
        try:
            with open(self._pid_path, 'w') as f:
                f.write(str(os.getpid()))
        except Exception:
            pass
        return True

    def _notify_existing(self):
        """通知已有实例 — 写信号文件 + 激活窗口"""
        restore_path = os.path.join(os.environ.get('TEMP', '.'), '.labmanager_restore')
        try:
            with open(restore_path, 'w') as f:
                f.write('1')
        except Exception:
            pass
        # 同时尝试用 FindWindow 激活已有窗口
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, '电子技术创新实验室 - 服务器管理')
            if hwnd:
                user32.ShowWindow(hwnd, 9)   # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        # 弹提示
        hostname = socket.gethostname()
        try:
            stg = load_settings()
            port = stg.get("port", 5000)
        except Exception:
            port = 5000
        messagebox.showinfo(
            "LabManager 已在运行",
            f"程序已在后台运行中。\n\n访问地址：http://{hostname}:{port}"
        )

    def _check_restore_signal(self):
        """每 2 秒检查恢复信号文件"""
        restore_path = os.path.join(os.environ.get('TEMP', '.'), '.labmanager_restore')
        try:
            if os.path.exists(restore_path):
                os.unlink(restore_path)
                self._restore_window()
        except Exception:
            pass
        self.root.after(2000, self._check_restore_signal)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=16)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)

        # ── 标题 ──
        ttk.Label(main, text="🔬 电子技术创新实验室 - 服务器管理",
                  font=("Microsoft YaHei UI", 17, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # ── 访问地址（醒目）──
        url_bar = ttk.LabelFrame(main, text="访问地址（固定）", padding=10)
        url_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        url_bar.columnconfigure(0, weight=1)

        hostname = socket.gethostname()
        port = self._get_port()
        fixed_url = f"http://{hostname}:{port}"
        ip_url = f"http://{get_local_ip()}:{port}"

        self.big_url_label = tk.Label(
            url_bar,
            text=f"🌐  {fixed_url}",
            font=("Consolas", 16, "bold"),
            fg="#2563eb",
            anchor="center",
            cursor="hand2"
        )
        self.big_url_label.grid(row=0, column=0, sticky="ew")

        self.small_url_label = tk.Label(
            url_bar,
            text=f"备用: {ip_url}  |  本机: http://localhost:5000",
            font=("Microsoft YaHei UI", 9),
            fg="#94a3b8",
            anchor="center"
        )
        self.small_url_label.grid(row=1, column=0, sticky="ew")

        self.btn_copy_url = ttk.Button(url_bar, text="复制地址", command=self._copy_url)
        self.btn_copy_url.grid(row=0, column=1, rowspan=2, padx=(8, 0))
        self.btn_copy_url.configure(state="disabled")

        # ── 环境状态 + 服务器状态 (并排) ──
        top_row = ttk.Frame(main)
        top_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=1)

        # 左：服务器状态
        self._build_server_status(top_row, 0)
        # 右：环境检测
        self._build_env_status(top_row, 1)

        # ── 按钮栏 ──
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        self.btn_start = ttk.Button(btn_frame, text="▶  启动服务", command=self.start_server, state="disabled")
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_stop = ttk.Button(btn_frame, text="■  停止服务", command=self.stop_server, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 8))

        self.btn_browser = ttk.Button(btn_frame, text="🌐 打开网页", command=self.open_browser, state="disabled")
        self.btn_browser.pack(side="left", padx=(0, 8))

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=12)

        self.btn_clear = ttk.Button(btn_frame, text="清空日志", command=self.clear_log)
        self.btn_clear.pack(side="left", padx=(0, 8))

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=12)

        self.btn_settings = ttk.Button(btn_frame, text="⚙ 设置", command=self._open_settings)
        self.btn_settings.pack(side="left")

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=12)

        self.btn_update = ttk.Button(btn_frame, text="🔄 检查更新", command=self.check_update)
        self.btn_update.pack(side="left")

        # ── 日志区 ──
        log_frame = ttk.LabelFrame(main, text="运行日志", padding=4)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        self.log_area = scrolledtext.ScrolledText(
            log_frame, wrap="word", font=("Consolas", 10),
            bg="#1a1a2e", fg="#c0c0c0", insertbackground="white",
            relief="flat", borderwidth=0
        )
        self.log_area.grid(row=0, column=0, sticky="nsew")
        self.log_area.configure(state="disabled")

        # ── 底部 ──
        bottom = ttk.Frame(main)
        bottom.grid(row=4, column=0, sticky="ew")
        ip = get_local_ip()
        port = self._get_port()

        self.stats_label = ttk.Label(bottom, text="",
                                     foreground="gray", font=("Microsoft YaHei UI", 9))
        self.stats_label.pack(side="left")

        ttk.Label(bottom, text=f"  本机 IP: {ip}  |  端口: {port}  |  本地: http://localhost:{port}",
                  foreground="gray", font=("Microsoft YaHei UI", 9)).pack(side="right")

    def _build_server_status(self, parent, col):
        frame = ttk.LabelFrame(parent, text="服务器状态", padding=12)
        frame.grid(row=0, column=col, sticky="nsew", padx=(0, 6) if col == 0 else (6, 0))
        frame.columnconfigure(1, weight=1)

        self.status_indicator = tk.Canvas(frame, width=14, height=14, highlightthickness=0)
        self.status_indicator.grid(row=0, column=0, padx=(0, 8))

        self.status_label = ttk.Label(frame, text="已停止", font=("Microsoft YaHei UI", 13))
        self.status_label.grid(row=0, column=1, sticky="w")

        self.url_label = ttk.Label(frame, text="", foreground="gray")
        self.url_label.grid(row=1, column=1, sticky="w", pady=(2, 0))

    def _build_env_status(self, parent, col):
        frame = ttk.LabelFrame(parent, text="环境检测", padding=12)
        frame.grid(row=0, column=col, sticky="nsew", padx=(0, 6) if col == 0 else (6, 0))
        frame.columnconfigure(0, weight=1)

        self.env_labels = {}
        checks = [
            ("env_python", "Python"),
            ("env_venv",   "虚拟环境"),
            ("env_deps",   "依赖包"),
        ]
        for i, (key, name) in enumerate(checks):
            lbl = ttk.Label(frame, text=f"⏳ {name}: 检测中...", foreground="gray")
            lbl.grid(row=i, column=0, sticky="w", pady=2)
            self.env_labels[key] = lbl

        self.btn_fix = ttk.Button(frame, text="🔧 一键修复", command=self._fix_all, state="disabled")
        self.btn_fix.grid(row=len(checks), column=0, sticky="w", pady=(8, 0))

        self.btn_recheck = ttk.Button(frame, text="重新检测", command=self._run_env_check)
        self.btn_recheck.grid(row=len(checks), column=0, sticky="e", pady=(8, 0))

    # ══════════════════════════════════════════════
    # 环境检测
    # ══════════════════════════════════════════════

    def _run_env_check(self):
        """后台线程执行环境检测"""
        threading.Thread(target=self._do_env_check, daemon=True).start()

    def _do_env_check(self):
        """检测 Python → venv → 依赖"""
        results = {}

        if IS_FROZEN:
            # 打包成 exe，环境全内置
            results["python"] = (True, "已内置（exe 打包）")
            results["venv"] = (True, "已内置")
            results["deps"] = (True, "已内置")
        else:
            # 1. Python
            try:
                r = subprocess.run(["python", "--version"], capture_output=True, text=True, timeout=5)
                results["python"] = (True, r.stdout.strip())
            except Exception:
                results["python"] = (False, "未找到 Python，请从 python.org 安装")

            # 2. venv
            results["venv"] = (PYTHON.exists(), "venv 已就绪" if PYTHON.exists() else "虚拟环境未创建")

            # 3. 依赖
            if PYTHON.exists():
                missing = self._check_deps()
                results["deps"] = (len(missing) == 0, "所有依赖已安装" if len(missing) == 0 else f"缺失: {', '.join(missing)}")
            else:
                results["deps"] = (False, "需要先创建虚拟环境")

        self.root.after(0, self._apply_env_results, results)

    def _check_deps(self):
        """返回缺失的依赖列表"""
        missing = []
        if not REQ_TXT.exists():
            return missing

        for line in REQ_TXT.read_text().strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pkg = line.split(">=")[0].split("==")[0].split(">")[0].strip()
            if not pkg:
                continue
            try:
                r = subprocess.run(
                    [str(PYTHON), "-c", f"import {pkg}"],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode != 0:
                    missing.append(pkg)
            except Exception:
                missing.append(pkg)
        return missing

    def _apply_env_results(self, results):
        """在主线程更新环境 UI"""
        for key, name, icon_ok, icon_fail in [
            ("python", "Python", "✓", "✗"),
            ("venv", "虚拟环境", "✓", "✗"),
            ("deps", "依赖包", "✓", "✗"),
        ]:
            ok, msg = results.get(key, (False, "检测失败"))
            icon = icon_ok if ok else icon_fail
            color = "#16a34a" if ok else "#dc2626"
            self.env_labels[f"env_{key}"].configure(text=f"{icon} {name}: {msg}", foreground=color)

        all_ok = all(results.get(k, (False,))[0] for k in ["python", "venv", "deps"])
        self.env_ok = all_ok

        if all_ok:
            self.btn_fix.configure(state="disabled")
            self.btn_start.configure(state="normal")
            self._append_log("[系统] 环境检测通过 ✓\n")
        else:
            self.btn_fix.configure(state="normal")
            self.btn_start.configure(state="disabled")
            if not results.get("python", (False,))[0]:
                self.btn_fix.configure(state="disabled")  # Python 必须手动装

    def _fix_all(self):
        """一键修复环境"""
        if IS_FROZEN:
            self._append_log("[系统] exe 模式，无需修复环境\n")
            return
        if PYTHON.exists():
            self._append_log("[系统] 正在自动配置环境...\n")
            self.btn_fix.configure(state="disabled", text="⏳ 修复中...")
            threading.Thread(target=self._do_fix, daemon=True).start()
        else:
            messagebox.showerror("无法修复", "Python 未安装，请先从 python.org 下载安装。")

    def _do_fix(self):
        """后台执行修复"""
        # venv
        if not PYTHON.exists():
            r = subprocess.run(
                ["python", "-m", "venv", str(BASE_DIR / "venv")],
                capture_output=True, text=True, timeout=60, cwd=str(BASE_DIR)
            )
            if r.returncode != 0:
                self.root.after(0, lambda: self._append_log(f"[错误] 创建虚拟环境失败: {r.stderr}\n"))
                self.root.after(0, lambda: self.btn_fix.configure(state="normal", text="🔧 一键修复"))
                self.root.after(0, self._run_env_check)
                return

        # 安装依赖
        r = subprocess.run(
            [str(PYTHON), "-m", "pip", "install", "-r", str(REQ_TXT), "--quiet"],
            capture_output=True, text=True, timeout=120, cwd=str(BASE_DIR)
        )
        if r.returncode != 0:
            self.root.after(0, lambda: self._append_log(f"[错误] 安装依赖失败: {r.stderr[-200:]}\n"))
            self.root.after(0, lambda: self.btn_fix.configure(state="normal", text="🔧 一键修复"))
        else:
            self.root.after(0, lambda: self._append_log("[系统] 环境修复完成 ✓\n"))

        self.root.after(500, self._run_env_check)

    # ══════════════════════════════════════════════
    # 状态
    # ══════════════════════════════════════════════

    def _update_status(self):
        ip = get_local_ip()
        hostname = socket.gethostname()
        port = self._get_port()
        fixed_url = f"http://{hostname}:{port}"
        self.status_indicator.delete("all")
        if self.running:
            self.status_indicator.create_oval(1, 1, 13, 13, fill="#22c55e", outline="#16a34a")
            self.status_label.configure(text="运行中", foreground="#16a34a")
            self.url_label.configure(text=f"本机: http://localhost:{port}")
            self.big_url_label.configure(
                text=f"🌐  {fixed_url}",
                fg="#2563eb", font=("Consolas", 16, "bold")
            )
            self.small_url_label.configure(
                text=f"备用: http://{ip}:{port}  |  本机: http://localhost:{port}"
            )
            self.btn_copy_url.configure(state="normal")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.btn_browser.configure(state="normal")
            # 更新托盘图标为绿色
            if TRAY_AVAILABLE and self._tray_running:
                self._show_tray()
        else:
            self.status_indicator.create_oval(1, 1, 13, 13, fill="#94a3b8", outline="#64748b")
            self.status_label.configure(text="已停止", foreground="#64748b")
            self.url_label.configure(text="")
            # 始终显示固定地址，醒目蓝色
            self.big_url_label.configure(
                text=f"🌐  {fixed_url}",
                fg="#2563eb", font=("Consolas", 16, "bold")
            )
            self.small_url_label.configure(
                text=f"备用: http://{ip}:{port}  |  本机: http://localhost:{port}（服务未启动）"
            )
            self.btn_copy_url.configure(state="normal")  # 始终可复制
            self.btn_browser.configure(state="disabled")
            self.btn_stop.configure(state="disabled")
            if self.env_ok:
                self.btn_start.configure(state="normal")

    # ══════════════════════════════════════════════
    # 开机自启（设置里管理，面板无需按钮）
    # ══════════════════════════════════════════════

    def _check_autostart(self):
        try:
            r = subprocess.run(
                f'reg query HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v {TASK_NAME}',
                shell=True, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.autostart_enabled = (r.returncode == 0)
        except Exception:
            self.autostart_enabled = False

    def _enable_autostart(self):
        # 用注册表 HKCU\Run 而不是 schtasks，确保在用户会话启动（有托盘图标）
        if IS_FROZEN:
            cmd = f'reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v {TASK_NAME} /t REG_SZ /d "\\"{sys.executable}\\" --auto" /f'
        else:
            pythonw = str(PYTHONW)
            script = str(RUN_PY)
            cmd = f'reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v {TASK_NAME} /t REG_SZ /d "\\"{pythonw}\\" \\"{script}\\" --auto" /f'
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0:
                self.autostart_enabled = True
                self._append_log("[系统] 开机自启已开启（注册表方式）\n")
            else:
                self._append_log(f"[系统] 设置失败: {r.stderr}\n")
        except Exception as e:
            self._append_log(f"[错误] {e}\n")

    def _disable_autostart(self):
        cmd = f'reg delete HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v {TASK_NAME} /f'
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0:
                self.autostart_enabled = False
                self._append_log("[系统] 开机自启已关闭\n")
            else:
                self._append_log(f"[错误] 关闭失败: {r.stderr}\n")
        except Exception as e:
            self._append_log(f"[错误] {e}\n")

    def _run_as_admin_enable(self):
        """注册表方式不需要提权，直接调用 _enable_autostart"""
        pass

    # ══════════════════════════════════════════════
    # 日志
    # ══════════════════════════════════════════════

    def _append_log(self, text):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", text)
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def _read_stdout(self):
        for line in iter(self.process.stdout.readline, ""):
            if not line:
                break
            self.log_queue.put(line)
        self.process.stdout.close()

    def _poll_queue(self):
        while True:
            try:
                line = self.log_queue.get_nowait()
                self._append_log(line)
            except queue.Empty:
                break
        if self.process and self.process.poll() is not None:
            self.running = False
            self._append_log("\n[系统] 服务器已停止\n")
            self._update_status()
        self.root.after(200, self._poll_queue)

    # ══════════════════════════════════════════════
    # 服务控制
    # ══════════════════════════════════════════════

    def start_server(self):
        if not self.env_ok:
            messagebox.showwarning("无法启动", "环境检测未通过，请先点击「一键修复」。")
            return

        self._append_log("[系统] 正在启动服务器...\n")

        if IS_FROZEN:
            self._start_server_direct()
        else:
            self._start_server_subprocess()

    def _start_server_direct(self):
        """exe 模式：daemon 线程跑 waitress"""
        self._shutdown_event.clear()

        def _run():
            try:
                from src.app import create_app
                app = create_app()
                self.log_queue.put("[系统] 服务器启动成功！\n\n")
                from waitress import serve
                serve(app, host="0.0.0.0", port=self._get_port(), threads=4, _quiet=True)
            except Exception as e:
                if not self._shutdown_event.is_set():
                    self.log_queue.put(f"[错误] 服务器异常: {e}\n")
                self.running = False
                self.root.after(0, self._update_status)

        threading.Thread(target=_run, daemon=True).start()
        self.running = True
        self._update_status()

    def _start_server_subprocess(self):
        """开发模式：子进程启动"""
        if not PYTHON.exists():
            messagebox.showerror("错误", f"Python 未找到:\n{PYTHON}")
            return

        try:
            self.process = subprocess.Popen(
                [str(PYTHON), str(RUN_PY)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=str(BASE_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.running = True
            self._update_status()
            threading.Thread(target=self._read_stdout, daemon=True).start()
            self._append_log("[系统] 服务器启动成功！\n\n")
        except Exception as e:
            self._append_log(f"[错误] 启动失败: {e}\n")
            self.running = False
            self._update_status()

    def stop_server(self):
        if IS_FROZEN:
            self._shutdown_event.set()
            killed = 0

            # 用 netstat 找占用端口进程并杀死
            try:
                result = subprocess.run(
                    f'netstat -ano | findstr ":{self._get_port()}"',
                    shell=True, capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                seen = set()
                for line in result.stdout.splitlines():
                    parts = line.strip().split()
                    if parts and 'LISTENING' in parts:
                        pid = parts[-1]
                    elif len(parts) >= 2 and parts[1].endswith(f':{self._get_port()}'):
                        pid = parts[-1]
                    else:
                        continue
                    if pid not in seen and pid.isdigit() and int(pid) != os.getpid():
                        seen.add(pid)
                        subprocess.run(['taskkill', '/F', '/PID', pid],
                                       capture_output=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                        killed += 1
            except Exception:
                pass

            if killed > 0:
                self._append_log(f"[系统] 服务器已停止（终止 {killed} 个进程）\n")
            else:
                self._append_log("[系统] 服务器已停止\n")
            self.running = False
            self._update_status()
            return

        if self.process:
            self._append_log("[系统] 正在停止服务器...\n")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self._append_log("[系统] 服务器已停止\n")
            self.process = None
            self.running = False
            self._update_status()
        else:
            self._append_log("[系统] 服务器未在运行。\n")

    def _open_settings(self):
        """打开设置对话框"""
        if self.running:
            messagebox.showwarning("提示", "请先停止服务器再修改设置。")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("系统设置")
        dlg.geometry("560x550")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        # 居中
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 560) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 550) // 2
        dlg.geometry(f"+{x}+{y}")

        # Canvas + Scrollbar
        canvas = tk.Canvas(dlg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        main = ttk.Frame(canvas, padding=20)

        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scroll — only when dialog is focused
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollbar.bind("<MouseWheel>", _on_mousewheel)

        # ── 数据库位置 ──
        ttk.Label(main, text="数据库位置", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(main, text="SQLite 数据库文件的保存路径，所有器材和记录都存这里。",
                  foreground="gray").pack(anchor="w", pady=(2, 6))

        db_frame = ttk.Frame(main)
        db_frame.pack(fill="x")
        current_db = self._stg.get("db_path", "") or get_default_db_path()
        db_path_var = tk.StringVar(value=self._stg.get("db_path", ""))
        db_entry = ttk.Entry(db_frame, textvariable=db_path_var, state="readonly")
        db_entry.pack(side="left", fill="x", expand=True)

        # 提示当前实际使用的路径
        ttk.Label(db_frame, text="（默认: exe 同目录下的 instance/lab.db）",
                  foreground="gray").pack(side="left", padx=(6, 0))

        def _pick_db():
            path = filedialog.asksaveasfilename(
                title="选择数据库位置",
                defaultextension=".db",
                filetypes=[("SQLite 数据库", "*.db"), ("所有文件", "*.*")],
                initialfile="lab.db",
                initialdir=os.path.dirname(get_default_db_path())
            )
            if path:
                db_path_var.set(path)

        ttk.Button(db_frame, text="浏览...", command=_pick_db).pack(side="left", padx=(6, 0))

        # ── 端口号 ──
        ttk.Label(main, text="", font=("", 6)).pack()
        ttk.Label(main, text="端口号", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(main, text="服务器监听的端口，默认 5000。如有冲突可改成其他（如 8080、3000）。",
                  foreground="gray").pack(anchor="w", pady=(2, 6))

        port_frame = ttk.Frame(main)
        port_frame.pack(fill="x")
        port_var = tk.StringVar(value=str(self._get_port()))
        port_entry = ttk.Entry(port_frame, textvariable=port_var, width=10)
        port_entry.pack(side="left")

        # ── 每页条数 ──
        ttk.Label(main, text="", font=("", 6)).pack()
        ttk.Label(main, text="每页显示条数", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(main, text="器材列表、记录查询等页面每页显示多少条数据。",
                  foreground="gray").pack(anchor="w", pady=(2, 6))

        page_frame = ttk.Frame(main)
        page_frame.pack(fill="x")
        page_var = tk.StringVar(value=str(self._stg.get("items_per_page", 15)))
        page_entry = ttk.Entry(page_frame, textvariable=page_var, width=10)
        page_entry.pack(side="left")
        ttk.Label(page_frame, text="条", foreground="gray").pack(side="left", padx=(4, 0))

        # ── 开机自启选项 ──
        ttk.Label(main, text="", font=("", 6)).pack()
        ttk.Label(main, text="开机自启选项", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")

        auto_srv_var = tk.BooleanVar(value=self._stg.get("auto_start_server", False))
        ttk.Checkbutton(main, text="开机自启时自动启动服务器", variable=auto_srv_var).pack(anchor="w", pady=(6, 0))
        ttk.Label(main, text="开启后，设置开机自启会在系统启动时自动运行服务器服务",
                  foreground="gray", font=("", 9)).pack(anchor="w", padx=(24, 0))

        tray_var = tk.BooleanVar(value=self._stg.get("minimize_to_tray", True))
        ttk.Checkbutton(main, text="关闭面板时最小化到系统托盘", variable=tray_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(main, text="关闭面板窗口后，程序图标出现在任务栏右下角通知区域",
                  foreground="gray", font=("", 9)).pack(anchor="w", padx=(24, 0))

        # 开机自启开关按钮
        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=(10, 10))
        auto_frame = ttk.Frame(main)
        auto_frame.pack(fill="x")

        self.autostart_status_var = tk.StringVar(value="检测中...")
        ttk.Label(auto_frame, textvariable=self.autostart_status_var,
                  foreground="gray", font=("", 9)).pack(side="left")

        def _toggle_autostart():
            if self.autostart_enabled:
                self._disable_autostart()
                self._check_autostart()
                self.autostart_status_var.set("已开启" if self.autostart_enabled else "未开启")
            else:
                self._enable_autostart()
                # schtasks 操作可能需要管理员提权，延迟检测
                self.root.after(2000, lambda: self._check_autostart())
                self.root.after(2500, lambda: self.autostart_status_var.set(
                    "已开启" if self.autostart_enabled else "未开启"))

        self._check_autostart()
        if self.autostart_enabled:
            self.autostart_status_var.set("已开启")
            ttk.Button(auto_frame, text="关闭系统自启", command=_toggle_autostart).pack(side="right")
        else:
            self.autostart_status_var.set("未开启")
            ttk.Button(auto_frame, text="设置系统自启", command=_toggle_autostart).pack(side="right")

        # ── 按钮 ──
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(20, 0))

        def _save():
            try:
                port = int(port_var.get())
                if port < 1 or port > 65535:
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "端口号必须是 1-65535 之间的整数。", parent=dlg)
                return
            try:
                pp = int(page_var.get())
                if pp < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "每页条数必须是正整数。", parent=dlg)
                return

            self._stg["db_path"] = db_path_var.get()
            self._stg["port"] = port
            self._stg["items_per_page"] = pp
            self._stg["auto_start_server"] = auto_srv_var.get()
            self._stg["minimize_to_tray"] = tray_var.get()
            save_settings(self._stg)
            self._append_log(f"[系统] 设置已保存（端口={port}, 每页{pp}条）\n")
            self._update_status()
            dlg.destroy()

        ttk.Button(btn_frame, text="保存", command=_save).pack(side="left")
        ttk.Button(btn_frame, text="取消", command=dlg.destroy).pack(side="left", padx=(8, 0))

        def _reset():
            if messagebox.askyesno("确认", "恢复所有设置为默认值？", parent=dlg):
                db_path_var.set("")
                port_var.set(str(SETTING_DEFAULTS["port"]))
                page_var.set(str(SETTING_DEFAULTS["items_per_page"]))

        ttk.Button(btn_frame, text="恢复默认", command=_reset).pack(side="right")

    def open_browser(self):
        webbrowser.open(f"http://localhost:{self._get_port()}")

    def _copy_url(self):
        hostname = socket.gethostname()
        url = f"http://{hostname}:{self._get_port()}"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self._append_log(f"[系统] 已复制地址: {url}\n")

    def clear_log(self):
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")

    # ══════════════════════════════════════════════
    # 系统托盘（常驻）
    # ══════════════════════════════════════════════

    def _create_tray_image(self):
        """创建托盘图标（绿色圆点）"""
        img = Image.new("RGB", (16, 16), (16, 185, 129) if self.running else (100, 100, 100))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 13, 13], fill=(16, 185, 129) if self.running else (148, 163, 184))
        return img

    def _show_tray(self):
        """显示系统托盘图标（覆盖旧图标）"""
        # 先停止旧图标
        if self._tray_icon:
            try: self._tray_icon.stop()
            except: pass
            self._tray_icon = None

        def _toggle_window(icon, item=None):
            self.root.after(0, self._toggle_window)

        def _quit_app(icon, item=None):
            icon.stop()
            self._tray_running = False
            self.root.after(0, self._do_quit)

        menu = _pystray_mod.Menu(
            _pystray_mod.MenuItem("显示/隐藏面板", _toggle_window, default=True),
            _pystray_mod.Menu.SEPARATOR,
            _pystray_mod.MenuItem("退出程序", _quit_app),
        )

        self._tray_icon = _pystray_mod.Icon(
            "labmanager", self._create_tray_image(),
            "电子技术创新实验室 — 器材管理系统", menu
        )
        self._tray_icon.run_detached()
        self._tray_running = True

    def _toggle_window(self):
        """切换窗口显示/隐藏"""
        if self.root.state() == 'withdrawn' or self.root.state() == 'iconic':
            self._restore_window()
        else:
            self._hide_to_tray()

    def _hide_to_tray(self):
        """隐藏主窗口（托盘图标保持在）"""
        self.root.withdraw()
        self._append_log("[提示] 面板已隐藏，点击系统托盘图标恢复\n")

    def _restore_window(self):
        """从托盘恢复窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _do_quit(self):
        """退出程序"""
        if self.running:
            self.stop_server()
        if self._tray_icon:
            try: self._tray_icon.stop()
            except: pass
        self._tray_running = False
        try: os.unlink(self._pid_path)
        except: pass
        self.root.destroy()

    def on_close(self):
        """关闭窗口 → 隐藏到托盘"""
        self._hide_to_tray()

    def _update_stats(self):
        """定时更新统计信息"""
        try:
            from src.models import User, Equipment
            import psutil
            mem = psutil.virtual_memory()
            mem_used = mem.used / (1024 * 1024)
            mem_total = mem.total / (1024 * 1024)
            user_count = User.query.count()
            eq_count = Equipment.query.count()
            self.stats_label.configure(
                text=f"系统: {eq_count}种器材 | {user_count}个用户 | 内存: {mem_used:.0f}/{mem_total:.0f}MB"
            )
        except ImportError:
            try:
                from src.models import User, Equipment
                user_count = User.query.count()
                eq_count = Equipment.query.count()
                self.stats_label.configure(text=f"系统: {eq_count}种器材 | {user_count}个用户")
            except Exception:
                pass
        except Exception:
            pass
        self.root.after(10000, self._update_stats)

    # ══════════════════════════════════════════════
    # 一键更新
    # ══════════════════════════════════════════════

    def check_update(self):
        """检查 GitHub Release 是否有新版本"""
        self.btn_update.configure(state="disabled", text="⏳ 检查中...")
        threading.Thread(target=self._do_check_update, daemon=True).start()

    def _do_check_update(self):
        headers = {"User-Agent": "LabManager"}

        try:
            req = urllib.request.Request(GITHUB_API, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}"
            if e.code == 403:
                msg += "（API 限流，请稍后重试）"
            if e.code == 404:
                msg += "（未找到发布版本）"
            self.root.after(0, lambda: self._append_log(f"[更新] 检查失败: {msg}\n"))
            self.root.after(0, lambda: self.btn_update.configure(state="normal", text="🔄 检查更新"))
            return
        except Exception as e:
            self.root.after(0, lambda: self._append_log(f"[更新] 检查失败: {e}\n"))
            self.root.after(0, lambda: self.btn_update.configure(state="normal", text="🔄 检查更新"))
            return

        latest_tag = data.get("tag_name", "v0.0")
        assets = data.get("assets", [])
        self.root.after(0, lambda: self._append_log(f"[更新] 最新版本: {latest_tag}（当前: {CURRENT_VERSION}）\n"))

        if not self._is_newer(latest_tag, CURRENT_VERSION):
            self.root.after(0, lambda: self._append_log("[更新] 已是最新版本 ✓\n"))
            self.root.after(0, lambda: self.btn_update.configure(state="normal", text="🔄 已是最新"))
            self.root.after(3000, lambda: self.btn_update.configure(text="🔄 检查更新"))
            return

        exe_asset = None
        for a in assets:
            if a["name"].endswith(".exe"):
                exe_asset = a
                break

        if not exe_asset:
            self.root.after(0, lambda: self._append_log("[更新] 未找到 exe 文件\n"))
            self.root.after(0, lambda: self.btn_update.configure(state="normal", text="🔄 检查更新"))
            return

        dl_url = exe_asset["browser_download_url"]
        dl_size = exe_asset["size"]
        self.root.after(0, lambda: self._append_log(f"[更新] 发现新版本 {latest_tag}，大小 {dl_size / 1048576:.1f} MB\n"))

        # 询问用户
        result = [None]
        self.root.after(0, lambda: result.__setitem__(0,
            messagebox.askyesno("发现新版本",
                f"当前版本: {CURRENT_VERSION}\n最新版本: {latest_tag}\n文件大小: {dl_size / 1048576:.1f} MB\n\n是否下载并更新？\n\n更新过程中将自动停止服务。")))

        while result[0] is None:
            time.sleep(0.1)

        if not result[0]:
            self.root.after(0, lambda: self.btn_update.configure(state="normal", text="🔄 检查更新"))
            return

        # 下载（支持重试）
        self.root.after(0, lambda: self._append_log(f"[更新] 正在下载 {latest_tag}...\n"))
        self.root.after(0, lambda: self.btn_update.configure(text=f"⏳ 下载中..."))
        self.root.after(0, lambda: self.root.update_idletasks())

        tmp_path = None
        total = 0
        for attempt in range(3):
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
                tmp_path = tmp.name
                req2 = urllib.request.Request(dl_url, headers=headers)
                with urllib.request.urlopen(req2, timeout=600) as resp2:
                    total = 0
                    while True:
                        chunk = resp2.read(65536)
                        if not chunk:
                            break
                        tmp.write(chunk)
                        total += len(chunk)
                    tmp.close()
                break  # 成功
            except Exception as e:
                try: os.unlink(tmp_path)
                except: pass
                if attempt < 2:
                    self.root.after(0, lambda: self._append_log(f"[更新] 下载失败，2秒后重试（{attempt+2}/3）...\n"))
                    time.sleep(2)
                else:
                    self.root.after(0, lambda: self._append_log(f"[更新] 下载失败: {e}\n"))
                    self.root.after(0, lambda: self.btn_update.configure(state="normal", text="🔄 检查更新"))
                    return

        self.root.after(0, lambda: self._append_log(f"[更新] 下载完成（{total / 1048576:.1f} MB）\n"))

        # 停止服务
        if self.running:
            self.root.after(0, lambda: self._append_log("[更新] 正在停止服务...\n"))
            self.root.after(0, self.stop_server)
            time.sleep(2)

        # 替换 exe
        current_exe = sys.executable if IS_FROZEN else None

        if IS_FROZEN:
            exe_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            exe_path = current_exe
            new_tmp = exe_path + ".new"
            backup_path = exe_path + ".old"

            def _replace():
                try:
                    # 先把新文件放到 .new 旁边
                    os.replace(tmp_path, new_tmp)
                    # 生成替换脚本（等当前进程退出后再执行）
                    bat = (
                        f'@echo off\r\n'
                        f'chcp 65001 >nul\r\n'
                        f'echo Waiting for update...\r\n'
                        f'timeout /t 3 /nobreak >nul\r\n'
                        f'if exist "{backup_path}" del /f "{backup_path}"\r\n'
                        f'rename "{exe_path}" "{os.path.basename(backup_path)}"\r\n'
                        f'rename "{new_tmp}" "{exe_name}"\r\n'
                        f'if exist "{exe_path}" start "" "{exe_path}" --auto\r\n'
                        f'del "%~f0"\r\n'
                    )
                    bat_path = os.path.join(tempfile.gettempdir(), "labmanager_update.bat")
                    with open(bat_path, "w", encoding="utf-8") as f:
                        f.write(bat)
                    subprocess.Popen(f'cmd /c "{bat_path}"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self._append_log(f"[更新] 即将重启以完成更新...\n")
                    # 延迟片刻确保 bat 已启动，然后退出
                    self.root.after(500, self._do_quit)
                except Exception as e:
                    self._append_log(f"[更新] 文件替换失败: {e}\n")
                    try: os.unlink(tmp_path)
                    except: pass
                    try: os.unlink(new_tmp)
                    except: pass

            self.root.after(0, _replace)
        else:
            # 源码模式：保存到 dist 目录
            dist_dir = BASE_DIR / "dist"
            os.makedirs(dist_dir, exist_ok=True)
            new_path = os.path.join(dist_dir, target_name)
            try:
                os.replace(tmp_path, new_path)
                self.root.after(0, lambda: self._append_log(f"[更新] 已保存至 {new_path}\n[更新] 更新完成 ✓\n"))
                self.root.after(0, lambda: messagebox.showinfo("更新完成", f"新版本已保存到:\n{new_path}"))
            except Exception as e:
                self.root.after(0, lambda: self._append_log(f"[更新] 保存失败: {e}\n"))

        self.root.after(0, lambda: self.btn_update.configure(state="normal", text="🔄 检查更新"))

    @staticmethod
    def _is_newer(new_tag, cur_tag):
        """比较 v3.2 格式的版本号"""
        def parse(v):
            try:
                return tuple(int(x) for x in v.lstrip("vV").split("."))
            except Exception:
                return (0,)
        return parse(new_tag) > parse(cur_tag)


if __name__ == "__main__":
    root = tk.Tk()
    app = ServerManager(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
