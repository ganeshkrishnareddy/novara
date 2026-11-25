/* Little Grins — local prototype behaviour.
   Vanilla JS only. No network requests, no analytics, no storage,
   no third-party scripts and no form submission anywhere. */
(function () {
  "use strict";

  /* ---------- Mobile navigation ---------- */
  var navToggle = document.getElementById("nav-toggle");
  var primaryNav = document.getElementById("primary-nav");

  function setNavOpen(open) {
    if (!navToggle || !primaryNav) return;
    primaryNav.classList.toggle("is-open", open);
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    navToggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
  }

  if (navToggle && primaryNav) {
    navToggle.addEventListener("click", function () {
      setNavOpen(navToggle.getAttribute("aria-expanded") !== "true");
    });
    primaryNav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setNavOpen(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && primaryNav.classList.contains("is-open")) {
        setNavOpen(false);
        navToggle.focus();
      }
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 760) setNavOpen(false);
    });
  }

  /* ---------- Prototype consent controls (labels only, nothing stored) ---------- */
  var analyticsToggle = document.getElementById("analytics-toggle");
  var consentDismiss = document.getElementById("consent-dismiss");
  var consentBanner = document.getElementById("consent-banner");

  if (analyticsToggle) {
    analyticsToggle.addEventListener("click", function () {
      var on = analyticsToggle.getAttribute("aria-pressed") !== "true";
      analyticsToggle.setAttribute("aria-pressed", on ? "true" : "false");
      analyticsToggle.textContent = on ? "Analytics: on (prototype only)" : "Analytics: off";
    });
  }
  if (consentDismiss && consentBanner) {
    consentDismiss.addEventListener("click", function () {
      consentBanner.hidden = true;
    });
  }

  /* ---------- FAQ accordion ---------- */
  var triggers = Array.prototype.slice.call(document.querySelectorAll(".accordion-trigger"));

  function setPanel(trigger, open) {
    var panel = document.getElementById(trigger.getAttribute("aria-controls"));
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    if (panel) panel.hidden = !open;
  }

  triggers.forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      var shouldOpen = trigger.getAttribute("aria-expanded") !== "true";
      triggers.forEach(function (other) { setPanel(other, false); });
      if (shouldOpen) setPanel(trigger, true);
    });
  });

  /* ---------- Local guide category filter ---------- */
  var filterButtons = Array.prototype.slice.call(document.querySelectorAll(".filter-chip"));
  var guideCards = Array.prototype.slice.call(document.querySelectorAll("#guide-grid .guide-card"));

  filterButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      var category = button.getAttribute("data-filter");
      filterButtons.forEach(function (other) {
        other.setAttribute("aria-pressed", other === button ? "true" : "false");
      });
      guideCards.forEach(function (card) {
        card.hidden = category !== "all" && card.getAttribute("data-category") !== category;
      });
    });
  });

  /* ---------- Smooth in-page scrolling ---------- */
  var reduceMotion = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };

  document.addEventListener("click", function (event) {
    var link = event.target.closest ? event.target.closest('a[href^="#"]') : null;
    if (!link) return;
    var hash = link.getAttribute("href");
    if (!hash || hash === "#") return;

    var target;
    try {
      target = document.querySelector(hash);
    } catch (error) {
      return;
    }
    if (!target) return;

    event.preventDefault();
    setNavOpen(false);
    target.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "start" });

    if (window.history && window.history.pushState) {
      try {
        window.history.pushState(null, "", hash);
      } catch (error) {
        /* Some browsers restrict history changes on file:// pages; scrolling still works. */
      }
    }

    var isFocusable = target.matches("a, button, input, select, textarea, [tabindex]");
    if (!isFocusable) target.setAttribute("tabindex", "-1");
    try {
      target.focus({ preventScroll: true });
    } catch (error) {
      target.focus();
    }
  });

  /* ---------- Enquiry form: validation only, never submitted ---------- */
  var form = document.getElementById("enquiry-form");

  if (form) {
    var summary = document.getElementById("form-summary");
    var status = document.getElementById("form-status");

    function validDate(value) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
      var parts = value.split("-");
      var year = Number(parts[0]);
      var month = Number(parts[1]);
      var day = Number(parts[2]);
      var date = new Date(year, month - 1, day);
      return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
    }

    var rules = {
      parentName: function (value) {
        return value.trim() ? "" : "Please enter your name.";
      },
      childName: function (value) {
        return value.trim() ? "" : "Please enter your child's name.";
      },
      childAge: function (value) {
        if (!value.trim()) return "Please enter your child's age.";
        var age = Number(value);
        if (!Number.isInteger(age) || age < 0 || age > 18) return "Enter a whole number from 0 to 18.";
        return "";
      },
      email: function (value) {
        if (!value.trim()) return "Please enter an email address.";
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
          ? ""
          : "Enter a valid email address, such as name@example.com.";
      },
      phone: function (value) {
        if (!value.trim()) return "";
        var digits = value.replace(/\D/g, "");
        if (digits.length < 7 || digits.length > 15) return "Enter a valid phone number, or leave this blank.";
        return "";
      },
      topic: function (value) {
        return value ? "" : "Please choose a service of interest.";
      },
      preferredDate: function (value) {
        if (!value.trim()) return "";
        return validDate(value.trim()) ? "" : "Enter a valid date, or leave this blank.";
      },
      preferredTime: function () { return ""; },
      clinic: function (value) {
        return value ? "" : "Please choose a clinic.";
      },
      message: function (value) {
        return value.trim().length >= 10 ? "" : "Please write at least 10 characters.";
      },
      consent: function (value) {
        return value ? "" : "Please read and accept the sample privacy notice.";
      }
    };

    function showError(input, message) {
      var error = document.getElementById(input.id + "-error");
      if (error) error.textContent = message;
      if (message) {
        input.setAttribute("aria-invalid", "true");
      } else {
        input.removeAttribute("aria-invalid");
      }
    }

    function validateField(input) {
      var rule = rules[input.name];
      if (!rule) return "";
      var value = input.type === "checkbox" ? (input.checked ? "yes" : "") : input.value;
      var message = rule(value);
      showError(input, message);
      return message;
    }

    Object.keys(rules).forEach(function (name) {
      var input = form.elements[name];
      if (!input) return;
      var eventName = input.tagName === "SELECT" || input.type === "checkbox" ? "change" : "input";
      input.addEventListener(eventName, function () {
        if (input.getAttribute("aria-invalid") === "true") validateField(input);
        if (status) status.textContent = "";
        if (summary) {
          summary.hidden = true;
          summary.textContent = "";
        }
      });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault(); /* hard guarantee: nothing is ever submitted */

      var firstInvalid = null;
      var invalidCount = 0;

      Object.keys(rules).forEach(function (name) {
        var input = form.elements[name];
        if (!input) return;
        var message = validateField(input);
        if (message) {
          invalidCount += 1;
          if (!firstInvalid) firstInvalid = input;
        }
      });

      if (status) status.textContent = "";

      if (invalidCount) {
        if (summary) {
          summary.textContent = invalidCount === 1
            ? "Please check the highlighted field before continuing."
            : "Please check the " + invalidCount + " highlighted fields before continuing.";
          summary.hidden = false;
        }
        if (firstInvalid) firstInvalid.focus();
        return;
      }

      if (summary) {
        summary.textContent = "";
        summary.hidden = true;
      }
      if (status) {
        status.textContent = "Local prototype — nothing was sent. No booking has been created.";
      }
    });

    /* Second guard: even if the main handler is interrupted, the form cannot navigate. */
    form.onsubmit = function () { return false; };
  }

  /* ---------- Footer year ---------- */
  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
