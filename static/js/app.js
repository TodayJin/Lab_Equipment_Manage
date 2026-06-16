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

// ═══════════════ 续签检测（全局，所有标签页生效） ═══════════════
//   用 localStorage 作唯一状态源，每次 tick() 重新读取，
//   不依赖内存变量，彻底解决跨标签页/页面切换重复弹窗问题
(function() {
    var RENEW_POINTS = [3, 6, 9];        // 3h / 6h / 9h 触发续签
    var HARD_LIMIT_MIN = 12 * 60;        // 12h 硬性签退
    var GRACE_SEC = 5 * 60;              // 5 分钟响应倒计时
    var STORAGE_TS = 'lab_signin_ts';
    var STORAGE_ACK = 'lab_renew_ack';

    var countdownSec = 0;
    var activeRenewIdx = -1;  // 当前弹窗对应 RENEW_POINTS 的索引
    var beepTimer = null;

    function readAck() {
        try { return JSON.parse(localStorage.getItem(STORAGE_ACK)) || {}; } catch(e) { return {}; }
    }

    function writeAck(obj) {
        localStorage.setItem(STORAGE_ACK, JSON.stringify(obj));
    }

    function ackKey(h) { return 'h' + h; }

    function getSigninTs() {
        var v = localStorage.getItem(STORAGE_TS);
        return v ? parseInt(v, 10) : null;
    }

    function fmtDur(m) {
        var h = Math.floor(m / 60), r = m % 60;
        return h > 0 ? h + 'h ' + r + 'm' : r + 'm';
    }

    function beep() {
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            [0, 0.25, 0.5].forEach(function(d) {
                var o = ctx.createOscillator(), g = ctx.createGain();
                o.connect(g); g.connect(ctx.destination);
                o.type = 'square'; o.frequency.value = 800; g.gain.value = 0.15;
                o.start(ctx.currentTime + d); o.stop(ctx.currentTime + d + 0.1);
            });
        } catch(e) {}
    }

    function startBeep() {
        stopBeep();
        beep();
        beepTimer = setInterval(beep, 2000);
        setTimeout(stopBeep, 15000);
    }

    function stopBeep() {
        if (beepTimer) { clearInterval(beepTimer); beepTimer = null; }
    }

    function removeModal() {
        stopBeep();
        var el = document.getElementById('renewModal');
        if (el) el.remove();
        countdownSec = 0;
        activeRenewIdx = -1;
    }

    function showModal(hour) {
        removeModal();
        countdownSec = GRACE_SEC;
        var label = hour >= 1 ? hour + ' 小时' : Math.round(hour * 60) + ' 分钟';
        startBeep();

        LabToast.notifyBrowser('续签确认 — 已在线 ' + label, Math.round(GRACE_SEC / 60) + ' 分钟内不响应将自动签退。');

        var div = document.createElement('div');
        div.id = 'renewModal';
        div.dataset.hour = hour;
        div.setAttribute('style',
            'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(15,23,42,0.6);' +
            'z-index:99999;display:flex;align-items:center;justify-content:center;' +
            'padding:20px;'
        );
        div.innerHTML =
            '<div style="background:#fff;border-radius:12px;box-shadow:0 16px 48px rgba(0,0,0,0.25);' +
            'padding:32px;text-align:center;max-width:380px;width:100%">' +
            '<i class="bi bi-clock-history" style="font-size:48px;color:#f59e0b;display:block;margin-bottom:12px"></i>' +
            '<h5 class="fw-bold mb-2" style="color:#1e2130">续签确认 — 已在线 ' + label + '</h5>' +
            '<p class="text-muted small mb-3">请确认你仍在实验室，' + Math.round(GRACE_SEC / 60) + ' 分钟内不响应将自动签退。</p>' +
            '<div id="renewCD" style="font-size:48px;font-weight:700;color:#ef4444;' +
            'font-variant-numeric:tabular-nums;margin-bottom:16px">' + Math.floor(countdownSec / 60) + ':' +
            (countdownSec % 60).toString().padStart(2, '0') + '</div>' +
            '<div class="d-flex gap-2 justify-content-center">' +
            '<button class="btn btn-primary" onclick="LabRenew.confirm()"><i class="bi bi-hand-thumbs-up"></i> 我在实验室</button>' +
            '<button class="btn btn-outline-danger" onclick="LabRenew.signout()"><i class="bi bi-box-arrow-right"></i> 签退</button></div></div>';
        document.body.appendChild(div);
    }

    function autoSignout() {
        stopBeep();
        removeModal();
        fetch('/lab/checkin/auto-signout', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function() {
            localStorage.removeItem(STORAGE_TS);
            localStorage.removeItem(STORAGE_ACK);
            window.location.href = window.location.href.split('?')[0] + '?_=' + Date.now();
        })
        .catch(function() {
            localStorage.removeItem(STORAGE_TS);
            localStorage.removeItem(STORAGE_ACK);
            window.location.reload();
        });
    }

    // ---------- 主循环 ----------
    function tick() {
        var ts = getSigninTs();
        if (!ts) return;
        var elapsedMin = Math.floor((Date.now() - ts) / 60000);

        // 签到页面上的持续显示更新
        var durEl = document.getElementById('signinDuration');
        var afkEl = document.getElementById('afkCountdown');
        var panelEl = document.getElementById('countdownPanel');
        if (panelEl) panelEl.style.display = '';
        if (durEl) durEl.textContent = fmtDur(elapsedMin);

        // 硬限制
        if (elapsedMin >= HARD_LIMIT_MIN) { autoSignout(); return; }

        // 倒计时中
        if (countdownSec > 0) {
            // 从 localStorage 读 ack，如果该续签点已被确认则关弹窗
            var ack = readAck();
            if (activeRenewIdx >= 0) {
                var ch = RENEW_POINTS[activeRenewIdx];
                if (ack[ackKey(ch)]) { removeModal(); return; }
            }
            countdownSec--;
            var cdEl = document.getElementById('renewCD');
            if (cdEl) {
                var m = Math.floor(countdownSec / 60), s = countdownSec % 60;
                cdEl.textContent = m + ':' + s.toString().padStart(2, '0');
            }
            if (countdownSec <= 0) { removeModal(); autoSignout(); }
            return;
        }

        // 检查所有续签点（从 localStorage 读 ack，不依赖内存）
        var ack = readAck();
        for (var i = 0; i < RENEW_POINTS.length; i++) {
            var h = RENEW_POINTS[i];
            if (elapsedMin >= h * 60 && !ack[ackKey(h)]) {
                showModal(h);
                activeRenewIdx = i;   // 放在 showModal() 之后，避免 removeModal() 覆盖
                return;
            }
        }

        // 显示下一个检查点倒计时
        if (afkEl && countdownSec === 0) {
            var next = HARD_LIMIT_MIN;
            for (var j = 0; j < RENEW_POINTS.length; j++) {
                if (elapsedMin < RENEW_POINTS[j] * 60) { next = RENEW_POINTS[j] * 60; break; }
            }
            var remain = Math.max(0, next - elapsedMin);
            afkEl.textContent = fmtDur(remain);
            afkEl.style.color = remain <= 30 ? '#ef4444' : '#f59e0b';
        }
    }

    // 监听其他标签页的签到退出
    window.addEventListener('storage', function(e) {
        if (e.key === STORAGE_TS && e.newValue === null) { removeModal(); }
    });

    // 与服务端状态同步：定期检查（每30秒）
    var serverCheckTick = 0;
    function checkServerStatus() {
        var ts = getSigninTs();
        if (!ts) return;
        fetch('/lab/checkin/status', { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (!d.checked_in) {
                localStorage.removeItem(STORAGE_TS);
                localStorage.removeItem(STORAGE_ACK);
                removeModal();
                window.location.reload();
            }
        })
        .catch(function() {});
    }

    // 暴露接口
    window.LabRenew = {
        setSignInTs: function(t) { localStorage.setItem(STORAGE_TS, t); },
        confirm: function() {
            stopBeep();
            var modal = document.getElementById('renewModal');
            var hour = modal ? parseFloat(modal.dataset.hour) : null;
            if (!hour && activeRenewIdx >= 0) {
                hour = RENEW_POINTS[activeRenewIdx];
            }
            removeModal();
            if (hour) {
                var key = ackKey(hour);
                var a = readAck();
                a[key] = true;
                writeAck(a);
                fetch('/lab/checkin/renew', { method: 'POST', cache: 'no-store' }).catch(function() {});
            }
            LabToast.show('已确认在线，续签成功。', 'success', 3000);
        },
        signout: function() { stopBeep(); autoSignout(); },
        tick: function() {
            tick();
            serverCheckTick++;
            if (serverCheckTick >= 30) { serverCheckTick = 0; checkServerStatus(); }
        }
    };

    setInterval(function() { window.LabRenew.tick(); }, 1000);
    window.LabRenew.tick();
    setTimeout(checkServerStatus, 1000);
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
    setInterval(poll, 10000);
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
            setInterval(poll, 15000);
        }
    }).catch(function() {
        // Even if init fails, start polling
        if (!started) {
            started = true;
            setInterval(poll, 15000);
        }
    });
})();
