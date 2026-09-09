// Superior Automotive Bothell — interactions + validated contact form
(function () {
  "use strict";

  // 1. Mobile nav toggle
  var toggle = document.querySelector(".nav-toggle");
  var links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "✕" : "☰";
    });
    links.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        if (window.innerWidth <= 640) {
          links.classList.remove("open");
          toggle.setAttribute("aria-expanded", "false");
          toggle.textContent = "☰";
        }
      });
    });
  }

  // 2. Smooth scroll for in-page anchors (respects reduced motion)
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      var id = a.getAttribute("href");
      if (!id || id === "#") return;
      var t = document.querySelector(id);
      if (t) {
        e.preventDefault();
        t.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
        if (t.id === "contact" || t.id === "book") {
          var first = document.querySelector('#quote-form input[name="name"]');
          if (first) setTimeout(function () { first.focus({ preventScroll: true }); }, 500);
        }
      }
    });
  });

  // 3. Scroll reveal
  var revealEls = document.querySelectorAll(".cards li, .steps li, .review-grid blockquote, .panel, .faq details");
  revealEls.forEach(function (el) { el.classList.add("reveal"); });
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("visible");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("visible"); });
  }

  // 4. Sticky header shadow
  var header = document.querySelector(".site-header");
  function onScroll() {
    if (!header) return;
    header.style.boxShadow = window.scrollY > 8 ? "0 6px 20px rgba(22,26,34,.12)" : "none";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // 5. Contact / quote form with validation
  var form = document.getElementById("quote-form");
  if (form) {
    var note = form.querySelector(".form-note");
    function setErr(field, bad) {
      if (!field) return;
      if (bad) field.setAttribute("aria-invalid", "true");
      else field.removeAttribute("aria-invalid");
    }
    ["name", "phone", "message", "service"].forEach(function (n) {
      var f = form.elements[n];
      if (f) f.addEventListener("input", function () { setErr(f, false); });
      if (f) f.addEventListener("change", function () { setErr(f, false); });
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var name = form.elements["name"];
      var phone = form.elements["phone"];
      var email = form.elements["email"];
      var vehicle = form.elements["vehicle"];
      var service = form.elements["service"];
      var message = form.elements["message"];
      var consent = form.elements["consent"];

      var errors = [];
      var digits = (phone.value || "").replace(/\D/g, "");

      if (!name.value.trim() || name.value.trim().length < 2) {
        errors.push("Please enter your full name.");
        setErr(name, true);
      }
      if (digits.length < 7) {
        errors.push("Please enter a valid phone number so we can call you back.");
        setErr(phone, true);
      }
      if (email && email.value.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
        errors.push("That email look off — check it or leave it blank.");
        setErr(email, true);
      }
      if (!service.value) {
        errors.push("Please choose the service you need.");
        setErr(service, true);
      }
      if (!message.value.trim() || message.value.trim().length < 10) {
        errors.push("Tell us a little more (10+ characters) so we can prepare your free estimate.");
        setErr(message, true);
      }
      if (consent && !consent.checked) {
        errors.push("Please tick the contact consent box so we may call you back.");
      }

      if (errors.length) {
        note.textContent = errors[0];
        note.className = "form-note err";
        var firstBad = form.querySelector('[aria-invalid="true"]');
        if (firstBad) firstBad.focus();
        return;
      }

      // Success — store locally + show confirmation (no backend required)
      var payload = {
        name: name.value.trim(),
        phone: phone.value.trim(),
        email: (email.value || "").trim(),
        vehicle: (vehicle.value || "").trim(),
        service: service.value,
        message: message.value.trim(),
        at: new Date().toISOString(),
        shop: "Superior Automotive Bothell"
      };
      try {
        var key = "superior-bothell-quote-requests";
        var prev = JSON.parse(localStorage.getItem(key) || "[]");
        prev.push(payload);
        localStorage.setItem(key, JSON.stringify(prev));
      } catch (err) { /* private mode — ignore */ }

      note.textContent = "Thanks, " + payload.name.split(" ")[0] + "! Request received — we will call " +
        payload.phone + " during open hours (Mon–Fri 8 AM–6 PM). Need us sooner? Call (425) 454-5028.";
      note.className = "form-note ok";
      form.reset();
    });
  }

  // 6. Footer year safety (HTML already ships © 2026)
  // 7. FAQ: close others when one opens (accordion feel, first stays open by default)
  var faqs = document.querySelectorAll(".faq details");
  faqs.forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) {
        faqs.forEach(function (o) { if (o !== d) o.removeAttribute("open"); });
      }
    });
  });
})();
