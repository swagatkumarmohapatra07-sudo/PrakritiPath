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

  const LOGO = `<svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <path d="M25.5 6.5c-7.8-1.4-14 2.4-15.3 8.4-.8 3.7 1.6 7.3 5.2 7.7 6.1.7 10-4.4 10.1-16.1Z" fill="currentColor" opacity=".92"/>
    <path d="M9 26c1.2-6.8 4.4-11.2 9.4-13.6" stroke="#0f3d2e" stroke-width="1.7" stroke-linecap="round"/>
    <path d="M6 26.5h9" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".55"/>
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
            <span class="brand-tag">Odisha · Biodiversity & Tourism</span>
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
      <div class="mobile-nav" id="mobile-nav">
        <nav aria-label="Mobile navigation">
          <ul>${navMarkup(true)}</ul>
        </nav>
        <a class="btn btn-primary" href="/map.html">${BT.icon("map")}Open interactive map</a>
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
                <span class="brand-tag">Odisha · Biodiversity & Tourism</span>
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
    if (!toggle || !panel) return;
    const close = () => {
      panel.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.innerHTML = '<i data-lucide="menu" aria-hidden="true"></i>';
      BT.refreshIcons();
    };
    toggle.addEventListener("click", () => {
      const open = panel.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.innerHTML = open
        ? '<i data-lucide="x" aria-hidden="true"></i>'
        : '<i data-lucide="menu" aria-hidden="true"></i>';
      BT.refreshIcons();
    });
    panel.addEventListener("click", (event) => {
      if (event.target.closest("a")) close();
    });
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
