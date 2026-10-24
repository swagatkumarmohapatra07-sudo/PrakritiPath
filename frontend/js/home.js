/* ==========================================================================
   My Utkal Heritage — landing page
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;

  function setStat(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.removeAttribute("data-count-to");
    el.textContent = BT.num(value);
  }

  function renderCategories(categories) {
    const host = document.getElementById("home-categories");
    if (!host) return;
    const visible = (categories || []).filter((item) => item.count > 0);
    if (!visible.length) {
      host.innerHTML = BT.emptyState(
        "No categories yet",
        "The catalogue has not been seeded. Run the seed script, then reload this page.",
        "compass"
      );
      BT.refreshIcons();
      return;
    }
    host.innerHTML = visible
      .map(
        (item) => `<a class="category-tile" href="/tourism.html?category=${encodeURIComponent(item.slug)}">
          <span class="cat-count">${BT.num(item.count)}</span>
          <span class="cat-icon">${BT.icon(item.icon)}</span>
          <strong>${BT.esc(item.label)}</strong>
          <span>${BT.esc(item.group)}</span>
        </a>`
      )
      .join("");
    BT.refreshIcons();
  }

  function renderFeatured(featured) {
    const host = document.getElementById("featured-grid");
    if (!host) return;
    if (!featured || !featured.length) {
      host.innerHTML = BT.emptyState(
        "No featured places",
        "Featured destinations appear once the tourism catalogue is seeded.",
        "map-pin"
      );
      BT.refreshIcons();
      return;
    }
    host.innerHTML = featured.slice(0, 6).map((item) => BT.destinationCard(item)).join("");
    BT.refreshIcons();
  }

  function renderRecent(items) {
    const host = document.getElementById("recent-observations");
    if (!host) return;
    if (!items || !items.length) {
      host.innerHTML = BT.emptyState(
        "No observations yet",
        "Be the first to submit a consented observation from the identification studio. Records remain pending until reviewed.",
        "notebook-pen",
        `<a class="btn btn-primary" href="/biodiversity.html">${BT.icon("camera")}Identify a plant or bird</a>`
      );
      BT.refreshIcons();
      return;
    }
    host.innerHTML = `<div class="grid grid-2">${items
      .map(
        (item) => `<a class="obs-item" href="/observations.html?open=${encodeURIComponent(item.id)}" style="text-decoration:none;color:inherit">
          <div class="obs-thumb-placeholder">${BT.icon(item.category === "bird" ? "bird" : "leaf")}</div>
          <div class="obs-body">
            <div class="row-between" style="gap:8px">
              <div style="min-width:0">
                <h3 class="obs-title">${BT.esc(item.label || item.scientific_name || "Unidentified")}</h3>
                <div class="obs-sci">${BT.esc(item.scientific_name || "")}</div>
              </div>
              ${BT.statusBadge(item.status)}
            </div>
            <div class="obs-meta">
              <span>${BT.icon(item.category === "bird" ? "bird" : "leaf")} ${item.category === "bird" ? "Bird" : "Plant"}</span>
              <span class="dot-sep"></span>
              <span>AI confidence ${BT.pct(item.confidence)}</span>
              <span class="dot-sep"></span>
              <span>${BT.icon("map-pin")} ${BT.esc(item.district || "No district recorded")}</span>
              <span class="dot-sep"></span>
              <span>${BT.relative(item.created_at)}</span>
            </div>
          </div>
        </a>`
      )
      .join("")}</div>`;
    BT.refreshIcons();
  }

  function renderMap(points) {
    const host = document.getElementById("home-map");
    if (!host) return;
    if (!window.L) {
      host.innerHTML = `<div class="map-fallback">${BT.icon("map")}Map library failed to load. Open the interactive map page for the full experience.</div>`;
      BT.refreshIcons();
      return;
    }
    const map = L.map(host, {
      zoomControl: false,
      scrollWheelZoom: false,
      attributionControl: true,
    });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const group = L.featureGroup();
    (points || []).forEach((point) => {
      const marker = L.circleMarker([point.latitude, point.longitude], {
        radius: 6,
        weight: 1.5,
        color: "#f4fff9",
        fillColor: "#14523c",
        fillOpacity: 0.92,
      });
      marker.bindPopup(
        `<div class="map-popup"><span class="popup-cat">${BT.esc(BT.category(point.category).label)}</span>
         <h4>${BT.esc(point.name)}</h4>
         <a href="/destination.html?slug=${encodeURIComponent(point.slug)}">View details</a></div>`
      );
      group.addLayer(marker);
    });

    if (points && points.length) {
      map.fitBounds(group.getBounds().pad(0.15));
      group.addTo(map);
    } else {
      map.setView([20.3, 84.8], 6);
    }
    // The panel is initially hidden in some layouts; recalculate after paint.
    setTimeout(() => map.invalidateSize(), 150);
  }

  function setupSearch() {
    const form = document.getElementById("hero-search");
    const input = document.getElementById("hero-q");
    if (form && input) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const q = input.value.trim();
        window.location.href = q ? `/tourism.html?q=${encodeURIComponent(q)}` : "/tourism.html";
      });
    }
    BT.qsa("[data-suggest]").forEach((button) => {
      button.addEventListener("click", () => {
        window.location.href = `/tourism.html?category=${encodeURIComponent(button.dataset.suggest)}`;
      });
    });
  }

  function setupHeroGallery() {
    const gallery = document.getElementById("hero-gallery");
    if (!gallery) return;
    const buttons = Array.from(gallery.querySelectorAll("[data-hero-item]"));
    if (!buttons.length) return;

    const stage = document.getElementById("hero-stage-panel");
    const stageImg = document.getElementById("hero-stage-img");
    const kickerEl = document.getElementById("hero-stage-kicker");
    const titleEl = document.getElementById("hero-stage-title");
    const linkEl = document.getElementById("hero-stage-link");
    const odiaEl = document.getElementById("hero-stage-odia");
    const countEl = document.getElementById("hero-count-current");
    const totalEl = document.getElementById("hero-count-total");
    const prevBtn = document.querySelector("[data-hero-prev]");
    const nextBtn = document.querySelector("[data-hero-next]");
    const playBtn = document.querySelector("[data-hero-play]");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

    let index = Math.max(0, buttons.findIndex((btn) => btn.classList.contains("is-active")));
    let timer = null;
    let playing = !reduced.matches;
    let inView = true;
    let hovered = false;

    if (totalEl) totalEl.textContent = String(buttons.length).padStart(2, "0");

    function paint(next, options) {
      const opts = options || {};
      index = (next + buttons.length) % buttons.length;
      const btn = buttons[index];
      const data = btn.dataset;

      buttons.forEach((item, i) => {
        const active = i === index;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", String(active));
        item.tabIndex = active ? 0 : -1;
      });

      const src = data.src;
      if (stageImg && src && stageImg.getAttribute("src") !== src) {
        stageImg.classList.add("is-swapping");
        const preload = new Image();
        const commit = () => {
          stageImg.src = src;
          stageImg.alt = data.alt || "";
          stageImg.classList.remove("is-swapping");
        };
        preload.onload = commit;
        preload.onerror = () => stageImg.classList.remove("is-swapping");
        preload.src = src;
      } else if (stageImg && src) {
        stageImg.alt = data.alt || "";
      }

      if (kickerEl) kickerEl.textContent = data.kicker || "";
      if (titleEl) titleEl.textContent = data.title || "";
      if (odiaEl) odiaEl.textContent = data.odia || "";
      if (linkEl && data.href) linkEl.href = data.href;
      if (stage) stage.setAttribute("aria-labelledby", btn.id);
      if (countEl) countEl.textContent = String(index + 1).padStart(2, "0");
      if (opts.focus) btn.focus({ preventScroll: true });
    }

    function stop() {
      if (timer) {
        window.clearInterval(timer);
        timer = null;
      }
    }

    function start() {
      stop();
      if (!playing || reduced.matches || !inView || hovered || document.hidden) return;
      timer = window.setInterval(() => paint(index + 1), 4600);
    }

    function restart() {
      if (playing) start();
    }

    buttons.forEach((btn, i) => {
      btn.addEventListener("click", () => {
        paint(i);
        restart();
      });
    });

    gallery.addEventListener("keydown", (event) => {
      const key = event.key;
      if (key === "ArrowRight" || key === "ArrowDown") {
        event.preventDefault();
        paint(index + 1, { focus: true });
        restart();
      } else if (key === "ArrowLeft" || key === "ArrowUp") {
        event.preventDefault();
        paint(index - 1, { focus: true });
        restart();
      } else if (key === "Home") {
        event.preventDefault();
        paint(0, { focus: true });
        restart();
      } else if (key === "End") {
        event.preventDefault();
        paint(buttons.length - 1, { focus: true });
        restart();
      }
    });

    if (prevBtn) prevBtn.addEventListener("click", () => {
      paint(index - 1);
      restart();
    });
    if (nextBtn) nextBtn.addEventListener("click", () => {
      paint(index + 1);
      restart();
    });

    if (playBtn) {
      playBtn.setAttribute("aria-pressed", String(!playing));
      playBtn.setAttribute("aria-label", playing ? "Pause automatic highlights" : "Play automatic highlights");
      playBtn.innerHTML = playing
        ? `<i data-lucide="pause" aria-hidden="true"></i>`
        : `<i data-lucide="play" aria-hidden="true"></i>`;
      playBtn.addEventListener("click", () => {
        playing = !playing;
        playBtn.setAttribute("aria-pressed", String(!playing));
        playBtn.setAttribute("aria-label", playing ? "Pause automatic highlights" : "Play automatic highlights");
        playBtn.innerHTML = playing
          ? `<i data-lucide="pause" aria-hidden="true"></i>`
          : `<i data-lucide="play" aria-hidden="true"></i>`;
        BT.refreshIcons();
        if (playing) start();
        else stop();
      });
    }

    const setHover = (value) => {
      hovered = value;
      if (hovered) stop();
      else restart();
    };
    gallery.addEventListener("mouseenter", () => setHover(true));
    gallery.addEventListener("mouseleave", () => setHover(false));
    gallery.addEventListener("focusin", () => stop());
    gallery.addEventListener("focusout", (event) => {
      if (!gallery.contains(event.relatedTarget)) restart();
    });

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          inView = entries.some((entry) => entry.isIntersecting);
          if (inView) restart();
          else stop();
        },
        { threshold: 0.2 }
      );
      observer.observe(gallery);
    }

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stop();
      else restart();
    });

    if (reduced.addEventListener) {
      reduced.addEventListener("change", (event) => {
        playing = !event.matches;
        if (playBtn) {
          playBtn.setAttribute("aria-pressed", String(!playing));
          playBtn.innerHTML = playing
            ? `<i data-lucide="pause" aria-hidden="true"></i>`
            : `<i data-lucide="play" aria-hidden="true"></i>`;
          playBtn.setAttribute("aria-label", playing ? "Pause automatic highlights" : "Play automatic highlights");
          BT.refreshIcons();
        }
        if (playing) start();
        else stop();
      });
    }

    paint(index);
    start();
  }

  async function init() {
    setupSearch();
    setupHeroGallery();

    try {
      await BT.loadTaxonomy();
      await BT.loadFavourites();
      const data = await BT.api("/api/home");
      const stats = data.stats || {};
      setStat("stat-destinations", stats.destinations_total || 0);
      setStat("stat-districts", stats.districts_covered || 0);
      setStat("stat-species", stats.species_catalogued || 0);
      setStat("stat-observations", stats.observations_total || 0);

      const floatSpecies = document.getElementById("float-species");
      if (floatSpecies) floatSpecies.textContent = BT.num(stats.species_catalogued || 0);
      const floatDistricts = document.getElementById("float-districts");
      if (floatDistricts) floatDistricts.textContent = BT.num(stats.districts_covered || 0);

      renderCategories(data.categories);
      renderFeatured(data.featured);
      renderRecent(data.recent_observations);
      renderMap(data.map_preview);
    } catch (err) {
      const featured = document.getElementById("featured-grid");
      if (featured) {
        featured.innerHTML = BT.emptyState(
          "The catalogue could not load",
          "The My Utkal Heritage server may still be starting. Check that it is running, then reload the page.",
          "cloud-off",
          `<a class="btn btn-secondary" href="/">Reload</a>`
        );
      }
      BT.errorToast(err);
      BT.refreshIcons();
    }
    BT.refreshIcons();
    const cards = document.getElementById("featured-grid");
    if (cards) BT.bindDestinationCards(cards);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
