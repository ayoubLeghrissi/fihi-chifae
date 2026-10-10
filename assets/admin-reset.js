/* fihi-chifae admin password reset (single-use token from the e-mailed link). */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var msg = $('#msg');
  function show(text, ok) { msg.textContent = text; msg.className = ok ? 'auth-error ok' : 'auth-error'; }

  var token = new URLSearchParams(window.location.search).get('token') || '';
  if (!token.trim()) {
    show('رابط غير صالح: لا يوجد رمز استعادة.');
    $('#resetForm').hidden = true;
    return;
  }

  $('#resetForm').addEventListener('submit', function (e) {
    e.preventDefault();
    var pw1 = $('#pw1').value;
    var pw2 = $('#pw2').value;
    if (pw1.length < 8) { show('يجب أن تتكون كلمة المرور من 8 أحرف على الأقل.'); return; }
    if (pw1 !== pw2) { show('كلمتا المرور غير متطابقتين.'); return; }
    show('جاري التحديث…', true);
    fetch('/api/v1/admin/reset/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token, password: pw1 }),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, data: d }; });
    }).then(function (res) {
      if (!res.ok) {
        var e = res.data.error;
        show((e && e.message) || 'خطأ في الخادم.');
        return;
      }
      $('#resetForm').hidden = true;
      show('');
      $('#okBox').hidden = false;
    }).catch(function () { show('تعذر الاتصال بالخادم.'); });
  });
})();
