/* ==========================================================================
   My Utkal Heritage — shared header/footer layout and global behaviours
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;
  const NAV = [
    { href: "/", label: "Home", icon: "home" },
    { href: "/biodiversity.html", label: "Biodiversity AI", icon: "scan-eye" },
    { href: "/tourism.html", label: "Tourism Explorer", icon: "compass" },
    { href: "/map.html", label: "Interactive Map", icon: "map" },
    { href: "/saved.html", label: "Saved Places", icon: "heart" },
    { href: "/observations.html", label: "My Observations", icon: "notebook-pen" },
    { href: "/about.html", label: "About Project", icon: "info" },
  ];

  // The mark combines the Konark Sun Temple chariot wheel with a leaf in the
  // hub: Odisha's cultural signature and the biodiversity subject of the app.
  const LOGO = `<svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <circle cx="16" cy="16" r="13.1" stroke="currentColor" stroke-width="2"/>
    <circle cx="16" cy="16" r="10" stroke="currentColor" stroke-width="0.9" opacity=".55"/>
    <g stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
      <path d="M16 2.9v8M16 21.1v8M2.9 16h8M21.1 16h8"/>
      <path d="M6.7 6.7l5.7 5.7M19.6 19.6l5.7 5.7M25.3 6.7l-5.7 5.7M12.4 19.6l-5.7 5.7"/>
    </g>
    <circle cx="16" cy="16" r="3.7" fill="currentColor"/>
    <path d="M16 13.2c2 .7 3.2 2 3.2 3.6 0 1.5-1.1 2.7-3.2 3.1-2.1-.4-3.2-1.6-3.2-3.1 0-1.6 1.2-2.9 3.2-3.6Z" fill="#fff8e9" opacity=".94"/>
  </svg>`;

  const ODIA_NAME = "ମୋ ଉତ୍କଳ ଐତିହ୍ୟ";
  const SLOGAN = "Discover Our Roots. Explore Our Treasures.";

  // The masthead lockup. "Utkal" carries the gold/terracotta gradient defined in
  // odisha.css; the Odia line uses the bundled Noto Serif Oriya face.
  function brandMarkup(extraClass) {
    return `<a class="brand${extraClass ? ` ${extraClass}` : ""}" href="/" aria-label="My Utkal Heritage — home">
      <span class="brand-mark">${LOGO}</span>
      <span class="brand-text">
        <span class="brand-name"><span class="brand-my">My</span><span class="brand-utkal">Utkal</span> <span class="brand-heritage">Heritage</span></span>
        <span class="brand-tag brand-odia" lang="or">${ODIA_NAME}</span>
      </span>
    </a>`;
  }


  // The loader is a full-screen brand moment built around the Konark wheel.
  function mountLoader() {
    if (!document.body || document.getElementById("bt-loader")) return;
    const loader = document.createElement("div");
    loader.id = "bt-loader";
    loader.className = "bt-loader";
    loader.setAttribute("role", "status");
    loader.setAttribute("aria-live", "polite");
    loader.setAttribute("aria-label", "Loading My Utkal Heritage");
    loader.innerHTML = `
      <div class="bt-loader-inner">
        <div class="bt-loader-wheel">${LOGO}</div>
        <div class="bt-loader-word">My Utkal Heritage</div>
        <div class="bt-loader-sub" lang="or">${ODIA_NAME}</div>
        <div class="bt-loader-slogan">${SLOGAN}</div>
        <div class="bt-loader-bar" aria-hidden="true"><span></span></div>
      </div>`;
    document.body.appendChild(loader);
    document.body.classList.add("is-loading");
    let done = false;
    const hide = () => {
      if (done) return;
      done = true;
      loader.classList.add("is-done");
      document.body.classList.remove("is-loading");
      window.setTimeout(() => loader.remove(), 700);
    };
    if (document.readyState === "complete") {
      window.setTimeout(hide, 250);
    } else {
      window.addEventListener("load", () => window.setTimeout(hide, 300), { once: true });
      document.addEventListener("DOMContentLoaded", () => window.setTimeout(hide, 850), { once: true });
    }
    // Never let a slow image or a stalled request trap the interface behind the loader.
    window.setTimeout(hide, 1400);
  }

  function currentPath() {
    let path = location.pathname;
    if (path.endsWith("/index.html")) path = path.replace("index.html", "");
    return path || "/";
  }

  function activeKey() {
    const path = currentPath();
    if (path === "/" || path === "") return "/";
    if (path.includes("destination")) return "/tourism.html";
    if (path.includes("itinerary")) return "/saved.html";
    return path;
  }

  function navMarkup(mobile) {
    return NAV.map((item) => {
      const active = item.href === activeKey();
      return `<li><a class="nav-link" href="${item.href}" ${active ? 'aria-current="page"' : ""}>
        ${BT.icon(item.icon)}<span>${BT.esc(item.label)}</span>
      </a></li>`;
    }).join("");
  }

  function buildHeader() {
    const host = document.getElementById("site-header");
    if (!host) return;
    host.innerHTML = `
      <a class="skip-link" href="#main">Skip to main content</a>
      <div class="container nav">
        ${brandMarkup()}
        <nav class="nav-main" aria-label="Primary navigation">
          <ul class="nav-links">${navMarkup(false)}</ul>
        </nav>
        <div class="nav-actions">
          <a class="btn btn-primary btn-sm nav-map-link" href="/map.html">${BT.icon("map")}Explore map</a>
          <button class="icon-btn" id="theme-toggle" type="button" aria-label="Switch colour theme">
            <i data-lucide="moon" aria-hidden="true"></i>
          </button>
          <button class="icon-btn nav-toggle" id="nav-toggle" type="button"
                  aria-label="Open navigation menu" aria-expanded="false" aria-controls="mobile-nav">
            <i data-lucide="menu" aria-hidden="true"></i>
          </button>
        </div>
      </div>
      <div class="nav-backdrop" id="nav-backdrop" aria-hidden="true"></div>
      <aside class="mobile-nav" id="mobile-nav" aria-label="Site menu" aria-hidden="true">
        <div class="mobile-nav-head">
          ${brandMarkup()}
          <button class="icon-btn" id="nav-close" type="button" aria-label="Close navigation menu">
            <i data-lucide="x" aria-hidden="true"></i>
          </button>
        </div>
        <nav aria-label="Mobile navigation">
          <ul>${navMarkup(true)}</ul>
        </nav>
        <div class="mobile-nav-actions">
          <a class="btn btn-primary" href="/map.html">${BT.icon("map")}Open interactive map</a>
          <a class="btn btn-secondary" href="/tourism.html?category=cultural">${BT.icon("landmark")}Explore Odisha culture</a>
        </div>
        <div class="mobile-nav-foot">
          <span class="brand-odia" lang="or">${ODIA_NAME}</span>
          <span>${SLOGAN}</span>
        </div>
      </aside>
      <div id="header-observer" aria-hidden="true"></div>`;
    host.classList.add("site-header");
    host.id = "site-header";
    host.setAttribute("data-site-header", "true");
    host.style.position = "sticky";

    // The sticky header uses backdrop-filter, which creates a containing block
    // for fixed children. Move the drawer out so it always fills the viewport.
    ["#nav-backdrop", "#mobile-nav"].forEach((selector) => {
      const node = host.querySelector(selector);
      if (node) document.body.appendChild(node);
    });
  }


  function buildFooter() {
    const host = document.getElementById("site-footer");
    if (!host) return;
    host.className = "site-footer";
    host.innerHTML = `
      <div class="container">
        <div class="footer-grid">
          <div>
            ${brandMarkup()}
            <p class="footer-slogan" lang="en">${SLOGAN}</p>
            <p class="footer-about">
              A final-year B.Tech CSE (Data Science) project exploring whether
              uncertainty-aware AI and observation-quality checks can produce more
              trustworthy biodiversity records — paired with a carefully sourced
              guide to Odisha's cultural and natural places.
            </p>
            <p class="footer-about" style="margin-top:10px">
              AI predictions are preliminary and are never displayed as verified records.
            </p>
          </div>
          <div class="footer-col">
            <h4>Explore</h4>
            <ul>
              <li><a href="/biodiversity.html">Biodiversity AI</a></li>
              <li><a href="/tourism.html">Tourism Explorer</a></li>
              <li><a href="/tourism.html?category=cultural">Odisha culture</a></li>
              <li><a href="/map.html">Interactive map</a></li>
              <li><a href="/saved.html">Saved places & trips</a></li>
              <li><a href="/observations.html">Observations</a></li>
            </ul>
          </div>
          <div class="footer-col">
            <h4>Project</h4>
            <ul>
              <li><a href="/about.html">About & limitations</a></li>
              <li><a href="/about.html#research">Research & evaluation</a></li>
              <li><a href="/about.html#sources">Data sources</a></li>
              <li><a href="/docs" target="_blank" rel="noopener">API documentation</a></li>
              <li><a href="/admin.html">Reviewer console</a></li>
            </ul>
          </div>
          <div class="footer-col">
            <h4>Credibility</h4>
            <ul>
              <li><a href="/about.html#ethics">Ethics & privacy</a></li>
              <li><a href="/about.html#limitations">Known limitations</a></li>
              <li><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap licence</a></li>
              <li><a href="/about.html#datasets">Dataset licensing</a></li>
              <li><a href="/about.html#credits">Photograph credits</a></li>
            </ul>
          </div>
        </div>
        <div class="footer-bottom">
          <span>© ${new Date().getFullYear()} My Utkal Heritage · Academic project, Odisha, India.</span>
          <span class="footer-badge">${BT.icon("database")}Tourism coordinates © OpenStreetMap contributors (ODbL)</span>
          <span class="footer-badge">${BT.icon("cpu")}CPU-only · free & open source</span>
        </div>
      </div>`;
  }

  function setupTheme() {
    const button = document.getElementById("theme-toggle");
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = (theme, persist) => {
      document.documentElement.dataset.theme = theme;
      if (persist) {
        try {
          localStorage.setItem("biotrace_theme", theme);
        } catch (err) {
          /* ignore */
        }
      }
      if (button) {
        button.innerHTML = theme === "dark"
          ? '<i data-lucide="sun" aria-hidden="true"></i>'
          : '<i data-lucide="moon" aria-hidden="true"></i>';
        button.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
      }
      BT.refreshIcons();
      window.dispatchEvent(new CustomEvent("biotrace:theme", { detail: { theme } }));
    };

    apply(document.documentElement.dataset.theme || "light", false);
    if (button) {
      button.addEventListener("click", () => {
        const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        apply(next, true);
      });
    }
    media.addEventListener("change", (event) => {
      let stored = null;
      try {
        stored = localStorage.getItem("biotrace_theme");
      } catch (err) {
        stored = null;
      }
      if (!stored) apply(event.matches ? "dark" : "light", false);
    });
  }

  function setupMobileNav() {
    const toggle = document.getElementById("nav-toggle");
    const panel = document.getElementById("mobile-nav");
    const backdrop = document.getElementById("nav-backdrop");
    const closeBtn = document.getElementById("nav-close");
    if (!toggle || !panel) return;

    const desktop = window.matchMedia("(min-width: 1081px)");
    let returnFocus = null;

    const focusables = () =>
      Array.from(
        panel.querySelectorAll('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])')
      ).filter((el) => el.offsetParent !== null);

    function open() {
      returnFocus = document.activeElement;
      panel.classList.add("is-open");
      panel.setAttribute("aria-hidden", "false");
      if (backdrop) {
        backdrop.classList.add("is-open");
        backdrop.setAttribute("aria-hidden", "false");
      }
      document.body.classList.add("menu-open");
      toggle.setAttribute("aria-expanded", "true");
      toggle.innerHTML = '<i data-lucide="x" aria-hidden="true"></i>';
      BT.refreshIcons();
      const first = focusables()[0];
      if (first) window.setTimeout(() => first.focus({ preventScroll: true }), 60);
    }

    function close({ restoreFocus = true } = {}) {
      panel.classList.remove("is-open");
      panel.setAttribute("aria-hidden", "true");
      if (backdrop) {
        backdrop.classList.remove("is-open");
        backdrop.setAttribute("aria-hidden", "true");
      }
      document.body.classList.remove("menu-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.innerHTML = '<i data-lucide="menu" aria-hidden="true"></i>';
      BT.refreshIcons();
      if (restoreFocus && returnFocus && typeof returnFocus.focus === "function") {
        returnFocus.focus({ preventScroll: true });
      }
      returnFocus = null;
    }

    toggle.addEventListener("click", () => {
      if (panel.classList.contains("is-open")) close();
      else open();
    });
    if (closeBtn) closeBtn.addEventListener("click", () => close());
    panel.addEventListener("click", (event) => {
      if (event.target.closest("a")) close({ restoreFocus: false });
    });
    if (backdrop) backdrop.addEventListener("click", () => close());

    document.addEventListener("keydown", (event) => {
      if (!panel.classList.contains("is-open")) return;
      if (event.key === "Escape") {
        close();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    const handleViewport = () => {
      if (desktop.matches && panel.classList.contains("is-open")) close({ restoreFocus: false });
    };
    if (desktop.addEventListener) desktop.addEventListener("change", handleViewport);
    else desktop.addListener(handleViewport);
  }

  function setupScrollShadow() {
    const header = document.querySelector("[data-site-header]");
    if (!header) return;
    const update = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    update();
    window.addEventListener("scroll", update, { passive: true });
  }

  function setupReveal() {
    const items = BT.qsa(".reveal");
    if (!items.length) return;
    if (!("IntersectionObserver" in window)) {
      items.forEach((item) => item.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -40px 0px" }
    );
    items.forEach((item) => observer.observe(item));
  }

  function setupCounters() {
    const counters = BT.qsa("[data-count-to]");
    if (!counters.length) return;
    const animate = (el) => {
      const target = Number(el.dataset.countTo || 0);
      const duration = 900;
      const start = performance.now();
      const suffix = el.dataset.countSuffix || "";
      const step = (now) => {
        const progress = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(target * eased).toLocaleString("en-IN") + suffix;
        if (progress < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    if (!("IntersectionObserver" in window)) {
      counters.forEach((el) => (el.textContent = Number(el.dataset.countTo).toLocaleString("en-IN")));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animate(entry.target);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    counters.forEach((el) => observer.observe(el));
  }

  BT.initLayout = function () {
    // Rebuild header/footer contents (containers exist in each page).
    buildHeader();
    buildFooter();
    setupTheme();
    setupMobileNav();
    setupScrollShadow();
    setupReveal();
    setupCounters();
    BT.refreshIcons();
  };

  BT.observeReveal = setupReveal;
  BT.observeCounters = setupCounters;

  mountLoader();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", BT.initLayout);
  } else {
    BT.initLayout();
  }
})();
