// One Repair — mobile nav, smooth scroll, form validation
(function () {
  'use strict';

  // Mobile nav toggle
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

  // Smooth scroll for in-page anchors (respects reduced motion)
  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var id = a.getAttribute('href');
      if (id.length < 2) return;
      var t = document.querySelector(id);
      if (!t) return;
      e.preventDefault();
      if (prefersReduced) {
        t.scrollIntoView();
      } else {
        t.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      t.setAttribute('tabindex', '-1');
      t.focus({ preventScroll: true });
    });
  });

  // Quote / appointment form validation
  var form = document.getElementById('quote-form');
  if (!form) return;
  var note = form.querySelector('.form-note');

  function setNote(msg, kind) {
    note.textContent = msg;
    note.classList.remove('error', 'success');
    if (kind) note.classList.add(kind);
  }

  function markInvalid(el, bad) {
    el.classList.toggle('invalid', !!bad);
    el.setAttribute('aria-invalid', bad ? 'true' : 'false');
    return !bad;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = form.elements['name'];
    var phone = form.elements['phone'];
    var message = form.elements['message'];

    var okName = markInvalid(name, !name.value.trim());
    var digits = (phone.value || '').replace(/\D/g, '');
    var okPhone = markInvalid(phone, digits.length < 7);
    var okMsg = markInvalid(message, !message.value.trim());

    if (!okName || !okPhone || !okMsg) {
      setNote('Please add your name, a valid phone number, and a short message.', 'error');
      ( !okName ? name : !okPhone ? phone : message ).focus();
      return;
    }

    setNote('Thanks, ' + name.value.trim().split(' ')[0] + '! We will call you back shortly at ' + phone.value.trim() + '.', 'success');
    form.reset();
  });

  // Clear invalid state while typing
  form.querySelectorAll('input, textarea').forEach(function (el) {
    el.addEventListener('input', function () {
      el.classList.remove('invalid');
      el.removeAttribute('aria-invalid');
    });
  });

  // Footer year rollover safety (static 2026 in HTML, keep current if newer)
  var yearEl = document.querySelector('.footer-bottom p');
  if (yearEl) {
    var y = new Date().getFullYear();
    if (y !== 2026) yearEl.textContent = yearEl.textContent.replace('2026', String(y));
  }
})();
