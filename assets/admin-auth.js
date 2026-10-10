/* fihi-chifae admin : shared helpers for the protected pages
   - the session lives in an HttpOnly cookie set by the server (never readable here)
   - api() serializes JSON bodies and sends the user back to the login page on 401
   - toast() gives non-blocking feedback (replaces alert()) */
(function () {
  'use strict';

  var LOGIN = '/admin-login.html';

  function goLogin() {
    var next = window.location.pathname + window.location.search;
    window.location.replace(LOGIN + '?next=' + encodeURIComponent(next));
  }

  function errMsg(data, fallback) {
    var e = data && data.error;
    if (typeof e === 'string') return e;
    if (e && typeof e.message === 'string') return e.message;
    return fallback;
  }

  /* fetch wrapper: plain objects are sent as JSON; resolves to the Response. */
  function api(path, opts) {
    opts = Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opts || {});
    opts.headers = Object.assign({}, opts.headers || {});
    if (opts.body !== undefined && typeof opts.body !== 'string') {
      opts.body = JSON.stringify(opts.body);
      opts.headers['Content-Type'] = 'application/json';
    }
    return fetch(path, opts).then(function (res) {
      if (res.status === 401) {
        goLogin();
        var err = new Error('المصادقة مطلوبة');
        err.status = 401;
        throw err;
      }
      return res;
    });
  }

  /* api() + JSON decoding; throws Error(message) with .status/.payload on failure. */
  function apiJson(path, opts) {
    return api(path, opts).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) {
          var err = new Error(errMsg(data, 'خطأ في الخادم'));
          err.status = res.status;
          err.payload = data;
          throw err;
        }
        return data;
      });
    });
  }

  function require(cb) {
    fetch('/api/v1/admin/session', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error('auth'); return r.json(); })
      .then(function () {
        var loading = document.getElementById('authLoading');
        var main = document.getElementById('mainContent');
        if (loading) loading.hidden = true;
        if (main) main.hidden = false;
        var lo = document.getElementById('btnLogout');
        if (lo) lo.addEventListener('click', logout);
        cb();
      })
      .catch(goLogin);
  }

  function logout() {
    fetch('/api/v1/admin/session', { method: 'DELETE', credentials: 'same-origin' })
      .catch(function () { /* the cookie expires anyway */ })
      .then(function () { window.location.replace(LOGIN); });
  }

  function toast(msg, kind) {
    var box = document.getElementById('adminToasts');
    if (!box) {
      box = document.createElement('div');
      box.id = 'adminToasts';
      box.className = 'admin-toasts';
      box.setAttribute('role', 'status');
      box.setAttribute('aria-live', 'polite');
      document.body.appendChild(box);
    }
    var el = document.createElement('div');
    el.className = 'admin-toast ' + (kind === 'error' ? 'is-error' : 'is-ok');
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(function () { el.classList.add('out'); setTimeout(function () { el.remove(); }, 300); }, kind === 'error' ? 5000 : 3000);
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  /* One money format for the whole admin: 1,234.50 د.م. */
  function mad(n) {
    return Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' د.م.';
  }

  /* Accessible confirmation dialog; resolves to true/false. */
  function confirmDialog(message, okLabel, danger) {
    return new Promise(function (resolve) {
      var ov = document.createElement('div');
      ov.className = 'modal-overlay';
      ov.innerHTML =
        '<div class="modal-card narrow" role="alertdialog" aria-modal="true" aria-labelledby="cfTitle">' +
        '  <div class="modal-head"><h3 id="cfTitle">تأكيد</h3></div>' +
        '  <div class="modal-body"><p class="confirm-text"></p></div>' +
        '  <div class="modal-foot"><div class="modal-actions">' +
        '    <button type="button" class="btn-soft" data-no>إلغاء</button>' +
        '    <button type="button" class="' + (danger ? 'btn-danger' : 'btn-primary') + '" data-yes></button>' +
        '  </div></div>' +
        '</div>';
      ov.querySelector('.confirm-text').textContent = message;
      ov.querySelector('[data-yes]').textContent = okLabel || 'تأكيد';
      if (danger) ov.querySelector('[data-yes]').style.height = '2.6rem';
      function done(v) { document.removeEventListener('keydown', onKey); ov.remove(); resolve(v); }
      function onKey(e) { if (e.key === 'Escape') done(false); }
      ov.addEventListener('click', function (e) { if (e.target === ov) done(false); });
      ov.querySelector('[data-no]').addEventListener('click', function () { done(false); });
      ov.querySelector('[data-yes]').addEventListener('click', function () { done(true); });
      document.addEventListener('keydown', onKey);
      document.body.appendChild(ov);
      ov.querySelector('[data-yes]').focus();
    });
  }

  window.AdminAuth = {
    api: api, apiJson: apiJson, require: require, logout: logout,
    toast: toast, esc: esc, mad: mad, confirm: confirmDialog,
  };
})();
