// Safety Auto Repair - Bothell — interactions + form validation
(function () {
  'use strict';

  // Footer year
  var yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  // Mobile nav
  var toggle = document.querySelector('.nav-toggle');
  var links = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    links.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        links.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // Smooth scroll for anchor links (native CSS handles most; JS fallback for older)
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var id = a.getAttribute('href');
      if (id.length > 1) {
        var t = document.querySelector(id);
        if (t) {
          e.preventDefault();
          t.scrollIntoView({ behavior: 'smooth', block: 'start' });
          t.setAttribute('tabindex', '-1');
        }
      }
    });
  });

  // Open-now status (Mon–Fri 8-18, Sat 9-15, Sun closed; America/Los_Angeles approx via local time)
  function updateOpenStatus() {
    var el = document.getElementById('open-status');
    if (!el) return;
    var now = new Date();
    var day = now.getDay(); // 0 Sun
    var mins = now.getHours() * 60 + now.getMinutes();
    var open = false;
    if (day >= 1 && day <= 5) open = mins >= 480 && mins < 1080;
    else if (day === 6) open = mins >= 540 && mins < 900;
    el.textContent = open ? '● Open now — walk-ins welcome' : '● Currently closed — book online and we’ll confirm';
    el.classList.toggle('open', open);
    el.classList.toggle('closed', !open);
  }
  updateOpenStatus();
  setInterval(updateOpenStatus, 60000);

  // FAQ accordion
  document.querySelectorAll('.faq-q').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var ans = btn.nextElementSibling;
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!expanded));
      if (ans) ans.hidden = expanded;
    });
  });

  // Scroll reveal
  var revealEls = document.querySelectorAll('#services .cards li, #reviews blockquote, .visit-card');
  revealEls.forEach(function (el) { el.classList.add('reveal'); });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('visible');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('visible'); });
  }

  // Quote form validation
  var form = document.getElementById('quote-form');
  if (!form) return;
  var note = form.querySelector('.form-note');

  function setNote(msg, ok) {
    note.textContent = msg;
    note.classList.toggle('ok', !!ok);
    note.classList.toggle('err', !ok);
  }

  function markInvalid(field, bad) {
    if (!field) return;
    if (bad) field.setAttribute('aria-invalid', 'true');
    else field.removeAttribute('aria-invalid');
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = form.elements['name'];
    var phone = form.elements['phone'];
    var vehicle = form.elements['vehicle'];
    var service = form.elements['service'];
    var message = form.elements['message'];
    var consent = form.elements['consent'];

    var errors = [];
    var nameOk = name && name.value.trim().length >= 2;
    var phoneDigits = phone ? phone.value.replace(/\D/g, '') : '';
    var phoneOk = phoneDigits.length >= 7 && phoneDigits.length <= 15;
    var serviceOk = service && service.value !== '';
    var msgOk = message && message.value.trim().length >= 10;
    var consentOk = !consent || consent.checked;

    markInvalid(name, !nameOk);
    markInvalid(phone, !phoneOk);
    markInvalid(service, !serviceOk);
    markInvalid(message, !msgOk);

    if (!nameOk) errors.push('your name');
    if (!phoneOk) errors.push('a valid phone number');
    if (!serviceOk) errors.push('a service');
    if (!msgOk) errors.push('a message (10+ characters)');
    if (!consentOk) errors.push('text consent');

    if (errors.length) {
      setNote('Please add ' + errors.join(', ') + '.', false);
      var firstBad = !nameOk ? name : !phoneOk ? phone : !serviceOk ? service : message;
      if (firstBad) firstBad.focus();
      return;
    }

    var svc = service.value;
    var v = vehicle && vehicle.value.trim() ? ' (' + vehicle.value.trim() + ')' : '';
    setNote('Thanks ' + name.value.trim().split(' ')[0] + '! Your ' + svc + v + ' request was received. We’ll call ' + phone.value.trim() + ' within 1 business hour.', true);
    form.reset();
  });

  // Live-clear invalid state
  form.querySelectorAll('input, select, textarea').forEach(function (f) {
    f.addEventListener('input', function () { markInvalid(f, false); });
    f.addEventListener('change', function () { markInvalid(f, false); });
  });
})();
