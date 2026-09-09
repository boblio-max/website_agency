// ONB Automotive Repair — interactions
(function () {
  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  // Sticky header shadow
  var header = document.getElementById('header');
  function onScroll() {
    if (!header) return;
    header.classList.toggle('scrolled', window.scrollY > 8);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // Mobile nav
  var btn = document.getElementById('menuBtn');
  var nav = document.getElementById('nav');
  if (btn && nav) {
    btn.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      btn.textContent = open ? '✕' : '☰';
    });
    nav.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        nav.classList.remove('open');
        btn.textContent = '☰';
        btn.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // Reveal on scroll
  var els = document.querySelectorAll('.card, .panel, .quote-card, .faq details, .map-wrap');
  els.forEach(function (el) { el.classList.add('reveal'); });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  } else {
    els.forEach(function (el) { el.classList.add('visible'); });
  }

  // Service pre-select from card links
  var serviceSelect = document.querySelector('select[name="service"]');
  document.querySelectorAll('[data-service]').forEach(function (link) {
    link.addEventListener('click', function () {
      var val = link.getAttribute('data-service');
      if (serviceSelect) {
        Array.prototype.forEach.call(serviceSelect.options, function (opt) {
          if (opt.text === val || opt.value === val) serviceSelect.value = opt.value || opt.text;
        });
        // fallback: set by text match
        for (var i = 0; i < serviceSelect.options.length; i++) {
          if (serviceSelect.options[i].text === val) serviceSelect.selectedIndex = i;
        }
      }
    });
  });

  // Quote form: validate + success state (demo, no backend)
  var form = document.getElementById('quoteForm');
  var success = document.getElementById('formSuccess');
  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var name = form.elements['name'];
      var phone = form.elements['phone'];
      var vehicle = form.elements['vehicle'];
      var service = form.elements['service'];
      var valid = true;
      [name, phone, vehicle, service].forEach(function (f) {
        if (!f) return;
        var bad = !f.value || !f.value.trim();
        f.style.borderColor = bad ? '#d92d20' : '';
        if (bad) valid = false;
      });
      if (phone && phone.value) {
        var digits = phone.value.replace(/\D/g, '');
        if (digits.length < 10) { phone.style.borderColor = '#d92d20'; valid = false; }
      }
      if (!valid) {
        var firstBad = form.querySelector('[style*="d92d20"]');
        if (firstBad) firstBad.focus();
        return;
      }
      var btnSubmit = form.querySelector('button[type="submit"]');
      if (btnSubmit) { btnSubmit.disabled = true; btnSubmit.textContent = 'Sending…'; }
      setTimeout(function () {
        if (success) success.hidden = false;
        if (btnSubmit) { btnSubmit.disabled = false; btnSubmit.textContent = 'Request My Free Estimate'; }
        form.reset();
        if (success) success.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 700);
    });
    // clear error coloring on input
    form.querySelectorAll('input,select,textarea').forEach(function (f) {
      f.addEventListener('input', function () { f.style.borderColor = ''; });
    });
  }

  // Single-open FAQ (allow first open, close others)
  var faq = document.getElementById('faqList');
  if (faq) {
    faq.querySelectorAll('details').forEach(function (d) {
      d.addEventListener('toggle', function () {
        if (d.open) {
          faq.querySelectorAll('details').forEach(function (other) {
            if (other !== d) other.open = false;
          });
        }
      });
    });
  }
})();
