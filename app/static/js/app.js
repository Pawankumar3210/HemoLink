/* HemoLink progressive enhancements. Every feature also works without JavaScript. */
(function () {
  "use strict";

  var motion = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Subtle sticky header state.
  var siteHeader = document.querySelector(".site-header");
  if (siteHeader) {
    var onScroll = function () { siteHeader.classList.toggle("is-scrolled", window.scrollY > 8); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // Reveal elements on scroll.
  var revealSelector = [
    ".hero-copy", ".hero-visual", ".page-hero .container", ".section-head",
    ".stat-card", ".card", ".donor-card", ".group-card", ".feature-grid li",
    ".steps li", ".notice", ".faq", ".live-stats > div", ".table-wrap",
    ".empty-state", ".profile-summary", ".meta-list", ".item-list > li",
    ".filter-form", ".results-title", ".pagination", ".cta-inner",
    ".footer-grid > div", ".footer-grid > nav", ".auth-links", ".choice-grid > *",
    ".error-page .container"
  ].join(", ");
  if (motion && "IntersectionObserver" in window) {
    var seen = new Set();
    document.querySelectorAll(revealSelector).forEach(function (el) {
      if (seen.has(el) || el.closest(".flash-stack, .dialog, .site-header, .sidebar, .nav-backdrop, .reveal")) { return; }
      seen.add(el);
      el.classList.add("reveal");
      var parent = el.parentElement;
      var stagger = 0;
      if (parent) {
        var siblings = Array.prototype.filter.call(parent.children, function (c) { return c.matches && c.matches(revealSelector); });
        var idx = siblings.indexOf(el);
        if (idx > -1 && siblings.length > 1) { stagger = Math.min(idx, 8) * 70; }
      }
      el.style.setProperty("--reveal-delay", stagger + "ms");
    });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: "0px 0px -30px 0px" });
    document.querySelectorAll(".reveal").forEach(function (el) { observer.observe(el); });
  }

  // Mobile site navigation and app sidebar toggles.
  function wireToggle(buttonAttr, targetSelector, overlay) {
    var button = document.querySelector("[" + buttonAttr + "]");
    var target = document.querySelector(targetSelector);
    if (!button || !target) { return; }
    var backdrop = document.querySelector("[data-nav-backdrop]");
    var content = document.querySelector(".app-content");
    var narrow = window.matchMedia("(max-width: 860px)");
    function setOpen(open) {
      target.classList.toggle("is-open", open);
      button.setAttribute("aria-expanded", open ? "true" : "false");
      button.setAttribute("aria-label", button.getAttribute(open ? "data-close-label" : "data-open-label") || button.getAttribute("aria-label"));
      if (backdrop && overlay) { backdrop.classList.toggle("is-visible", open); }
      if (content && overlay && narrow.matches) { content.inert = open; }
    }
    button.addEventListener("click", function () {
      setOpen(!target.classList.contains("is-open"));
    });
    if (backdrop && overlay) {
      backdrop.addEventListener("click", function () {
        setOpen(false);
        button.focus();
      });
    }
    target.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () { setOpen(false); });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && target.classList.contains("is-open")) {
        setOpen(false);
        button.focus();
      }
    });
  }
  wireToggle("data-nav-toggle", "#site-nav", false);
  wireToggle("data-sidebar-toggle", "#sidebar", true);

  // Click/tap press feedback and ripple.
  function addRipple(target, event) {
    if (!motion || !target || target.disabled || target.classList.contains("no-ripple")) { return; }
    var rect = target.getBoundingClientRect();
    var size = Math.max(rect.width, rect.height) * 1.8;
    var ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.width = ripple.style.height = size + "px";
    ripple.style.left = ((event.clientX || (rect.left + rect.width / 2)) - rect.left - size / 2) + "px";
    ripple.style.top = ((event.clientY || (rect.top + rect.height / 2)) - rect.top - size / 2) + "px";
    target.appendChild(ripple);
    ripple.addEventListener("animationend", function () { ripple.remove(); });
  }
  document.addEventListener("pointerdown", function (event) {
    var target = event.target.closest(".btn, .group-card, .choice-card, .donor-card, .stat-card, .side-link, .nav-links a, .page-link, .tabs a, .notice, .alert-close");
    if (target && !target.disabled) {
      target.classList.add("is-pressed");
      var cs = window.getComputedStyle(target);
      if (cs.position === "static") { target.style.position = "relative"; target.dataset.ripplePos = "1"; }
      if (cs.overflow !== "hidden") { target.style.overflow = "hidden"; target.dataset.rippleOv = "1"; }
      addRipple(target, event);
    }
  });
  ["pointerup", "pointerleave", "pointercancel"].forEach(function (type) {
    document.addEventListener(type, function (event) {
      document.querySelectorAll(".is-pressed").forEach(function (target) { target.classList.remove("is-pressed"); });
    });
  });

  // Dismissible alerts.
  document.addEventListener("click", function (event) {
    var close = event.target.closest("[data-dismiss]");
    if (close) {
      var alert = close.closest(".alert");
      if (!alert) { return; }
      var stack = alert.closest(".flash-stack");
      var removeAlert = function () {
        alert.remove();
        var next = stack && stack.querySelector(".alert-close");
        if (next) {
          next.focus();
        } else {
          var main = document.getElementById("main");
          if (main) { main.setAttribute("tabindex", "-1"); main.focus(); }
        }
      };
      if (motion) {
        alert.style.transition = "opacity 180ms ease, transform 180ms ease, max-height 220ms ease, margin 220ms ease, padding 220ms ease";
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-6px)";
        alert.style.maxHeight = alert.offsetHeight + "px";
        requestAnimationFrame(function () {
          alert.style.maxHeight = "0";
          alert.style.marginBottom = "0";
          alert.style.paddingTop = "0";
          alert.style.paddingBottom = "0";
          alert.style.overflow = "hidden";
        });
        setTimeout(removeAlert, 220);
      } else {
        removeAlert();
      }
    }
  });

  // Route-aware page transitions.
  if (motion) {
    document.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) { return; }
      var a = event.target.closest("a[href]");
      if (!a) { return; }
      if (a.target && a.target !== "_self") { return; }
      if (a.hasAttribute("download")) { return; }
      var href = a.getAttribute("href") || "";
      if (href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) { return; }
      if (a.closest("[data-confirm]")) { return; }
      var url;
      try { url = new URL(a.href, window.location.href); } catch (e) { return; }
      if (url.origin !== window.location.origin) { return; }
      if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) { return; }
      event.preventDefault();
      a.classList.add("is-navigating");
      document.body.classList.add("is-leaving");
      setTimeout(function () { window.location.href = url.href; }, 170);
    });
    window.addEventListener("pageshow", function () {
      document.body.classList.remove("is-leaving");
      document.querySelectorAll(".is-navigating").forEach(function (el) { el.classList.remove("is-navigating"); });
    });
  }

  // Show/hide password.
  document.querySelectorAll("[data-toggle-password]").forEach(function (box) {
    box.addEventListener("change", function () {
      var input = document.getElementById(box.getAttribute("data-toggle-password"));
      if (input) { input.type = box.checked ? "text" : "password"; }
    });
  });

  // Confirmation dialog for buttons with data-confirm.
  var dialog = document.getElementById("confirm-dialog");
  var pending = null;
  if (dialog && typeof dialog.showModal === "function") {
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-confirm]");
      if (!button || button.dataset.confirmed === "yes") { return; }
      event.preventDefault();
      pending = button;
      document.getElementById("confirm-message").textContent = button.getAttribute("data-confirm");
      dialog.showModal();
    });
    dialog.addEventListener("close", function () {
      if (dialog.returnValue === "ok" && pending) {
        var button = pending;
        button.dataset.confirmed = "yes";
        if (button.form && typeof button.form.requestSubmit === "function") {
          button.form.requestSubmit(button);
        } else {
          button.click();
        }
      }
      pending = null;
      dialog.returnValue = "";
    });
  } else {
    // Fallback for very old browsers: native confirm().
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-confirm]");
      if (button && !window.confirm(button.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  }

  // Loading state on submit, to prevent double submissions.
  document.querySelectorAll("form[data-loading-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (event.defaultPrevented) { return; }
      var submit = event.submitter || form.querySelector("button[type=submit][data-loading-text]");
      if (!submit || submit.classList.contains("is-loading") || !submit.hasAttribute("data-loading-text")) { return; }
      var spinner = document.createElement("span");
      spinner.className = "spinner";
      spinner.setAttribute("aria-hidden", "true");
      submit.classList.add("is-loading");
      submit.disabled = true;
      submit.replaceChildren(spinner, document.createTextNode(" " + submit.getAttribute("data-loading-text")));
    });
  });

  // Donor search: loading state while results reload.
  var searchForm = document.querySelector("[data-search-form]");
  var results = document.querySelector("[data-results]");
  if (searchForm && results) {
    function clearLoading() {
      results.classList.remove("is-loading");
      results.removeAttribute("aria-busy");
    }
    searchForm.addEventListener("submit", function () {
      results.classList.add("is-loading");
      results.setAttribute("aria-busy", "true");
    });
    window.addEventListener("pageshow", function (event) {
      if (event.persisted) { clearLoading(); }
    });
  }

  // Client-side password confirmation hint (server-side validation is authoritative).
  document.querySelectorAll("form[data-password-match]").forEach(function (form) {
    var first = form.querySelector("input[name=password], input[name=new_password]");
    var second = form.querySelector("input[name=confirm_password]");
    if (!first || !second) { return; }
    function check() {
      if (second.value && first.value !== second.value) {
        second.setCustomValidity("The passwords do not match.");
      } else {
        second.setCustomValidity("");
      }
    }
    first.addEventListener("input", check);
    second.addEventListener("input", check);
  });
})();
