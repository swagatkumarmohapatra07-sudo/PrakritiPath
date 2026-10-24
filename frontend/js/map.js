/* ==========================================================================
   My Utkal Heritage — unified interactive map
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;

  const state = {
    layers: "combined",
    categories: [],
    district: "",
    status: "",
    start: "",
    end: "",
    q: "",
  };

  let map = null;
  let cluster = null;
  let records = [];
  let bounds = null;
  let userMarker = null;

  function buildControls() {
    const select = document.getElementById("map-district");
    (BT.taxonomy.districts || []).forEach((district) => {
      const option = document.createElement("option");
      option.value = district;
      option.textContent = district;
      select.appendChild(option);
    });

    const host = document.getElementById("map-categories");
    const tourism = (BT.taxonomy.categories || []).map((item) => ({
      slug: item.slug,
      label: item.label,
      icon: item.icon,
    }));
    const bio = [
      { slug: "plant", label: "Plant observations", icon: "leaf" },
      { slug: "bird", label: "Bird observations", icon: "bird" },
    ];
    host.innerHTML = tourism
      .concat(bio)
      .map(
        (item) => `<button class="chip" type="button" data-map-category="${BT.esc(item.slug)}" aria-pressed="false">
          ${BT.icon(item.icon)}${BT.esc(item.label)}
        </button>`
      )
      .join("");
    BT.qsa("[data-map-category]", host).forEach((button) => {
      button.addEventListener("click", () => {
        const slug = button.dataset.mapCategory;
        const index = state.categories.indexOf(slug);
        if (index >= 0) state.categories.splice(index, 1);
        else state.categories.push(slug);
        const active = state.categories.includes(slug);
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
        load();
      });
    });
    BT.refreshIcons();
  }

  function popupFor(record) {
    if (record.type === "tourism") {
      const item = record.item;
      return `<div class="map-popup">
        <span class="popup-cat">${BT.esc(BT.category(item.category).label)}</span>
        <h4>${BT.esc(item.name)}</h4>
        <div class="tiny muted">${BT.esc([item.city, item.district].filter(Boolean).join(", ") || "Odisha")}</div>
        <div style="margin-top:5px">${BT.statusBadge(item.verification_status)}</div>
        <div style="margin-top:6px"><a href="/destination.html?slug=${encodeURIComponent(item.slug)}">View details</a></div>
      </div>`;
    }
    const item = record.item;
    return `<div class="map-popup">
      <span class="popup-cat">${item.category === "bird" ? "Bird observation" : "Plant observation"}</span>
      <h4>${BT.esc(item.label)}</h4>
      <div class="tiny muted">${BT.datetime(item.created_at)}</div>
      <div style="margin-top:5px">${BT.statusBadge(item.verification_status)}</div>
      ${item.obscured ? `<div class="tiny muted" style="margin-top:5px">${BT.icon("shield")} Approximate location (${BT.esc(item.location_precision)}) — sensitive record.</div>` : ""}
      <div style="margin-top:6px"><a href="/observations.html">View observations</a></div>
    </div>`;
  }

  function markerFor(record) {
    if (record.type === "tourism") {
      const meta = BT.category(record.item.category);
      const icon = L.divIcon({
        className: "",
        html: `<div class="map-marker dest"><span>${BT.icon(meta.icon)}</span></div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 28],
        popupAnchor: [0, -26],
      });
      return L.marker([record.item.latitude, record.item.longitude], { icon, title: record.item.name });
    }
    const item = record.item;
    const pending = item.verification_status === "pending" || item.verification_status === "needs_review";
    return L.circleMarker([item.latitude, item.longitude], {
      radius: 7,
      weight: pending ? 2 : 1.5,
      dashArray: pending ? "3 3" : null,
      color: pending ? "#ffd88a" : "#f4fff9",
      fillColor: item.category === "bird" ? "#b96f44" : "#4f8a52",
      fillOpacity: 0.92,
    });
  }

  function listMarkup(visible) {
    if (!visible.length) {
      return BT.emptyState(
        "No visible records",
        "No tourism destinations or consented observations match these filters.",
        "map-pin-off"
      );
    }
    return visible
      .map((record, index) => {
        if (record.type === "tourism") {
          const item = record.item;
          return `<button class="map-list-item" type="button" data-record-index="${index}">
            <span class="ml-icon">${BT.icon(BT.category(item.category).icon)}</span>
            <span style="min-width:0;flex:1">
              <strong>${BT.esc(item.name)}</strong>
              <span>${BT.esc(BT.category(item.category).label)} · ${BT.esc(item.district || "district not recorded")}</span>
            </span>
            ${BT.statusBadge(item.verification_status)}
          </button>`;
        }
        const item = record.item;
        return `<button class="map-list-item" type="button" data-record-index="${index}">
          <span class="ml-icon" style="background:${item.category === "bird" ? "var(--coral-soft)" : "var(--mint-soft)"};color:${item.category === "bird" ? "var(--coral)" : "var(--emerald-deep)"}">
            ${BT.icon(item.category === "bird" ? "bird" : "leaf")}
          </span>
          <span style="min-width:0;flex:1">
            <strong>${BT.esc(item.label)}</strong>
            <span>${BT.esc(item.category)} · ${BT.relative(item.created_at)}${item.obscured ? " · approximate" : ""}</span>
          </span>
          ${BT.statusBadge(item.verification_status)}
        </button>`;
      })
      .join("");
  }

  function applySearch() {
    const query = state.q.toLowerCase();
    const visible = records.filter((record) => {
      const text = record.type === "tourism" ? record.item.name : record.item.label;
      return !query || String(text).toLowerCase().includes(query);
    });
    if (cluster) {
      cluster.clearLayers();
      visible.forEach((record) => cluster.addLayer(record.marker));
    }
    const list = document.getElementById("map-list");
    list.innerHTML = listMarkup(visible);
    BT.qsa("[data-record-index]", list).forEach((button) => {
      button.addEventListener("click", () => {
        const record = visible[Number(button.dataset.recordIndex)];
        if (!record) return;
        map.setView([record.item.latitude, record.item.longitude], Math.max(map.getZoom(), 13));
        record.marker.openPopup();
      });
    });
    document.getElementById("map-count").textContent = `${visible.length} record${visible.length === 1 ? "" : "s"}`;
    BT.refreshIcons();
  }

  function fitBounds() {
    if (!map) return;
    if (bounds) {
      map.fitBounds(
        [[bounds.min_lat, bounds.min_lon], [bounds.max_lat, bounds.max_lon]],
        { padding: [24, 24] }
      );
    } else {
      map.setView([20.3, 84.8], 6);
    }
  }

  function render(data) {
    records = [];
    bounds = data.bounds;
    if (cluster) {
      map.removeLayer(cluster);
      cluster = null;
    }
    cluster = window.L.markerClusterGroup
      ? L.markerClusterGroup({ maxClusterRadius: 48, showCoverageOnHover: false })
      : L.featureGroup();

    data.destinations.forEach((item) => {
      const record = { type: "tourism", item, marker: null };
      record.marker = markerFor(record);
      record.marker.bindPopup(popupFor(record));
      records.push(record);
    });
    data.observations.forEach((item) => {
      const record = { type: "biodiversity", item, marker: null };
      record.marker = markerFor(record);
      record.marker.bindPopup(popupFor(record));
      records.push(record);
    });

    map.addLayer(cluster);
    document.getElementById("map-notes").textContent = data.notes;
    fitBounds();
    applySearch();
  }

  async function load() {
    const list = document.getElementById("map-list");
    list.innerHTML = `<div class="skeleton skeleton-line" aria-hidden="true"></div><div class="skeleton skeleton-line w-60" aria-hidden="true"></div>`;
    const params = new URLSearchParams();
    params.set("layers", state.layers);
    if (state.district) params.set("district", state.district);
    state.categories.forEach((slug) => params.append("category", slug));
    if (state.status) params.set("status", state.status);
    if (state.start) params.set("start_date", state.start);
    if (state.end) params.set("end_date", state.end);
    try {
      const data = await BT.api(`/api/map?${params.toString()}`);
      render(data);
    } catch (err) {
      list.innerHTML = BT.emptyState("Map data could not load", err.message, "cloud-off");
      document.getElementById("map-notes").textContent = "The map data request failed. Check the server and try again.";
      BT.errorToast(err);
      BT.refreshIcons();
    }
  }

  function initMap() {
    const host = document.getElementById("unified-map");
    map = L.map(host, { zoomControl: true, scrollWheelZoom: true }).setView([20.3, 84.8], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    setTimeout(() => map.invalidateSize(), 120);
  }

  function setupEvents() {
    BT.qsa("#layer-switch button").forEach((button) => {
      button.addEventListener("click", () => {
        state.layers = button.dataset.layer;
        BT.qsa("#layer-switch button").forEach((item) => {
          const active = item === button;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        load();
      });
    });
    document.getElementById("map-district").addEventListener("change", (event) => {
      state.district = event.target.value;
      load();
    });
    document.getElementById("map-status").addEventListener("change", (event) => {
      state.status = event.target.value;
      load();
    });
    document.getElementById("map-start").addEventListener("change", (event) => {
      state.start = event.target.value;
      load();
    });
    document.getElementById("map-end").addEventListener("change", (event) => {
      state.end = event.target.value;
      load();
    });
    const search = document.getElementById("map-search");
    const toolbarSearch = document.getElementById("map-toolbar-search");
    const onSearch = BT.debounce((value) => {
      state.q = value.trim();
      applySearch();
    }, 180);
    search.addEventListener("input", () => {
      toolbarSearch.value = search.value;
      onSearch(search.value);
    });
    toolbarSearch.addEventListener("input", () => {
      search.value = toolbarSearch.value;
      onSearch(toolbarSearch.value);
    });
    document.getElementById("map-fit").addEventListener("click", fitBounds);
    document.getElementById("map-locate").addEventListener("click", async () => {
      try {
        const position = await BT.geolocate();
        if (userMarker) map.removeLayer(userMarker);
        userMarker = L.circleMarker([position.lat, position.lon], {
          radius: 9,
          color: "#f4fff9",
          weight: 2,
          fillColor: "#16866a",
          fillOpacity: 1,
        }).addTo(map);
        userMarker.bindPopup(`<div class="map-popup"><h4>Your approximate location</h4><div class="tiny muted">Accuracy about ${Math.round(position.accuracy)} m. This marker is not stored.</div></div>`).openPopup();
        map.setView([position.lat, position.lon], 10);
      } catch (err) {
        BT.toast("Location unavailable", err.message, "error");
      }
    });
    document.getElementById("map-clear").addEventListener("click", () => {
      state.categories = [];
      state.district = "";
      state.status = "";
      state.start = "";
      state.end = "";
      state.q = "";
      state.layers = "combined";
      document.getElementById("map-district").value = "";
      document.getElementById("map-status").value = "";
      document.getElementById("map-start").value = "";
      document.getElementById("map-end").value = "";
      document.getElementById("map-search").value = "";
      document.getElementById("map-toolbar-search").value = "";
      BT.qsa("[data-map-category]").forEach((button) => {
        button.classList.remove("is-active");
        button.setAttribute("aria-pressed", "false");
      });
      BT.qsa("#layer-switch button").forEach((button) => {
        const active = button.dataset.layer === "combined";
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      load();
    });
  }

  async function init() {
    try {
      await BT.loadTaxonomy();
      buildControls();
      initMap();
      setupEvents();
      await load();
    } catch (err) {
      BT.errorToast(err);
    }
    BT.refreshIcons();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
