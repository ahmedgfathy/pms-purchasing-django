(function () {
    'use strict';

    var accels = {};
    document.querySelectorAll('[data-accel]').forEach(function (el) {
        var key = (el.getAttribute('data-accel') || '').trim().toLowerCase();
        if (key) accels[key] = el;
    });

    function flash(el) {
        el.classList.add('flash');
        setTimeout(function () { el.classList.remove('flash'); }, 900);
    }

    function flashTarget(t) {
        if (!t) return;
        t.classList.add('target-flash');
        setTimeout(function () { t.classList.remove('target-flash'); }, 900);
    }

    document.addEventListener('keydown', function (e) {
        if (!e.ctrlKey || !e.shiftKey || e.altKey || e.metaKey) return;
        var el = accels[e.key.toLowerCase()];
        if (!el) return;
        e.preventDefault();

        var target = el.getAttribute('data-target');
        var t = target ? document.querySelector(target) : null;
        if (!t) t = el;

        if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT') {
            t.focus();
            if (t.select) t.select();
        } else if (t.tagName === 'A' || t.tagName === 'BUTTON') {
            t.click();
        } else {
            t.focus();
        }

        flash(el);
        flashTarget(t);
    });

    // Clickable table rows -> detail view
    document.querySelectorAll('table.data-clickable tbody tr[data-href]').forEach(function (tr) {
        tr.addEventListener('click', function (e) {
            if (e.target.closest('a, button')) return;
            window.location.href = tr.getAttribute('data-href');
        });
    });

    // Collapsible sidebar groups
    document.querySelectorAll('.nav-group').forEach(function (group) {
        var key = group.id;
        var saved = null;
        try { saved = localStorage.getItem(key); } catch (e) { /* ignore */ }
        if (saved === '0') group.classList.remove('open');

        var label = group.querySelector('.nav-group-label');
        if (!label) return;
        label.addEventListener('click', function () {
            var open = group.classList.toggle('open');
            try { localStorage.setItem(key, open ? '1' : '0'); } catch (e) { /* ignore */ }
        });
    });

    // Notification bell dropdown
    function setupNotif() {
        var bell = document.getElementById('btn-notif');
        var panel = document.getElementById('notif-panel');
        if (!bell || !panel) return;
        bell.addEventListener('click', function (e) {
            e.stopPropagation();
            e.preventDefault();
            panel.classList.toggle('open');
        });
        document.addEventListener('click', function (e) {
            if (!panel.classList.contains('open')) return;
            if (!e.target.closest('#notif-wrap')) panel.classList.remove('open');
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') panel.classList.remove('open');
        });
    }
    setupNotif();
})();