/* ==========================================================================
   BioTrace — shared header/footer layout and global behaviours
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
        <a class="brand" href="/" aria-label="BioTrace home">
          <span class="brand-mark">${LOGO}</span>
          <span class="brand-text">
            <span class="brand-name">BioTrace</span>
            <span class="brand-tag">Odisha · Culture &amp; Nature</span>
          </span>
        </a>
        <nav aria-label="Primary navigation">
          <ul class="nav-links">${navMarkup(false)}</ul>
        </nav>
        <div class="nav-actions">
          <a class="btn btn-primary btn-sm" href="/map.html">${BT.icon("map")}Explore map</a>
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
      <div class="mobile-nav" id="mobile-nav">
        <nav aria-label="Mobile navigation">
          <ul>${navMarkup(true)}</ul>
        </nav>
        <a class="btn btn-primary" href="/map.html">${BT.icon("map")}Open interactive map</a>
        <a class="btn btn-secondary" href="/tourism.html?category=cultural">${BT.icon("landmark")}Explore Odisha culture</a>
      </div>
      <div id="header-observer" aria-hidden="true"></div>`;
    host.classList.add("site-header");
    host.id = "site-header";
    host.setAttribute("data-site-header", "true");
    host.style.position = "sticky";
  }

  function buildFooter() {
    const host = document.getElementById("site-footer");
    if (!host) return;
    host.className = "site-footer";
    host.innerHTML = `
      <div class="container">
        <div class="footer-grid">
          <div>
            <a class="brand" href="/">
              <span class="brand-mark">${LOGO}</span>
              <span class="brand-text">
                <span class="brand-name">BioTrace</span>
                <span class="brand-tag">Odisha · Culture, Biodiversity &amp; Tourism</span>
              </span>
            </a>
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
          <span>© ${new Date().getFullYear()} BioTrace · Academic project, Odisha, India.</span>
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
    if (!toggle || !panel) return;
    const close = () => {
      panel.classList.remove("is-open");
      if (backdrop) {
        backdrop.classList.remove("is-open");
        backdrop.setAttribute("aria-hidden", "true");
      }
      document.body.classList.remove("menu-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.innerHTML = '<i data-lucide="menu" aria-hidden="true"></i>';
      BT.refreshIcons();
    };
    toggle.addEventListener("click", () => {
      const open = panel.classList.toggle("is-open");
      if (backdrop) {
        backdrop.classList.toggle("is-open", open);
        backdrop.setAttribute("aria-hidden", String(!open));
      }
      document.body.classList.toggle("menu-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.innerHTML = open
        ? '<i data-lucide="x" aria-hidden="true"></i>'
        : '<i data-lucide="menu" aria-hidden="true"></i>';
      BT.refreshIcons();
    });
    panel.addEventListener("click", (event) => {
      if (event.target.closest("a")) close();
    });
    if (backdrop) backdrop.addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 1080) close();
    });
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", BT.initLayout);
  } else {
    BT.initLayout();
  }
})();
