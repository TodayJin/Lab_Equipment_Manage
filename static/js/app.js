// 电子技术创新实验室 - 器材管理系统
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss flash messages
    document.querySelectorAll('.flash-msg').forEach(el => {
        setTimeout(() => {
            const alert = bootstrap.Alert.getOrCreateInstance(el);
            if (alert) alert.close();
        }, 4000);
    });
    document.querySelectorAll('.auth-flash').forEach(el => {
        setTimeout(() => {
            const alert = bootstrap.Alert.getOrCreateInstance(el);
            if (alert) alert.close();
        }, 3000);
    });

    // Restore scroll position after form submission
    const savedScroll = sessionStorage.getItem('scrollY_' + location.pathname);
    if (savedScroll && parseInt(savedScroll) > 0) {
        setTimeout(() => {
            window.scrollTo(0, parseInt(savedScroll));
            sessionStorage.removeItem('scrollY_' + location.pathname);
        }, 100);
    }
});

// Save scroll position before form submit
document.addEventListener('submit', function(e) {
    const form = e.target.closest('form');
    if (form && form.method.toUpperCase() === 'POST') {
        sessionStorage.setItem('scrollY_' + location.pathname, window.scrollY);
    }
});

// 切换密码可见性
function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('bi-eye', 'bi-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('bi-eye-slash', 'bi-eye');
    }
}

// ═══════════════ Toast 通知系统 ═══════════════
const LabToast = {
    _container: null,

    _ensureContainer() {
        if (!this._container) {
            this._container = document.createElement('div');
            this._container.className = 'toast-container';
            document.body.appendChild(this._container);
        }
        return this._container;
    },

    show(message, type = 'info', duration = 5000) {
        const container = this._ensureContainer();
        const icons = { info: 'bi-info-circle', warning: 'bi-exclamation-triangle', danger: 'bi-x-circle', success: 'bi-check-circle' };
        const item = document.createElement('div');
        item.className = `toast-item ${type}`;
        item.innerHTML = `<i class="bi ${icons[type] || icons.info}"></i><span>${message}</span><span class="toast-close" onclick="this.parentElement.remove()">&times;</span>`;
        container.appendChild(item);
        if (duration > 0) {
            setTimeout(() => {
                item.classList.add('toast-fade-out');
                setTimeout(() => item.remove(), 300);
            }, duration);
        }
        return item;
    },

    notifyBrowser(title, body) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, { body, requireInteraction: true, tag: 'lab-renew' });
        }
    }
};

