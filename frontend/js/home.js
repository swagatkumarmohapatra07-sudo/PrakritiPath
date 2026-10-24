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

  async function init() {
    setupSearch();

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
      if (floatSpecies) floatSpecies.textContent = `${BT.num(stats.species_catalogued || 0)} species`;
      const floatDistricts = document.getElementById("float-districts");
      if (floatDistricts) floatDistricts.textContent = `${BT.num(stats.districts_covered || 0)} districts`;

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
