/* فيه شفاء - لوحة التحكم: مؤشرات، رسوم، تصدير Excel، الطلبات مجمعة حسب الزبون */
(function () {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const GREEN = ['#16A34A', '#4AAA6F', '#7EC79B', '#0E5E2D', '#229D4E', '#B8E0C8', '#12843D', '#0B4523'];
  let charts = [];
  let allLatest = [];

  function mad(n) {
    return Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' د.م.';
  }

  function monthsBack(k) {
    const out = [];
    const d = new Date();
    for (let i = 0; i < k; i++) {
      const dt = new Date(d.getFullYear(), d.getMonth() - i, 1);
      out.push(dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0'));
    }
    return out.reverse();
  }

  function fillMonthSelector(revenueByMonth) {
    const sel = $('#monthSel');
    const known = (revenueByMonth || []).map((r) => r.ym);
    const all = new Set([...monthsBack(6), ...known]);
    const ordered = [...all].sort();
    sel.innerHTML = '';
    ordered.forEach((ym) => {
      const opt = document.createElement('option');
      opt.value = ym;
      opt.textContent = ym;
      sel.appendChild(opt);
    });
    const now = new Date();
    const cur = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
    if ([...all].includes(cur)) sel.value = cur;
  }

  async function load() {
    let data;
    try {
      const res = await AdminAuth.api('/api/v1/sales/summary', { cache: 'no-store' });
      if (!res.ok) throw new Error('api');
      data = await res.json();
    } catch (e) {
      if (e.status === 401) return;
      $('#kRevenue').textContent = '—';
      ['chartRevenue', 'chartTop', 'chartCat'].forEach((id) => chartEmpty(id, 'تعذر الاتصال بالخادم'));
      $('#ordersTable').innerHTML = '<div class="empty-chart">تعذر الاتصال بالخادم.</div>';
      return;
    }

    const totals = data.totals || {};
    const month = data.month || {};
    const byMonth = data.revenueByMonth || [];
    const top = data.topSellers || [];
    const byCat = data.byCategory || [];

    $('#kRevenue').textContent = mad(totals.revenue);
    $('#kOrders').textContent = totals.orders;
    $('#kUnits').textContent = totals.units;
    $('#kMonthRevenue').textContent = mad(month.revenue);
    $('#kMonthSub').textContent = month.orders + ' طلب · ' + month.units + ' وحدة (' + month.label + ')';
    $('#kOrdersSub').textContent = month.orders + ' هذا الشهر';
    $('#kUnitsSub').textContent = totals.units + ' الإجمالي';

    fillMonthSelector(byMonth);
    renderCharts(byMonth, top, byCat);
    allLatest = data.latest || [];
    initOrdersFilters();
    renderOrdersFiltered();
  }

  function chartEmpty(id, msg) {
    const el = document.getElementById(id);
    if (el) { el.closest('.chart-box').innerHTML = '<div class="empty-chart">' + msg + '</div>'; }
  }

  function renderCharts(byMonth, top, byCat) {
    charts.forEach((c) => c.destroy());
    charts = [];

    const labels = byMonth.map((r) => r.ym);
    const revenue = byMonth.map((r) => r.revenue);

    const make = (id, conf) => {
      const ctx = document.getElementById(id);
      if (!ctx) return;
      const parent = ctx.closest('.chart-box');
      if (!conf.labels.length || !conf.labels.some((l, i) => conf.data[i])) {
        parent.innerHTML = '<div class="empty-chart">لا توجد مبيعات حالياً.</div>';
        return;
      }
      ctx.getContext('2d');
      charts.push(new Chart(ctx, {
        type: conf.type,
        data: {
          labels: conf.labels,
          datasets: [{
            label: conf.datasetLabel || '',
            data: conf.data,
            backgroundColor: conf.colors || GREEN,
            borderColor: conf.border || conf.colors || GREEN,
            borderWidth: conf.borderWidth !== undefined ? conf.borderWidth : 1,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: conf.indexAxis || 'x',
          plugins: { legend: { display: !!conf.legend } },
          scales: {
            x: { grid: { display: false }, ticks: { font: { family: 'Cairo' } } },
            y: { beginAtZero: true, grid: { color: '#EEF4EF' }, ticks: { font: { family: 'Cairo' } } },
          },
        },
      }));
    };

    make('chartRevenue', {
      type: 'bar',
      labels: labels,
      data: revenue,
      colors: '#16A34A',
      datasetLabel: 'الإيرادات (د.م.)',
    });

    make('chartTop', {
      type: 'bar',
      indexAxis: 'y',
      labels: top.map((r) => r.name),
      data: top.map((r) => r.revenue),
      colors: '#0E5E2D',
      datasetLabel: 'الإيرادات (د.م.)',
    });

    const catLabels = byCat.map((c) => catLabel(c.label));
    make('chartCat', {
      type: 'doughnut',
      labels: catLabels,
      data: byCat.map((c) => c.revenue),
      colors: GREEN,
      legend: true,
      borderWidth: 2,
      datasetLabel: 'الإيرادات (د.م.)',
    });
  }

  const CAT_NAMES = { amlou: 'أملو', miels: 'العسل', huiles: 'الزيوت', cosmetiques: 'عطور', autres: 'منتوجات أخرى', recettes: 'وصفات فيه شفاء', packs: 'باقات فيه شفاء', thes: 'الشاي' };
  const catLabel = (slug) => CAT_NAMES[slug] || slug || '—';

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  // ---- Orders: grouped by user, date filter, confined scroll ----
  function currentMonthBounds() {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth();
    const pad = (n) => String(n).padStart(2,'0');
    const first = y + '-' + pad(m+1) + '-01';
    const lastDay = new Date(y, m+1, 0).getDate();
    const last = y + '-' + pad(m+1) + '-' + pad(lastDay);
    return { from: first, to: last };
  }

  function initOrdersFilters() {
    const from = $('#ordersFrom');
    const to = $('#ordersTo');
    if (!from || !to) return;
    const bounds = currentMonthBounds();
    from.value = bounds.from;
    to.value = bounds.to;
    $('#ordersFilterBtn').addEventListener('click', renderOrdersFiltered);
    $('#ordersResetBtn').addEventListener('click', function () {
      const b = currentMonthBounds();
      from.value = b.from;
      to.value = b.to;
      renderOrdersFiltered();
    });
    from.addEventListener('change', renderOrdersFiltered);
    to.addEventListener('change', renderOrdersFiltered);
  }

  function renderOrdersFiltered() {
    const fromVal = $('#ordersFrom') ? $('#ordersFrom').value : '';
    const toVal = $('#ordersTo') ? $('#ordersTo').value : '';
    let filtered = allLatest.slice();
    // only current month by default if inputs empty -> use current month bounds
    if (fromVal || toVal) {
      filtered = filtered.filter((r) => {
        const d = String(r.created || '').slice(0,10);
        if (fromVal && d < fromVal) return false;
        if (toVal && d > toVal) return false;
        return true;
      });
    } else {
      // fallback to current month
      const m = new Date().toISOString().slice(0,7);
      filtered = filtered.filter((r) => String(r.created||'').slice(0,7) === m);
    }
    renderOrdersGrouped(filtered);
  }

  function renderOrdersGrouped(items) {
    const box = $('#ordersTable');
    const summary = $('#ordersSummary');
    if (!items.length) {
      box.innerHTML = '<div class="empty-chart">لا توجد طلبات في هذه الفترة.</div>';
      if (summary) summary.textContent = '0 طلب';
      return;
    }
    // group by buyer+phone
    const groups = {};
    items.forEach((r) => {
      const key = (r.buyer || 'مجهول') + '|' + (r.phone || '');
      if (!groups[key]) groups[key] = { buyer: r.buyer || 'مجهول', phone: r.phone || '—', items: [], total: 0, earliest: r.created };
      groups[key].items.push(r);
      groups[key].total += (Number(r.price)||0) * (Number(r.qty)||0);
      if (r.created && r.created < groups[key].earliest) groups[key].earliest = r.created;
    });
    const grouped = Object.values(groups).sort((a,b) => String(b.earliest).localeCompare(String(a.earliest)));
    const html = grouped.map((g) => {
      const date = String(g.earliest||'').slice(0,10);
      const rows = g.items.map((r) =>
        '<tr>' +
        '  <td>' + esc(r.product_name) + '</td>' +
        '  <td><span class="cat-tag">' + esc(catLabel(r.cat)) + '</span></td>' +
        '  <td>' + mad(r.price) + ' × ' + r.qty + '</td>' +
        '  <td><b>' + mad((Number(r.price)||0)*(Number(r.qty)||0)) + '</b></td>' +
        '</tr>'
      ).join('');
      return (
        '<div class="buyer-group">' +
        '  <div class="buyer-head">' +
        '    <span class="buyer-name">👤 ' + esc(g.buyer) + ' <span class="buyer-phone" dir="ltr">' + esc(g.phone) + '</span></span>' +
        '    <span class="buyer-date">' + esc(date) + '</span>' +
        '    <span class="buyer-total">' + mad(g.total) + '</span>' +
        '  </div>' +
        '  <div class="buyer-items"><table><thead><tr><th>المنتج</th><th>الفئة</th><th>السعر × الكمية</th><th>المجموع</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
        '</div>'
      );
    }).join('');
    box.innerHTML = html;
    if (summary) summary.textContent = grouped.length + ' زبون · ' + items.length + ' عنصر · ' + mad(grouped.reduce((s,g)=>s+g.total,0)) + ' إجمالي';
  }

  async function exportExcel() {
    const month = $('#monthSel').value || '';
    const url = '/api/v1/sales/export' + (month ? '?month=' + encodeURIComponent(month) : '');
    try {
      const res = await AdminAuth.api(url);
      if (!res.ok) throw new Error('api');
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = res.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || 'ventes.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    } catch (e) {
      alert('تعذر إنشاء ملف Excel.');
    }
  }

  function start() {
    $('#btnExport').addEventListener('click', exportExcel);
    const lo = $('#btnLogout');
    if (lo) lo.addEventListener('click', function () { AdminAuth.logout(); });
    load();
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!window.AdminAuth) return;
    AdminAuth.require(start);
  });
})();
