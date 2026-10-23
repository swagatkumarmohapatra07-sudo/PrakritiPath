/* ==========================================================================
   BioTrace shared utilities: API client, session, DOM, toasts, modals.
   Everything is attached to window.BT so plain <script> pages can share it.
   ========================================================================== */
(function () {
  "use strict";

  const BT = (window.BT = window.BT || {});

  /* ------------------------------------------------------------- Session */
  function createSessionId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "bt-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12);
  }

  BT.sessionId = function () {
    let id = null;
    try {
      id = localStorage.getItem("biotrace_session");
    } catch (err) {
      id = null;
    }
    if (!id || id.length < 8) {
      id = createSessionId();
      try {
        localStorage.setItem("biotrace_session", id);
      } catch (err) {
        /* private mode: keep the in-memory value for this page */
      }
      BT._memorySession = id;
    }
    return id || BT._memorySession;
  };

  /* ------------------------------------------------------------ API client */
  class ApiError extends Error {
    constructor(message, status, detail) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.detail = detail;
    }
  }
  BT.ApiError = ApiError;

  function normaliseDetail(detail, status) {
    if (!detail) return `Request failed (HTTP ${status}).`;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const loc = Array.isArray(item.loc) ? item.loc.filter((p) => p !== "body").join(".") : "";
          return (loc ? loc + ": " : "") + (item.msg || "Invalid value");
        })
        .join(" ");
    }
    if (typeof detail === "object") return detail.message || JSON.stringify(detail);
    return String(detail);
  }

  BT.api = async function (path, options = {}) {
    const headers = Object.assign(
      { "X-Session-Id": BT.sessionId() },
      options.headers || {}
    );
    let body = options.body;
    if (body && !(body instanceof FormData) && typeof body !== "string") {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), options.timeout || 60000);
    let response;
    try {
      response = await fetch(path, {
        method: options.method || "GET",
        headers,
        body,
        signal: controller.signal,
      });
    } catch (err) {
      clearTimeout(timeout);
      if (err.name === "AbortError") {
        throw new ApiError(
          "The request timed out. The server may still be starting up — try again in a moment.",
          0
        );
      }
      throw new ApiError(
        "Could not reach the BioTrace server. Make sure it is running and open the app from its server URL.",
        0
      );
    }
    clearTimeout(timeout);

    if (response.status === 204) return null;

    let payload = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        payload = await response.json();
      } catch (err) {
        payload = null;
      }
    } else {
      const text = await response.text();
      payload = text ? { detail: text.slice(0, 300) } : null;
    }

    if (!response.ok) {
      const message = normaliseDetail(payload && payload.detail, response.status);
      throw new ApiError(message, response.status, payload && payload.detail);
    }
    return payload;
  };

  BT.upload = function (path, formData, options = {}) {
    return BT.api(path, Object.assign({}, options, { method: "POST", body: formData, timeout: 120000 }));
  };

  /* --------------------------------------------------------------- Helpers */
  BT.esc = function (value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  BT.qs = (selector, root) => (root || document).querySelector(selector);
  BT.qsa = (selector, root) => Array.from((root || document).querySelectorAll(selector));

  BT.price = function (value) {
    if (value === 0) return "Free";
    return value ? `₹${Number(value).toLocaleString("en-IN")}` : "Not verified";
  };

  BT.num = function (value) {
    const n = Number(value || 0);
    return n.toLocaleString("en-IN");
  };

  BT.pct = function (value, digits = 0) {
    if (value === null || value === undefined) return "—";
    return `${(Number(value) * 100).toFixed(digits)}%`;
  };

  BT.fmtDate = function (value, options) {
    if (!value) return "Not specified";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Not specified";
    return date.toLocaleDateString("en-IN", options || { day: "numeric", month: "short", year: "numeric" });
  };

  BT.datetime = function (value) {
    if (!value) return "Unknown date";
    const date = new Date(value);
    return date.toLocaleString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  BT.relative = function (value) {
    if (!value) return "unknown";
    const then = new Date(value).getTime();
    if (Number.isNaN(then)) return "unknown";
    const diff = Math.round((Date.now() - then) / 1000);
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
    if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} d ago`;
    return BT.fmtDate(value);
  };

  BT.debounce = function (fn, wait = 250) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  };

  BT.icon = function (name, cls) {
    return `<i data-lucide="${BT.esc(name)}"${cls ? ` class="${BT.esc(cls)}"` : ""} aria-hidden="true"></i>`;
  };

  BT.refreshIcons = function () {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
    }
  };

  BT.statusBadge = function (status) {
    const map = {
      verified: ["badge-verified", "badge-check", "Verified"],
      pending: ["badge-pending", "clock", "Pending review"],
      needs_review: ["badge-review", "search-check", "Needs review"],
      rejected: ["badge-rejected", "x-circle", "Rejected"],
      provisional: ["badge-pending", "clock", "Provisional"],
      open: ["badge-pending", "inbox", "Open"],
      in_review: ["badge-review", "search-check", "In review"],
      resolved: ["badge-verified", "check", "Resolved"],
      dismissed: ["badge-neutral", "x", "Dismissed"],
    };
    const [cls, icon, label] = map[status] || ["badge-neutral", "circle", status || "Unknown"];
    return `<span class="badge ${cls}">${BT.icon(icon)}${BT.esc(label)}</span>`;
  };

  BT.CATEGORY_FALLBACK = {
    temple: { label: "Temples", icon: "landmark", group: "Religious sites", art: "temple" },
    mosque: { label: "Mosques & Islamic heritage", icon: "moon-star", group: "Religious sites", art: "mosque" },
    church: { label: "Churches", icon: "church", group: "Religious sites", art: "church" },
    buddhist: { label: "Buddhist sites", icon: "flower", group: "Religious sites", art: "buddhist" },
    jain: { label: "Jain heritage", icon: "hand", group: "Religious sites", art: "jain" },
    gurudwara: { label: "Gurudwaras", icon: "book-open", group: "Religious sites", art: "gurudwara" },
    museum: { label: "Museums & galleries", icon: "building-2", group: "Culture & heritage", art: "museum" },
    monument: { label: "Monuments & archaeology", icon: "history", group: "Culture & heritage", art: "monument" },
    fort_palace: { label: "Forts & palaces", icon: "castle", group: "Culture & heritage", art: "fort_palace" },
    cultural: { label: "Craft & culture", icon: "palette", group: "Culture & heritage", art: "cultural" },
    beach: { label: "Beaches", icon: "waves", group: "Nature & outdoors", art: "beach" },
    waterfall_lake: { label: "Lakes & waterfalls", icon: "droplets", group: "Nature & outdoors", art: "waterfall_lake" },
    wildlife: { label: "Wildlife & forests", icon: "trees", group: "Nature & outdoors", art: "wildlife" },
    park_garden: { label: "Parks & gardens", icon: "flower-2", group: "Nature & outdoors", art: "park_garden" },
    other: { label: "Other places", icon: "map-pin", group: "More to explore", art: "other" },
  };

  BT.category = function (slug) {
    const found = (BT.taxonomy && BT.taxonomy.categories || []).find((item) => item.slug === slug);
    return found || Object.assign({ slug, art: slug }, BT.CATEGORY_FALLBACK[slug] || BT.CATEGORY_FALLBACK.other);
  };

  BT.loadTaxonomy = async function () {
    if (BT._taxonomyPromise) return BT._taxonomyPromise;
    BT._taxonomyPromise = BT.api("/api/taxonomy")
      .then((data) => {
        BT.taxonomy = data;
        return data;
      })
      .catch(() => {
        BT.taxonomy = { categories: [], groups: [], districts: [], species: [] };
        return BT.taxonomy;
      });
    return BT._taxonomyPromise;
  };

  BT.art = function (category) {
    return `art-${BT.category(category).art || "other"}`;
  };

  BT.trainLabel = function (confidence) {
    if (confidence === null || confidence === undefined) return "Unscored";
    if (confidence >= 0.8) return "High for this model";
    if (confidence >= 0.55) return "Moderate";
    return "Low";
  };

  BT.emptyState = function (title, message, icon, action) {
    return `<div class="state">
      <div class="state-icon">${BT.icon(icon || "compass")}</div>
      <h3>${BT.esc(title)}</h3>
      <p>${BT.esc(message)}</p>
      ${action || ""}
    </div>`;
  };

  BT.skeletonCards = function (count = 3) {
    return Array.from({ length: count })
      .map(() => `<div class="skeleton skeleton-card" aria-hidden="true"></div>`)
      .join("");
  };

  /* ----------------------------------------------------------------- Toasts */
  BT.toast = function (title, message, type = "info", timeout = 5200) {
    let stack = BT.qs(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      stack.setAttribute("role", "status");
      stack.setAttribute("aria-live", "polite");
      document.body.appendChild(stack);
    }
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    const iconName = type === "success" ? "check-circle-2" : type === "error" ? "alert-circle" : "info";
    toast.innerHTML = `
      ${BT.icon(iconName)}
      <div style="min-width:0"><strong>${BT.esc(title)}</strong>${message ? `<p>${BT.esc(message)}</p>` : ""}</div>
      <button class="toast-close" type="button" aria-label="Dismiss notification">${BT.icon("x")}</button>`;
    stack.appendChild(toast);
    BT.refreshIcons();
    const remove = () => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      toast.style.transition = "opacity .2s, transform .2s";
      setTimeout(() => toast.remove(), 220);
    };
    toast.querySelector(".toast-close").addEventListener("click", remove);
    if (timeout) setTimeout(remove, timeout);
    return toast;
  };

  BT.errorToast = function (error) {
    const message = error && error.message ? error.message : "Unexpected error.";
    BT.toast("Something went wrong", message, "error", 7000);
  };

  /* ----------------------------------------------------------------- Modals */
  BT.modal = function ({ title, subtitle, body, footer, size, onClose, initialFocus }) {
    BT.closeModal();
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.setAttribute("role", "presentation");
    backdrop.innerHTML = `
      <div class="modal ${size === "lg" ? "modal-lg" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-head">
          <div><h3 id="modal-title">${BT.esc(title || "")}</h3>${subtitle ? `<p>${BT.esc(subtitle)}</p>` : ""}</div>
          <button class="modal-close" type="button" aria-label="Close dialog">${BT.icon("x")}</button>
        </div>
        <div class="modal-body">${body || ""}</div>
        ${footer ? `<div class="modal-foot">${footer}</div>` : ""}
      </div>`;
    document.body.appendChild(backdrop);
    document.body.classList.add("no-scroll");
    BT.refreshIcons();

    const previousFocus = document.activeElement;
    const close = () => {
      backdrop.remove();
      document.body.classList.remove("no-scroll");
      document.removeEventListener("keydown", onKey);
      if (previousFocus && previousFocus.focus) previousFocus.focus();
      if (onClose) onClose();
    };
    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
      if (event.key === "Tab") {
        const focusables = Array.from(
          backdrop.querySelectorAll("a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex='-1'])")
        ).filter((el) => el.offsetParent !== null);
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    backdrop.querySelector(".modal-close").addEventListener("click", close);
    backdrop.addEventListener("mousedown", (event) => {
      if (event.target === backdrop) close();
    });
    document.addEventListener("keydown", onKey);
    BT.activeModal = { element: backdrop, close };
    setTimeout(() => {
      const target = initialFocus
        ? backdrop.querySelector(initialFocus)
        : backdrop.querySelector("input, select, textarea, button.btn-primary, .modal-close");
      if (target) target.focus();
    }, 60);
    return BT.activeModal;
  };

  BT.closeModal = function () {
    if (BT.activeModal) {
      BT.activeModal.close();
      BT.activeModal = null;
    }
  };

  BT.confirm = function ({ title, message, confirmLabel = "Confirm", danger = false }) {
    return new Promise((resolve) => {
      BT.modal({
        title,
        body: `<p class="muted" style="margin:0;font-size:.9rem">${BT.esc(message)}</p>`,
        footer: `<button class="btn btn-secondary" data-action="cancel" type="button">Cancel</button>
                 <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-action="ok" type="button">${BT.esc(confirmLabel)}</button>`,
        onClose: () => resolve(false),
      });
      BT.qs('.modal [data-action="cancel"]').addEventListener("click", () => {
        BT.activeModal = null;
        resolve(false);
        BT.closeModal();
      });
      BT.qs('.modal [data-action="ok"]').addEventListener("click", () => {
        BT.activeModal = null;
        resolve(true);
        BT.closeModal();
      });
    });
  };

  /* -------------------------------------------------------------- Misc utils */
  BT.debounceInput = function (input, handler, wait) {
    const fn = BT.debounce(handler, wait);
    input.addEventListener("input", fn);
  };

  BT.copy = async function (text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try {
        ok = document.execCommand("copy");
      } catch (e) {
        ok = false;
      }
      area.remove();
      return ok;
    }
  };

  BT.geolocate = function () {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocation is not supported by this browser."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (position) => resolve({ lat: position.coords.latitude, lon: position.coords.longitude, accuracy: position.coords.accuracy }),
        (error) => {
          const messages = {
            1: "Location permission was denied. You can still search manually.",
            2: "Your location could not be determined right now.",
            3: "Location request timed out.",
          };
          reject(new Error(messages[error.code] || "Could not get your location."));
        },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
      );
    });
  };

  BT.share = async function (title, url) {
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return true;
      } catch (err) {
        if (err.name === "AbortError") return false;
      }
    }
    const ok = await BT.copy(url);
    if (ok) BT.toast("Link copied", "The destination link is on your clipboard.", "success");
    return ok;
  };

  BT.shareUrl = function (slug) {
    return `${location.origin}/destination.html?slug=${encodeURIComponent(slug)}`;
  };

  BT.setBusy = function (button, busy, busyLabel) {
    if (!button) return;
    if (busy) {
      button.dataset.original = button.innerHTML;
      button.disabled = true;
      button.classList.add("loading");
      button.innerHTML = `<span class="spinner"></span>${BT.esc(busyLabel || "Working…")}`;
    } else {
      button.disabled = false;
      button.classList.remove("loading");
      if (button.dataset.original) button.innerHTML = button.dataset.original;
    }
  };

  BT.directionsUrl = function (item) {
    if (item.latitude === null || item.latitude === undefined) return null;
    return `https://www.openstreetmap.org/directions?from=&to=${item.latitude}%2C${item.longitude}#map=15/${item.latitude}/${item.longitude}`;
  };

  BT.imageFallback = function (img, category) {
    img.addEventListener(
      "error",
      () => {
        img.style.display = "none";
      },
      { once: true }
    );
  };

  /* ------------------------------------------------------------ Placeholder art */
  BT.heroArt = function () {
    return `<svg class="art-hero-svg" viewBox="0 0 600 520" role="img" aria-label="Illustrated Odisha landscape with hills, a temple, birds and the coast">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#0e3f31"/><stop offset=".55" stop-color="#176b51"/><stop offset="1" stop-color="#2b8767"/>
        </linearGradient>
        <linearGradient id="sun" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#ffe3a8"/><stop offset="1" stop-color="#e7a95c"/>
        </linearGradient>
        <linearGradient id="hill1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#1d6f55"/><stop offset="1" stop-color="#124a38"/>
        </linearGradient>
        <linearGradient id="hill2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#0f4e3a"/><stop offset="1" stop-color="#0a3327"/>
        </linearGradient>
        <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#4fb59c"/><stop offset="1" stop-color="#1d7b67"/>
        </linearGradient>
      </defs>
      <rect width="600" height="520" fill="url(#sky)"/>
      <circle cx="438" cy="132" r="58" fill="url(#sun)" opacity=".95"/>
      <circle cx="438" cy="132" r="82" fill="none" stroke="#ffe3a8" stroke-opacity=".18"/>
      <circle cx="438" cy="132" r="108" fill="none" stroke="#ffe3a8" stroke-opacity=".1"/>
      <g fill="#eafff5" opacity=".7">
        <path d="M352 118c9-7 18-7 25 0-9 2-17 5-25 0Z" transform="rotate(-8 352 118)"/>
        <path d="M382 96c7-5 14-5 19 0-7 1-13 4-19 0Z" transform="rotate(6 382 96)"/>
        <path d="M322 154c6-4 12-4 17 0-6 1-11 4-17 0Z" transform="rotate(12 322 154)"/>
        <path d="M470 104c5-4 11-4 15 0-5 1-10 3-15 0Z" transform="rotate(-14 470 104)"/>
      </g>
      <ellipse cx="150" cy="468" rx="300" ry="90" fill="#082a20" opacity=".5"/>
      <path d="M0 330c60-50 90-84 150-84s72 46 122 46 70-54 130-54 100 68 198 54v228H0Z" fill="url(#hill1)"/>
      <path d="M0 386c54-42 98-60 152-42s74 50 138 34 86-58 152-42 106 54 158 42v142H0Z" fill="url(#hill2)"/>
      <g opacity=".9">
        <path d="M250 352c4-30 8-52 16-70h8c8 18 12 40 16 70Z" fill="#0a2a20"/>
        <path d="M258 302h20v-8h-20zM256 288h24v-7h-24zM254 274h28v-7h-28zM252 260h32v-6h-32zM266 246h4v-14h-4z" fill="#0a2a20"/>
        <path d="M244 352h60v8h-60z" fill="#0a2a20"/>
      </g>
      <path d="M0 448c62-16 118-6 168 6s94 12 148 0 92-18 148-6 88 8 136-6v78H0Z" fill="url(#water)" opacity=".8"/>
      <g fill="#082a20" opacity=".8">
        <path d="M92 430c0-26 8-44 18-52 10 8 18 26 18 52Z"/>
        <path d="M96 378c10-10 18-10 28 0-10 2-18 5-28 0Z"/>
        <path d="M470 428c0-20 6-32 14-38 8 6 14 18 14 38Z"/>
      </g>
      <g fill="none" stroke="#d7fff0" stroke-opacity=".32" stroke-width="1">
        <path d="M-20 60c40-24 70 24 120 6s74 14 130-4 88 16 150-2 90 18 160 2"/>
        <path d="M-20 78c40-24 70 24 120 6s74 14 130-4 88 16 150-2 90 18 160 2"/>
      </g>
    </svg>`;
  };

  BT.categoryArt = function (category, size) {
    const meta = BT.category(category);
    return `<div class="card-art ${BT.art(category)}">
      <span class="topo"></span>
      ${BT.icon(meta.icon || "map-pin", "art-icon")}
    </div>`;
  };
})();