// ═══════════════ 全局续签检测（所有标签页生效） ═══════════════
(function() {
    const RENEW_HOURS = [3, 6, 9];
    const HARD_LIMIT_H = 12;
    const RENEW_GRACE_MIN = 5;
    const STORAGE_KEY = 'lab_signin_ts';
    const WARNED_KEY = 'lab_renew_warned';

    let renewCountdownSec = 0;

    function getSignInTs() {
        const v = localStorage.getItem(STORAGE_KEY);
        return v ? parseInt(v) : null;
    }

    function fmtDur(totalMin) {
        const h = Math.floor(totalMin / 60);
        const m = totalMin % 60;
        return h > 0 ? h + 'h ' + m + 'm' : m + 'm';
    }

    function doAutoSignout() {
        stopAlertSound();
        removeRenewModal();
        fetch('/lab/checkin/auto-signout', { method: 'POST' })
        .then(r => r.json()).then(data => {
            localStorage.removeItem(STORAGE_KEY);
            localStorage.removeItem(WARNED_KEY);
            window.location.href = window.location.href.split('?')[0] + '?_=' + Date.now();
        })
        .catch(function() {
            // 网络失败时强制刷新页面，让服务端 _auto_signout_expired 处理
            localStorage.removeItem(STORAGE_KEY);
            localStorage.removeItem(WARNED_KEY);
            window.location.reload();
        });
    }

    let alertSoundTimer = null;

    function startAlertSound() {
        stopAlertSound();
        playBeep();
        alertSoundTimer = setInterval(playBeep, 2000);
        setTimeout(function() { stopAlertSound(); }, 30000);
    }

    function stopAlertSound() {
        if (alertSoundTimer) { clearInterval(alertSoundTimer); alertSoundTimer = null; }
    }

    function playBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            [0, 0.25, 0.5].forEach(function(delay) {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = 'square';
                osc.frequency.value = 800;
                gain.gain.value = 0.15;
                osc.start(ctx.currentTime + delay);
                osc.stop(ctx.currentTime + delay + 0.1);
            });
        } catch(e) { /* ignore */ }
    }

    function showRenewModal(hour) {
        removeRenewModal();
        renewCountdownSec = RENEW_GRACE_MIN * 60;
        const label = hour >= 1 ? hour + ' 小时' : Math.round(hour * 60) + ' 分钟';

        startAlertSound();

        LabToast.notifyBrowser('续签确认 — 已在线 ' + label, RENEW_GRACE_MIN + ' 分钟内不响应将自动签退。');

        const overlay = document.createElement('div');
        overlay.className = 'afk-warning-overlay';
        overlay.id = 'renewModal';
        overlay.innerHTML = `
            <div class="afk-warning-card">
                <i class="bi bi-clock-history" style="font-size:48px;color:var(--warning);display:block;margin-bottom:12px"></i>
                <h5 class="fw-bold mb-2">续签确认 — 已在线 ${label}</h5>
                <p class="text-muted small mb-3">请确认你仍在实验室，${RENEW_GRACE_MIN} 分钟内不响应将自动签退。</p>
                <div class="afk-countdown mb-3" id="renewCountdown">${RENEW_GRACE_MIN}:00</div>
                <div class="d-flex gap-2 justify-content-center">
                    <button class="btn btn-primary" onclick="LabRenew.confirm()"><i class="bi bi-hand-thumbs-up"></i> 我在实验室</button>
                    <button class="btn btn-outline-danger" onclick="LabRenew.signout()"><i class="bi bi-box-arrow-right"></i> 签退</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
    }

    function removeRenewModal() {
        stopAlertSound();
        const el = document.getElementById('renewModal');
        if (el) el.remove();
        renewCountdownSec = 0;
    }

    // 当前会话已检查过的续签点（不存 localStorage，刷新页面后重置）
    const warnedInSession = {};

    function tick() {
        const ts = getSignInTs();
        if (!ts) return;

        const elapsedMin = Math.floor((Date.now() - ts) / 60000);

        // Update countdown display if on checkin page
        const durEl = document.getElementById('signinDuration');
        const afkEl = document.getElementById('afkCountdown');
        const panel = document.getElementById('countdownPanel');
        if (panel) panel.style.display = '';
        if (durEl) durEl.textContent = fmtDur(elapsedMin);

        // 12h hard limit
        if (elapsedMin >= HARD_LIMIT_H * 60) { doAutoSignout(); return; }

        // 已有续签弹窗 —— 倒计时
        if (renewCountdownSec > 0) {
            renewCountdownSec--;
            const el = document.getElementById('renewCountdown');
            if (el) {
                const m = Math.floor(renewCountdownSec / 60), s = renewCountdownSec % 60;
                el.textContent = m + ':' + s.toString().padStart(2, '0');
            }
            if (renewCountdownSec <= 0) { removeRenewModal(); doAutoSignout(); }
            return;  // 已有弹窗时不再检查续签点
        }

        // 检查所有续签点，找到需要提醒的
        for (let h of RENEW_HOURS) {
            // 当前已过 h 小时，且本会话还没提醒过
            if (elapsedMin >= h * 60 && !warnedInSession['h' + h]) {
                warnedInSession['h' + h] = true;
                // 记录到 localStorage 用于跨标签页同步
                try {
                    const data = JSON.parse(localStorage.getItem(WARNED_KEY) || '{}');
                    data['h' + h] = true;
                    localStorage.setItem(WARNED_KEY, JSON.stringify(data));
                } catch(e) {}
                showRenewModal(h);
                return;  // 一次只弹一个窗
            }
        }

        // 如果已过续签点但没弹窗（比如用户刷新了页面，且已过了提醒窗口）
        // 获取最近的未完成续签点，如果倒计时还没结束就重新弹窗
        for (let h of [...RENEW_HOURS].reverse()) {
            if (elapsedMin >= h * 60 && elapsedMin < h * 60 + RENEW_GRACE_MIN) {
                if (!warnedInSession['grace_' + h]) {
                    try {
                        const data = JSON.parse(localStorage.getItem(WARNED_KEY) || '{}');
                        if (!data['h' + h]) {
                            // 服务器端已自动签退或用户之前已响应过
                            continue;
                        }
                    } catch(e) {}
                    // 重新弹窗——用户应该还在续签倒计时内
                    warnedInSession['grace_' + h] = true;
                    showRenewModal(h);
                    return;
                }
            }
        }

        // Next-check countdown display
        if (afkEl && renewCountdownSec === 0) {
            let nextCheck = HARD_LIMIT_H * 60;
            for (let c of RENEW_HOURS) { if (elapsedMin < c * 60) { nextCheck = c * 60; break; } }
            const remain = Math.max(0, nextCheck - elapsedMin);
            afkEl.textContent = fmtDur(remain);
            afkEl.style.color = remain <= 30 ? '#ef4444' : '#f59e0b';
        }
    }

    // Listen for cross-tab changes
    window.addEventListener('storage', function(e) {
        if (e.key === STORAGE_KEY && e.newValue === null) {
            removeRenewModal();
        }
    });

    // 页面打开时，同步其他标签页的提醒状态
    try {
        const warnedData = JSON.parse(localStorage.getItem(WARNED_KEY) || '{}');
        for (let k of Object.keys(warnedData)) {
            warnedInSession[k] = warnedData[k];
        }
    } catch(e) {}

    // Expose
    window.LabRenew = {
        setSignInTs: function(ts) { localStorage.setItem(STORAGE_KEY, ts); },
        confirm: function() {
            stopAlertSound();
            removeRenewModal();
            LabToast.show('已确认在线，续签成功。', 'success', 3000);
        },
        signout: function() {
            stopAlertSound();
            doAutoSignout();
        },
        tick: tick
    };

    setInterval(tick, 1000);
    tick();
})();

// ═══════════════ 全局未读消息轮询（所有页面生效） ═══════════════
(function() {
    function poll() {
        // 在群聊/共享文件页面不显示未读红点
        if (location.pathname.startsWith('/chat')) {
            var badge = document.querySelector('.chat-unread-badge');
            if (badge) badge.style.display = 'none';
            return;
        }
        fetch('/chat/unread')
        .then(r => r.json()).then(function(data) {
            var badge = document.querySelector('.chat-unread-badge');
            if (data && data.count > 0) {
                if (badge) {
                    badge.textContent = data.count;
                    badge.style.display = '';
                } else {
                    var navItem = document.querySelector('.sidebar-nav a[href*="/chat"]');
                    if (navItem && !navItem.querySelector('.chat-unread-badge')) {
                        var span = document.createElement('span');
                        span.className = 'chat-unread-badge';
                        span.textContent = data.count;
                        navItem.appendChild(span);
                    }
                }
            } else {
                if (badge) badge.style.display = 'none';
            }
        }).catch(function() {});
    }

    poll();
    setInterval(poll, 3000);
})();

// ═══════════════ 全局 P2P 文件轮询（所有页面生效） ═══════════════
(function() {
    var lastP2pId = 0;
    var started = false;

    function fmtP2pSize(bytes) {
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
        return (bytes / 1073741824).toFixed(2) + ' GB';
    }

    function poll() {
        fetch('/chat/p2p/pending?since=' + lastP2pId)
        .then(r => r.json()).then(function(data) {
            if (!data || !Array.isArray(data) || data.length === 0) return;
            data.forEach(function(t) {
                lastP2pId = Math.max(lastP2pId, t.id);
                var msg = '<strong>' + t.sender + '</strong> 发给你：' + t.original_name + ' (' + fmtP2pSize(t.size) + ')';
                var toast = LabToast.show(msg, 'info', 0);  // 0 = don't auto-dismiss
                if (toast) {
                    toast.style.cursor = 'pointer';
                    toast.style.pointerEvents = 'auto';
                    toast.onclick = function(e) {
                        e.stopPropagation();
                        window.location.href = '/chat/files';
                    };
                    // Add a "查看" button
                    var btn = document.createElement('button');
                    btn.textContent = '查看';
                    btn.className = 'btn btn-sm btn-primary ms-2';
                    btn.style.pointerEvents = 'auto';
                    btn.onclick = function(e) {
                        e.stopPropagation();
                        window.location.href = '/chat/files';
                    };
                    toast.appendChild(btn);
                    // Auto-dismiss after 15s
                    setTimeout(function() {
                        if (toast.parentElement) {
                            toast.classList.add('toast-fade-out');
                            setTimeout(function() { if (toast.parentElement) toast.remove(); }, 300);
                        }
                    }, 15000);
                }
            });
            if (location.pathname === '/chat/files') {
                setTimeout(function() { location.reload(); }, 2000);
            }
        }).catch(function() {});
    }

    // First: get baseline max ID, THEN start polling
    fetch('/chat/p2p/pending?init=1')
    .then(r => r.json()).then(function(data) {
        if (data && data.max_id) lastP2pId = data.max_id;
        // Also check page for data-p2p-id
        document.querySelectorAll('[data-p2p-id]').forEach(function(el) {
            var id = parseInt(el.dataset.p2pId);
            if (id > lastP2pId) lastP2pId = id;
        });
        if (!started) {
            started = true;
            setInterval(poll, 5000);
        }
    }).catch(function() {
        // Even if init fails, start polling
        if (!started) {
            started = true;
            setInterval(poll, 5000);
        }
    });
})();
