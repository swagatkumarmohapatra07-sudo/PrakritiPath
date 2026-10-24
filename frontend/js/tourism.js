/* ==========================================================================
   BioTrace — tourism explorer
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;
  const PAGE_SIZE = 12;

  const state = {
    q: "",
    categories: [],
    district: "",
    facility: "",
    accessible: false,
    coords: false,
    sort: "featured",
    page: 1,
    view: "grid",
    near: null,
  };

  let map = null;
  let markerLayer = null;

  function readUrl() {
    const params = new URLSearchParams(location.search);
    state.q = params.get("q") || "";
    state.categories = params.getAll("category").filter(Boolean);
    state.district = params.get("district") || "";
    state.facility = params.get("facility") || "";
    state.accessible = params.get("accessible") === "1";
    state.coords = params.get("coords") === "1";
    state.sort = ["featured", "name", "district", "newest"].includes(params.get("sort"))
      ? params.get("sort")
      : "featured";
    state.page = Math.max(1, Number(params.get("page") || 1));
    state.view = params.get("view") === "map" ? "map" : "grid";
    state.near = null;
  }

  function writeUrl() {
    const params = new URLSearchParams();
    if (state.q) params.set("q", state.q);
    state.categories.forEach((slug) => params.append("category", slug));
    if (state.district) params.set("district", state.district);
    if (state.facility) params.set("facility", state.facility);
    if (state.accessible) params.set("accessible", "1");
    if (state.coords) params.set("coords", "1");
    if (state.sort !== "featured") params.set("sort", state.sort);
    if (state.page > 1) params.set("page", String(state.page));
    if (state.view === "map") params.set("view", "map");
    const query = params.toString();
    history.replaceState(null, "", query ? `?${query}` : location.pathname);
  }

  function buildCategoryFilters() {
    const host = document.getElementById("filter-categories");
    if (!host) return;
    const categories = (BT.taxonomy && BT.taxonomy.categories) || [];
    const groups = (BT.taxonomy && BT.taxonomy.groups) || [];
    host.innerHTML = groups
      .map((group) => {
        const items = categories.filter((item) => item.group === group);
        if (!items.length) return "";
        return `<div class="filter-group" style="border:0;padding:8px 0 0">
          <h4>${BT.esc(group)}</h4>
          ${items
            .map(
              (item) => `<label class="checkbox">
                <input type="checkbox" value="${BT.esc(item.slug)}" data-category-filter />
                <span>${BT.esc(item.label)} <span class="count">${BT.num(item.count)}</span></span>
              </label>`
            )
            .join("")}
        </div>`;
      })
      .join("");
    BT.qsa("[data-category-filter]").forEach((input) => {
      input.addEventListener("change", () => {
        state.categories = BT.qsa("[data-category-filter]:checked").map((item) => item.value);
        state.page = 1;
        state.near = null;
        apply();
      });
    });
  }

  function buildDistrictOptions() {
    const select = document.getElementById("filter-district");
    if (!select) return;
    (BT.taxonomy.districts || []).forEach((district) => {
      const option = document.createElement("option");
      option.value = district;
      option.textContent = district;
      select.appendChild(option);
    });
  }

  function syncControls() {
    const q = document.getElementById("filter-q");
    const toolbarQ = document.getElementById("toolbar-q");
    if (q) q.value = state.q;
    if (toolbarQ) toolbarQ.value = state.q;
    document.getElementById("filter-district").value = state.district;
    document.getElementById("filter-facility").value = state.facility;
    document.getElementById("filter-accessible").checked = state.accessible;
    document.getElementById("filter-coords").checked = state.coords;
    document.getElementById("sort-select").value = state.sort;
    BT.qsa("[data-category-filter]").forEach((input) => {
      input.checked = state.categories.includes(input.value);
    });
    BT.qsa("#view-switch button").forEach((button) => {
      const active = button.dataset.view === state.view;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.getElementById("grid-view").classList.toggle("hidden", state.view === "map");
    document.getElementById("map-view").classList.toggle("hidden", state.view !== "map");
  }

  function categoryLabel(slug) {
    return BT.category(slug).label || slug;
  }

  function renderActiveFilters() {
    const host = document.getElementById("active-filters");
    if (!host) return;
    const chips = [];
    if (state.q) chips.push(["q", state.q, `Search: “${state.q}”`]);
    state.categories.forEach((slug) => chips.push(["category", slug, categoryLabel(slug)]));
    if (state.district) chips.push(["district", state.district, state.district]);
    if (state.facility) chips.push(["facility", state.facility, `Facility: ${state.facility}`]);
    if (state.accessible) chips.push(["accessible", "", "Accessibility recorded"]);
    if (state.coords) chips.push(["coords", "", "Has coordinates"]);
    if (state.near) chips.push(["near", "", "Near my location"]);
    host.innerHTML = chips
      .map(
        ([type, value, label]) => `<span class="chip is-active">${BT.esc(label)}
          <button class="active-filter" type="button" data-filter-type="${type}" data-filter-value="${BT.esc(value)}" aria-label="Remove ${BT.esc(label)} filter">
            ${BT.icon("x")}
          </button>
        </span>`
      )
      .join("");
    BT.qsa(".active-filter", host).forEach((button) => {
      button.addEventListener("click", () => removeFilter(button.dataset.filterType, button.dataset.filterValue));
    });
    BT.refreshIcons();
  }

  function removeFilter(type, value) {
    if (type === "q") {
      state.q = "";
      document.getElementById("filter-q").value = "";
      document.getElementById("toolbar-q").value = "";
    } else if (type === "category") {
      state.categories = state.categories.filter((item) => item !== value);
    } else if (type === "district") {
      state.district = "";
      document.getElementById("filter-district").value = "";
    } else if (type === "facility") {
      state.facility = "";
      document.getElementById("filter-facility").value = "";
    } else if (type === "accessible") {
      state.accessible = false;
      document.getElementById("filter-accessible").checked = false;
    } else if (type === "coords") {
      state.coords = false;
      document.getElementById("filter-coords").checked = false;
    } else if (type === "near") {
      state.near = null;
    }
    state.page = 1;
    apply();
  }

  function apply() {
    syncControls();
    writeUrl();
    renderActiveFilters();
    fetchResults();
  }

  function queryParams(overrides = {}) {
    const params = new URLSearchParams();
    if (state.q) params.set("q", state.q);
    state.categories.forEach((slug) => params.append("category", slug));
    if (state.district) params.set("district", state.district);
    if (state.facility) params.set("facility", state.facility);
    if (state.accessible) params.set("accessible", "true");
    if (state.coords) params.set("has_coordinates", "true");
    Object.entries(overrides).forEach(([key, value]) => {
      if (value === undefined || value === null) params.delete(key);
      else params.set(key, String(value));
    });
    return params;
  }

  function nearbyCard(item) {
    const meta = BT.category(item.category);
    const place = [item.city, item.district].filter(Boolean).join(", ");
    return `<article class="card">
      <a class="card-link" href="/destination.html?slug=${encodeURIComponent(item.slug)}">
        <div class="card-media">${BT.categoryArt(item.category)}
          <span class="card-flag">${BT.icon("locate-fixed")}${item.distance_km} km away</span>
        </div>
        <div class="card-body">
          <div class="card-kicker">${BT.icon(meta.icon)}${BT.esc(meta.label)}</div>
          <h3 class="card-title">${BT.esc(item.name)}</h3>
          <p class="card-copy">${BT.esc(place || "District not recorded")} · Distance is a straight line, not a travel route.</p>
          <div class="card-footer">
            <span class="chip">${BT.icon("navigation")}${item.distance_km} km</span>
            <span class="small strong" style="color:var(--emerald-deep)">Details ${BT.icon("arrow-right")}</span>
          </div>
        </div>
      </a>
    </article>`;
  }

  function renderPagination(total) {
    const host = document.getElementById("tourism-pagination");
    if (!host) return;
    const pages = Math.ceil(total / PAGE_SIZE);
    if (pages <= 1 || state.near) {
      host.innerHTML = "";
      return;
    }
    const buttons = [];
    buttons.push(`<button type="button" data-page="${state.page - 1}" ${state.page <= 1 ? "disabled" : ""} aria-label="Previous page">${BT.icon("chevron-left")}</button>`);
    const windowStart = Math.max(1, Math.min(state.page - 2, pages - 4));
    const windowEnd = Math.min(pages, windowStart + 4);
    for (let page = windowStart; page <= windowEnd; page += 1) {
      buttons.push(`<button type="button" data-page="${page}" class="${page === state.page ? "is-active" : ""}" aria-label="Page ${page}" ${page === state.page ? 'aria-current="page"' : ""}>${page}</button>`);
    }
    buttons.push(`<button type="button" data-page="${state.page + 1}" ${state.page >= pages ? "disabled" : ""} aria-label="Next page">${BT.icon("chevron-right")}</button>`);
    host.innerHTML = `<span class="page-info">Page ${state.page} of ${pages}</span>${buttons.join("")}`;
    BT.qsa("button[data-page]", host).forEach((button) => {
      button.addEventListener("click", () => {
        const page = Number(button.dataset.page);
        if (page < 1 || page > pages) return;
        state.page = page;
        apply();
        document.getElementById("tourism-results").scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    BT.refreshIcons();
  }

  async function fetchResults() {
    const host = document.getElementById("tourism-results");
    const count = document.getElementById("results-count");
    const note = document.getElementById("results-note");
    host.innerHTML = BT.skeletonCards(3);
    count.textContent = "Loading destinations…";
    note.textContent = "Records are provisional unless marked verified.";

    try {
      if (state.near) {
        const params = new URLSearchParams({
          lat: String(state.near.lat),
          lon: String(state.near.lon),
          radius_km: "75",
          limit: "24",
        });
        state.categories.forEach((slug) => params.append("category", slug));
        const rows = await BT.api(`/api/tourism/nearby?${params.toString()}`);
        count.textContent = `${rows.length} place${rows.length === 1 ? "" : "s"} within 75 km`;
        note.textContent = "Sorted by straight-line distance from your device. No route or travel time is implied.";
        host.innerHTML = rows.length
          ? rows.map(nearbyCard).join("")
          : BT.emptyState("Nothing nearby in the catalogue", "The seed catalogue may not cover this area yet. Try clearing the location filter or widening your search.", "map-pin-off");
        document.getElementById("tourism-pagination").innerHTML = "";
        if (state.view === "map") renderMap();
        BT.refreshIcons();
        return;
      }

      const params = queryParams({
        sort: state.sort,
        page: state.page,
        page_size: PAGE_SIZE,
      });
      const data = await BT.api(`/api/tourism/destinations?${params.toString()}`);
      count.textContent = `${BT.num(data.total)} place${data.total === 1 ? "" : "s"} found`;
      note.textContent = data.total
        ? `Showing ${(data.page - 1) * data.page_size + 1}–${Math.min(data.page * data.page_size, data.total)} · seed catalogue, provisional unless verified.`
        : "No records match the current filters.";
      host.innerHTML = data.items.length
        ? data.items.map((item) => BT.destinationCard(item)).join("")
        : BT.emptyState(
            "No destinations match",
            "Try removing a filter or searching for a district such as Khordha, Puri or Ganjam.",
            "search",
            `<button class="btn btn-secondary" id="empty-clear" type="button">Clear filters</button>`
          );
      const clear = document.getElementById("empty-clear");
      if (clear) clear.addEventListener("click", clearFilters);
      renderPagination(data.total);
      if (state.view === "map") renderMap();
    } catch (err) {
      host.innerHTML = BT.emptyState(
        "The catalogue could not load",
        "Check that the BioTrace server is running, then try again.",
        "cloud-off",
        `<button class="btn btn-secondary" id="retry-results" type="button">Try again</button>`
      );
      const retry = document.getElementById("retry-results");
      if (retry) retry.addEventListener("click", fetchResults);
      count.textContent = "Could not load destinations";
      BT.errorToast(err);
    }
    BT.refreshIcons();
  }

  function renderMap() {
    const host = document.getElementById("tourism-map");
    if (!host || !window.L) {
      if (host) host.innerHTML = `<div class="map-fallback">Map library failed to load.</div>`;
      return;
    }
    if (!map) {
      map = L.map(host, { scrollWheelZoom: true });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);
      map.setView([20.3, 84.8], 6);
    }
    setTimeout(() => map.invalidateSize(), 80);
    if (markerLayer) {
      map.removeLayer(markerLayer);
      markerLayer = null;
    }
    markerLayer = window.L.markerClusterGroup ? L.markerClusterGroup({ maxClusterRadius: 46 }) : L.featureGroup();
    const params = queryParams({ page: 1, page_size: 100 });
    BT.api(`/api/tourism/destinations?${params.toString()}`)
      .then((data) => {
        const points = data.items.filter((item) => item.latitude !== null && item.longitude !== null);
        points.forEach((item) => {
          const meta = BT.category(item.category);
          const icon = L.divIcon({
            className: "",
            html: `<div class="map-marker dest"><span>${BT.icon(meta.icon)}</span></div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 28],
            popupAnchor: [0, -26],
          });
          const marker = L.marker([item.latitude, item.longitude], { icon, title: item.name });
          marker.bindPopup(
            `<div class="map-popup">
              <span class="popup-cat">${BT.esc(meta.label)}</span>
              <h4>${BT.esc(item.name)}</h4>
              <div class="tiny muted">${BT.esc([item.city, item.district].filter(Boolean).join(", ") || "Location recorded")}</div>
              <a href="/destination.html?slug=${encodeURIComponent(item.slug)}">View details</a>
            </div>`
          );
          markerLayer.addLayer(marker);
        });
        map.addLayer(markerLayer);
        if (points.length) map.fitBounds(markerLayer.getBounds().pad(0.15));
        else map.setView([20.3, 84.8], 6);
        document.getElementById("map-note").textContent = `${points.length} place${points.length === 1 ? "" : "s"} with coordinates match the current filters. Records without reliable coordinates remain in the grid view.`;
        BT.refreshIcons();
      })
      .catch((err) => {
        document.getElementById("map-note").textContent = "The map data could not be loaded. Try the grid view.";
        BT.errorToast(err);
      });
  }

  function clearFilters() {
    state.q = "";
    state.categories = [];
    state.district = "";
    state.facility = "";
    state.accessible = false;
    state.coords = false;
    state.sort = "featured";
    state.page = 1;
    state.near = null;
    apply();
  }

  function setupEvents() {
    const filterQ = document.getElementById("filter-q");
    const toolbarQ = document.getElementById("toolbar-q");
    const onSearch = BT.debounce((value) => {
      state.q = value.trim();
      state.page = 1;
      state.near = null;
      apply();
    }, 260);
    filterQ.addEventListener("input", () => {
      toolbarQ.value = filterQ.value;
      onSearch(filterQ.value);
    });
    toolbarQ.addEventListener("input", () => {
      filterQ.value = toolbarQ.value;
      onSearch(toolbarQ.value);
    });

    document.getElementById("filter-district").addEventListener("change", (event) => {
      state.district = event.target.value;
      state.page = 1;
      state.near = null;
      apply();
    });
    document.getElementById("filter-facility").addEventListener("change", (event) => {
      state.facility = event.target.value;
      state.page = 1;
      state.near = null;
      apply();
    });
    document.getElementById("filter-accessible").addEventListener("change", (event) => {
      state.accessible = event.target.checked;
      state.page = 1;
      state.near = null;
      apply();
    });
    document.getElementById("filter-coords").addEventListener("change", (event) => {
      state.coords = event.target.checked;
      state.page = 1;
      state.near = null;
      apply();
    });
    document.getElementById("sort-select").addEventListener("change", (event) => {
      state.sort = event.target.value;
      state.page = 1;
      apply();
    });
    BT.qsa("#view-switch button").forEach((button) => {
      button.addEventListener("click", () => {
        state.view = button.dataset.view;
        apply();
        if (state.view === "map") renderMap();
      });
    });
    document.getElementById("clear-filters").addEventListener("click", clearFilters);

    const sidebar = document.getElementById("filter-sidebar");
    const filterBackdrop = document.getElementById("filter-backdrop");
    const filterToggle = document.getElementById("mobile-filter");
    const openFilters = () => {
      sidebar.classList.add("is-open");
      if (filterBackdrop) {
        filterBackdrop.classList.remove("hidden");
        filterBackdrop.setAttribute("aria-hidden", "false");
      }
      document.body.classList.add("filter-open");
      filterToggle.setAttribute("aria-expanded", "true");
      const close = document.getElementById("filter-close");
      if (close) close.focus();
    };
    const closeFilters = () => {
      sidebar.classList.remove("is-open");
      if (filterBackdrop) {
        filterBackdrop.classList.add("hidden");
        filterBackdrop.setAttribute("aria-hidden", "true");
      }
      document.body.classList.remove("filter-open");
      filterToggle.setAttribute("aria-expanded", "false");
    };
    filterToggle.setAttribute("aria-expanded", "false");
    filterToggle.addEventListener("click", () => {
      if (sidebar.classList.contains("is-open")) closeFilters();
      else openFilters();
    });
    if (filterBackdrop) filterBackdrop.addEventListener("click", closeFilters);
    const filterClose = document.getElementById("filter-close");
    if (filterClose) filterClose.addEventListener("click", closeFilters);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && sidebar.classList.contains("is-open")) closeFilters();
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) closeFilters();
    });
    document.getElementById("near-me").addEventListener("click", async () => {
      const button = document.getElementById("near-me");
      BT.setBusy(button, true, "Locating…");
      try {
        const position = await BT.geolocate();
        state.near = { lat: position.lat, lon: position.lon };
        state.page = 1;
        BT.toast("Location added", `Showing places within 75 km. Accuracy about ${Math.round(position.accuracy)} m.`, "success");
        apply();
      } catch (err) {
        BT.toast("Location unavailable", err.message, "error");
      } finally {
        BT.setBusy(button, false);
      }
    });
    window.addEventListener("popstate", () => {
      readUrl();
      syncControls();
      renderActiveFilters();
      fetchResults();
    });
  }

  function suggestionModal() {
    const categories = (BT.taxonomy && BT.taxonomy.categories) || [];
    const districts = (BT.taxonomy && BT.taxonomy.districts) || [];
    const body = `
      <div class="callout info" style="margin-bottom:16px">${BT.icon("info")}
        <div>Suggestions enter a review queue. They do <strong>not</strong> appear publicly until a reviewer checks the source and details.</div>
      </div>
      <div class="field">
        <label for="suggest-name">Place name</label>
        <input class="input" id="suggest-name" maxlength="200" placeholder="e.g. A temple, museum, beach or park" />
      </div>
      <div class="grid grid-2" style="gap:12px">
        <div class="field">
          <label for="suggest-category">Category</label>
          <select class="select" id="suggest-category">
            ${categories.map((item) => `<option value="${BT.esc(item.slug)}">${BT.esc(item.label)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="suggest-district">District</label>
          <select class="select" id="suggest-district">
            <option value="">Not sure</option>
            ${districts.map((name) => `<option value="${BT.esc(name)}">${BT.esc(name)}</option>`).join("")}
          </select>
        </div>
      </div>
      <div class="field">
        <label for="suggest-city">City or locality (optional)</label>
        <input class="input" id="suggest-city" maxlength="120" />
      </div>
      <div class="field">
        <label for="suggest-description">Why should it be listed?</label>
        <textarea class="textarea" id="suggest-description" maxlength="2000" placeholder="A short description and what makes it notable."></textarea>
      </div>
      <div class="field">
        <label for="suggest-source">Source URL (strongly recommended)</label>
        <input class="input" id="suggest-source" type="url" maxlength="500" placeholder="https://…" />
        <span class="field-hint">An official site, district page, ASI listing or reputable source helps a reviewer verify it.</span>
      </div>
      <div class="field">
        <label for="suggest-contact">Contact (optional)</label>
        <input class="input" id="suggest-contact" maxlength="200" placeholder="Only if you are happy for reviewers to see it" />
      </div>
      <label class="checkbox">
        <input type="checkbox" id="suggest-consent" />
        <span>I consent to reviewers storing this suggestion and contacting me if needed.</span>
      </label>`;
    const modal = BT.modal({
      title: "Suggest a place",
      subtitle: "Help improve the Odisha catalogue.",
      body,
      size: "lg",
      footer: `<button class="btn btn-secondary" data-close type="button">Cancel</button>
               <button class="btn btn-primary" id="suggest-submit" type="button">Submit suggestion</button>`,
    });
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    const submit = modal.element.querySelector("#suggest-submit");
    submit.addEventListener("click", async () => {
      const name = modal.element.querySelector("#suggest-name").value.trim();
      const consent = modal.element.querySelector("#suggest-consent").checked;
      if (name.length < 3) {
        BT.toast("Name required", "Enter at least 3 characters for the place name.", "error");
        return;
      }
      if (!consent) {
        BT.toast("Consent required", "Tick the consent box so reviewers may follow up.", "error");
        return;
      }
      BT.setBusy(submit, true, "Sending…");
      try {
        const result = await BT.api("/api/tourism/suggestions", {
          method: "POST",
          body: {
            name,
            category: modal.element.querySelector("#suggest-category").value,
            district: modal.element.querySelector("#suggest-district").value || null,
            city: modal.element.querySelector("#suggest-city").value.trim() || null,
            description: modal.element.querySelector("#suggest-description").value.trim() || null,
            source_url: modal.element.querySelector("#suggest-source").value.trim() || null,
            submitter_contact: modal.element.querySelector("#suggest-contact").value.trim() || null,
            consent: true,
          },
        });
        BT.closeModal();
        BT.toast("Suggestion queued", result.message, "success", 7000);
      } catch (err) {
        BT.setBusy(submit, false);
        BT.errorToast(err);
      }
    });
  }

  async function init() {
    readUrl();
    try {
      await BT.loadTaxonomy();
      await BT.loadFavourites();
      buildCategoryFilters();
      buildDistrictOptions();
      syncControls();
      setupEvents();
      renderActiveFilters();
      fetchResults();
      if (state.view === "map") renderMap();
    } catch (err) {
      BT.errorToast(err);
    }
    document.getElementById("suggest-place").addEventListener("click", suggestionModal);
    const grid = document.getElementById("tourism-results");
    if (grid) BT.bindDestinationCards(grid);
    BT.refreshIcons();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
