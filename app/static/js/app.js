/* HemoLink progressive enhancements. Every feature also works without JavaScript. */
(function () {
  "use strict";

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

  // Dismissible alerts.
  document.addEventListener("click", function (event) {
    var close = event.target.closest("[data-dismiss]");
    if (close) {
      var alert = close.closest(".alert");
      if (!alert) { return; }
      var stack = alert.closest(".flash-stack");
      alert.remove();
      var next = stack && stack.querySelector(".alert-close");
      if (next) {
        next.focus();
      } else {
        var main = document.getElementById("main");
        if (main) { main.setAttribute("tabindex", "-1"); main.focus(); }
      }
    }
  });

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
      var submit = form.querySelector("button[type=submit][data-loading-text]");
      if (!submit || submit.classList.contains("is-loading")) { return; }
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
