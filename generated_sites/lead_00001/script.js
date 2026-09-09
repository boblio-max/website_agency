// Mobile nav
const toggle = document.querySelector('.nav-toggle');
const links = document.querySelector('.nav-links');
if (toggle && links) {
  toggle.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  links.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    links.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }));
}

// Smooth scroll for anchor links (with header offset feel)
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const id = a.getAttribute('href');
    if (id.length < 2) return;
    const t = document.querySelector(id);
    if (t) {
      e.preventDefault();
      t.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// Menu tabs
const tabs = document.querySelectorAll('.tab');
tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    tabs.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    const name = tab.dataset.tab;
    document.querySelectorAll('.tab-panel').forEach(p => {
      const show = p.id === 'panel-' + name;
      p.classList.toggle('active', show);
      if (show) p.removeAttribute('hidden'); else p.setAttribute('hidden', '');
    });
  });
});

// Review slider (auto + dots)
const reviews = Array.from(document.querySelectorAll('.review'));
const dots = Array.from(document.querySelectorAll('.dot'));
let idx = 0, timer = null;
function show(n) {
  idx = (n + reviews.length) % reviews.length;
  reviews.forEach((r, i) => r.classList.toggle('active', i === idx));
  dots.forEach((d, i) => d.classList.toggle('active', i === idx));
}
dots.forEach((d, i) => d.addEventListener('click', () => { show(i); restart(); }));
function restart() { if (timer) clearInterval(timer); timer = setInterval(() => show(idx + 1), 5000); }
if (reviews.length > 1) restart();

// Open-now status (simple heuristic, matches posted hours)
(function openStatus() {
  const el = document.getElementById('openStatus');
  if (!el) return;
  const d = new Date();
  const day = d.getDay(); // 0 Sun
  const h = d.getHours() + d.getMinutes() / 60;
  let open = false, closeH = 22;
  if (day === 0) { open = h >= 12 && h < 21; closeH = 21; }
  else if (day === 5 || day === 6) { open = h >= 11 && h < 22; closeH = 22; }
  else { open = h >= 11 && h < 21.5; closeH = 21.5; }
  if (open) {
    const hr = Math.floor(closeH);
    const min = closeH % 1 ? ':30' : '';
    const suffix = hr >= 12 ? 'PM' : 'AM';
    el.textContent = 'Open Now · Till ' + (hr > 12 ? hr - 12 : hr) + min + ' ' + suffix;
  } else {
    el.textContent = 'Currently Closed · Opens at 11 AM';
  }
})();

// Callback form
const form = document.getElementById('quote-form');
if (form) {
  form.addEventListener('submit', e => {
    e.preventDefault();
    const note = form.querySelector('.form-note');
    const name = form.name.value.trim();
    const phone = form.phone.value.trim();
    const msg = form.message.value.trim();
    if (!name || !phone || !msg) { note.textContent = 'Please fill in name, phone and message.'; return; }
    if (!/^[+()\-.\s\d]{7,}$/.test(phone)) { note.textContent = 'Please enter a valid phone number.'; return; }
    note.textContent = 'Thanks ' + name.split(' ')[0] + '! We\u2019ll call you back shortly at ' + phone + '. For faster service call (425) 286-6608.';
    form.reset();
  });
}

// Footer year + scroll reveal
const y = document.getElementById('year');
if (y) y.textContent = new Date().getFullYear();

const io = new IntersectionObserver(entries => {
  entries.forEach(en => { if (en.isIntersecting) en.target.classList.add('visible'); });
}, { threshold: 0.12 });
document.querySelectorAll('.card, .menu-list li, .about-card, .review.active').forEach(el => {
  el.classList.add('reveal');
  io.observe(el);
});
