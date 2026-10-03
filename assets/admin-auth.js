/* fihi-chifae admin : shared authentication
   - manages the session token (sessionStorage)
   - wraps API calls so a 401 triggers the login overlay
   - leaves room for MFA (two-factor) - the flow is wired, MFA is not enabled yet */
(function () {
  'use strict';

  var KEY = 'fifi_admin_token';
  var onSuccess = null;
  var overlay = null;

  function getToken() { try { return sessionStorage.getItem(KEY) || ''; } catch (e) { return ''; } }
  function setToken(t) { try { sessionStorage.setItem(KEY, t); } catch (e) { /* ignore */ } }
  function clearToken() { try { sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ } }
  function $id(id) { return document.getElementById(id); }

  function errMsg(data, fallback) {
    var e = data && data.error;
    if (typeof e === 'string') return e;
    if (e && typeof e.message === 'string') return e.message;
    return fallback;
  }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    opts.headers['X-Token'] = getToken();
    if (opts.body && !opts.headers['Content-Type']) opts.headers['Content-Type'] = 'application/json';
    return fetch(path, opts).then(function (res) {
      if (res.status !== 401) return res;
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (data && data.auth_required) showLogin(onSuccess);
        var err = new Error(errMsg(data, 'المصادقة مطلوبة'));
        err.status = 401;
        throw err;
      });
    });
  }

  function verify() {
    var token = getToken();
    if (!token) return Promise.reject({ status: 401 });
    return fetch('/api/v1/admin/session', { cache: 'no-store', headers: { 'X-Token': token } })
      .then(function (r) {
        if (r.status === 401) { clearToken(); throw { status: 401 }; }
        return r.json();
      });
  }

  function buildOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.className = 'auth-overlay';
    // Enterprise best practice: generic wording, no explicit "admin" disclosure
    overlay.innerHTML =
      '<div class="auth-card">' +
      '  <div class="auth-brand"><img src="assets/logo.jpg" alt="شعار فيه شفاء"><span>فيه <b>شفاء</b></span></div>' +
      '  <h2>المصادقة</h2>' +
      '  <p class="auth-intro">مساحة آمنة — يرجى تسجيل الدخول للمتابعة.</p>' +
      '  <form id="authForm" class="auth-form" novalidate>' +
      '    <div class="auth-field"><label for="authUser">اسم المستخدم</label><input id="authUser" type="text" autocomplete="username" required placeholder="اسم المستخدم"></div>' +
      '    <div class="auth-field"><label for="authPass">كلمة المرور</label><input id="authPass" type="password" autocomplete="current-password" required placeholder="••••••••"></div>' +
      '    <div class="auth-mfa-field" id="authMfaBox" style="display:none">' +
      '      <label for="authMfa">رمز التحقق</label>' +
      '      <input id="authMfa" type="text" inputmode="numeric" autocomplete="one-time-code" placeholder="000000">' +
      '      <span class="auth-note">التحقق بخطوتين سيتم تفعيله قريباً.</span>' +
      '    </div>' +
      '    <button type="submit" class="btn-login">تسجيل الدخول</button>' +
      '    <div class="auth-error" id="authError"></div>' +
      '    <p class="auth-links"><a href="javascript:void(0)" id="forgotLink">نسيت كلمة المرور؟</a></p>' +
      '  </form>' +
      '  <form id="resetForm" class="auth-form" novalidate hidden>' +
      '    <div class="auth-field"><label for="resetEmail">البريد الإلكتروني</label><input id="resetEmail" type="email" autocomplete="email" placeholder="you@example.com" required></div>' +
      '    <button type="submit" class="btn-login">إرسال رابط الاستعادة</button>' +
      '    <div class="auth-error" id="resetError"></div>' +
      '    <p class="auth-links"><a href="javascript:void(0)" id="backLoginLink">← العودة لتسجيل الدخول</a></p>' +
      '  </form>' +
      '  <p class="auth-foot">المصادقة الثنائية (MFA) قريباً.</p>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('#authForm').addEventListener('submit', function (e) { e.preventDefault(); submitLogin(); });
    overlay.querySelector('#resetForm').addEventListener('submit', function (e) { e.preventDefault(); submitReset(); });
    $id('forgotLink').addEventListener('click', function () { toggleReset(true); });
    $id('backLoginLink').addEventListener('click', function () { toggleReset(false); });
    return overlay;
  }

  function toggleReset(show) {
    $id('authForm').hidden = show;
    $id('resetForm').hidden = !show;
    setError('');
    $id('resetError').textContent = '';
    setTimeout(function () {
      var el = show ? $id('resetEmail') : $id('authUser');
      if (el) el.focus();
    }, 30);
  }

  function submitReset() {
    var email = $id('resetEmail').value.trim();
    var box = $id('resetError');
    box.textContent = '';
    if (!email) { box.textContent = 'يرجى إدخال البريد الإلكتروني.'; return; }
    var btn = $id('resetForm').querySelector('button');
    btn.disabled = true;

    fetch('/api/v1/admin/reset/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email }),
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, data: d }; });
    }).then(function (res) {
      var text = 'إذا كان البريد مسجلاً، سيتم إرسال رابط الاستعادة.';
      if (res.ok) {
        toggleReset(false);
        setError(text);
        setTimeout(function () { setError(''); }, 6000);
      } else {
        box.textContent = errMsg(res.data, text);
      }
    }).catch(function () { box.textContent = 'تعذر الاتصال بالخادم.'; })
      .then(function () { btn.disabled = false; });
  }

  function showLogin(fn) {
    onSuccess = fn || onSuccess;
    buildOverlay();
    overlay.style.display = '';
    setTimeout(function () { var u = $id('authUser'); if (u) u.focus(); }, 30);
  }

  function hideLogin() { if (overlay) overlay.style.display = 'none'; }

  function setError(msg) { $id('authError').textContent = msg || ''; }

  function submitLogin() {
    var user = $id('authUser').value.trim();
    var pass = $id('authPass').value;
    var mfaBox = $id('authMfaBox');
    var mfaMode = mfaBox && mfaBox.style.display !== 'none';

    setError('');
    if (!user || !pass) { setError('يرجى إدخال بيانات الاعتماد.'); return; }

    var btn = $id('authForm').querySelector('button');
    btn.disabled = true;

    var route, body;
    if (mfaMode) {
      route = '/api/v1/admin/verify-mfa';
      body = { username: user, code: $id('authMfa').value.trim() };
    } else {
      route = '/api/v1/admin/session';
      body = { username: user, password: pass };
    }

    fetch(route, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, data: d }; });
    }).then(function (res) {
      var d = res.data || {};
      if (!res.ok) { setError(errMsg(d, mfaMode ? 'رمز غير صالح أو MFA غير متاح.' : 'بيانات الاعتماد غير صحيحة.')); }
      else if (d.mfa_required) { mfaBox.style.display = ''; mfaBox.querySelector('input').focus(); setError(errMsg(d, 'أدخل رمز التحقق.')); }
      else if (d.token) {
        setToken(d.token);
        hideLogin();
        if (onSuccess) { var fn = onSuccess; onSuccess = null; fn(); }
      }
    }).catch(function () { setError('تعذر الاتصال بالخادم.'); })
      .then(function () { btn.disabled = false; });
  }

  function logout() {
    var token = getToken();
    try {
      fetch('/api/v1/admin/session', { method: 'DELETE', headers: { 'X-Token': token } });
    } catch (e) { /* offline logout still clears the local session */ }
    clearToken();
    window.location.reload();
  }

  function require(cb) {
    verify().then(function () { cb(); }, function () { showLogin(cb); });
  }

  window.AdminAuth = {
    api: api,
    verify: verify,
    require: require,
    logout: logout,
    getToken: getToken,
  };
})();