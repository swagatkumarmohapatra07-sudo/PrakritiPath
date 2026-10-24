/* ==========================================================================
   My Utkal Heritage — itinerary editor
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;
  let trip = null;
  let map = null;
  let markerLayer = null;
  let searchTimer = null;

  function stopMinutes(stop) {
    return stop.destination.estimated_visit_minutes || null;
  }

  function totalText() {
    if (!trip) return "";
    const known = trip.stops.map(stopMinutes).filter((value) => value !== null);
    if (!known.length) return "No visit-duration estimates recorded";
    return `${known.reduce((sum, value) => sum + value, 0)} min estimated for ${known.length} of ${trip.stops.length} stops`;
  }

  function render() {
    const root = document.getElementById("trip-root");
    const stops = trip.stops || [];
    root.innerHTML = `
      <div class="breadcrumbs">
        <a href="/">Home</a>${BT.icon("chevron-right")}
        <a href="/saved.html">Saved places & trips</a>${BT.icon("chevron-right")}
        <span>${BT.esc(trip.title)}</span>
      </div>
      <div class="trip-hero">
        <div>
          <span class="eyebrow">Personal itinerary</span>
          <h1>${BT.esc(trip.title)}</h1>
          <div class="trip-summary">
            <span>${BT.icon("calendar")}${trip.travel_date ? BT.fmtDate(trip.travel_date) : "No travel date"}</span>
            <span>${BT.icon("map-pin")}${stops.length} stop${stops.length === 1 ? "" : "s"}</span>
            <span>${BT.icon("clock")}${BT.esc(totalText())}</span>
          </div>
          ${trip.notes ? `<p class="small muted" style="margin-top:12px;max-width:720px">${BT.esc(trip.notes)}</p>` : ""}
        </div>
        <div class="row" style="gap:8px">
          <button class="btn btn-secondary btn-sm" id="edit-trip" type="button">${BT.icon("pencil-line")}Edit details</button>
          <button class="btn btn-secondary btn-sm" id="print-trip" type="button">${BT.icon("printer")}Print</button>
          <button class="btn btn-secondary btn-sm" id="copy-trip" type="button">${BT.icon("copy")}Copy plan</button>
          <button class="btn btn-danger btn-sm" id="delete-trip" type="button">${BT.icon("trash-2")}Delete</button>
        </div>
      </div>

      <div class="detail-layout">
        <div>
          <div class="detail-section">
            <div class="panel-head" style="margin-bottom:14px">
              <div>
                <h2 style="font-size:1.3rem;margin:0">Stops in order</h2>
                <p>Reorder with the arrow buttons. Save the order after adding notes.</p>
              </div>
              <button class="btn btn-secondary btn-sm" id="save-order" type="button">${BT.icon("save")}Save order & notes</button>
            </div>
            ${
              stops.length
                ? `<div id="stops-list">${stops
                    .map((stop, index) => {
                      const dest = stop.destination;
                      const meta = BT.category(dest.category);
                      return `<div class="trip-stop" data-stop-index="${index}">
                        <div class="row" style="align-items:flex-start;gap:12px">
                          <span class="trip-index">${index + 1}</span>
                          <div style="flex:1;min-width:0">
                            <div class="row-between" style="gap:8px;align-items:flex-start">
                              <div style="min-width:0">
                                <h4 style="margin:0 0 2px"><a href="/destination.html?slug=${encodeURIComponent(dest.slug)}" style="text-decoration:none;color:inherit">${BT.esc(dest.name)}</a></h4>
                                <p class="tiny muted" style="margin:0">
                                  ${BT.esc(meta.label)} · ${BT.esc([dest.city, dest.district].filter(Boolean).join(", ") || "Location not recorded")}
                                  ${stopMinutes(stop) !== null ? ` · ${stopMinutes(stop)} min estimate` : " · duration not recorded"}
                                </p>
                              </div>
                              <div class="trip-actions">
                                <button class="icon-btn" type="button" data-move-up="${index}" ${index === 0 ? "disabled" : ""} aria-label="Move ${BT.esc(dest.name)} up">${BT.icon("arrow-up")}</button>
                                <button class="icon-btn" type="button" data-move-down="${index}" ${index === stops.length - 1 ? "disabled" : ""} aria-label="Move ${BT.esc(dest.name)} down">${BT.icon("arrow-down")}</button>
                                <button class="icon-btn" type="button" data-remove-stop="${index}" aria-label="Remove ${BT.esc(dest.name)}" style="color:var(--danger)">${BT.icon("x")}</button>
                              </div>
                            </div>
                            <textarea class="textarea" data-stop-note="${index}" maxlength="1000" placeholder="Note for this stop (optional)">${BT.esc(stop.notes || "")}</textarea>
                          </div>
                        </div>
                      </div>`;
                    })
                    .join("")}</div>`
                : BT.emptyState(
                    "This itinerary is empty",
                    "Search for a destination below and add your first stop.",
                    "route"
                  )
            }
          </div>

          <div class="detail-section">
            <h2>Add a stop</h2>
            <div class="field" style="position:relative">
              <label for="stop-search">Search destinations</label>
              <div class="search-field">
                ${BT.icon("search")}
                <input class="input" id="stop-search" type="search" autocomplete="off" placeholder="Type a place name, district or category" />
              </div>
              <div id="stop-suggestions" class="suggestions hidden" role="listbox" aria-label="Destination suggestions"></div>
            </div>
            <p class="tiny muted" style="margin:0">A destination can only appear once in a trip. Adding a place stores the stop immediately.</p>
          </div>

          <div class="callout warning">
            ${BT.icon("alert-triangle")}
            <div><strong>Plan, don't promise.</strong> ${BT.esc(trip.disclaimer || "Opening hours, entry fees and travel times can change. Verify before you travel.")}</div>
          </div>
        </div>

        <div>
          <div class="detail-section">
            <h2>Plan map</h2>
            <div class="map-shell map-sm" id="trip-map" aria-label="Map of itinerary stops"></div>
            <p class="tiny muted" style="margin:10px 0 0">${BT.icon("info")} The line connects stops in order. It is a straight-line sketch, not a road route or travel-time estimate.</p>
          </div>
          <div class="detail-section">
            <h2>Trip checklist</h2>
            <div class="stack-sm">
              <div class="check-row ${stops.length ? "ok" : "warn"}">${BT.icon(stops.length ? "check-circle-2" : "circle")}<span>${stops.length ? `${stops.length} stop${stops.length === 1 ? "" : "s"} added` : "No stops yet"}</span></div>
              <div class="check-row ${trip.travel_date ? "ok" : "warn"}">${BT.icon(trip.travel_date ? "check-circle-2" : "circle")}<span>${trip.travel_date ? "Travel date set" : "Travel date not set"}</span></div>
              <div class="check-row warn">${BT.icon("alert-triangle")}<span>Verify opening hours, entry fees, accessibility and closures with each place.</span></div>
            </div>
          </div>
        </div>
      </div>`;
    bindEvents();
    renderMap();
    BT.refreshIcons();
  }

  function currentStops() {
    return (trip.stops || []).map((stop) => ({
      destination_id: stop.destination.id,
      notes: stop.notes || null,
    }));
  }

  async function persistStops(successMessage) {
    try {
      const updated = await BT.api(`/api/itineraries/${trip.id}`, {
        method: "PUT",
        body: { stops: currentStops() },
      });
      trip = updated;
      render();
      if (successMessage) BT.toast("Itinerary updated", successMessage, "success", 2600);
    } catch (err) {
      BT.errorToast(err);
      loadTrip(trip.id);
    }
  }

  function renderMap() {
    const host = document.getElementById("trip-map");
    if (!host || !window.L) return;
    if (map) {
      map.remove();
      map = null;
    }
    map = L.map(host, { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    const points = [];
    markerLayer = L.featureGroup();
    (trip.stops || []).forEach((stop, index) => {
      const dest = stop.destination;
      if (dest.latitude === null || dest.longitude === null || dest.latitude === undefined) return;
      points.push([dest.latitude, dest.longitude]);
      const icon = L.divIcon({
        className: "",
        html: `<div class="map-marker dest" style="background:#14523c"><span style="font-weight:800;font-size:.72rem">${index + 1}</span></div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 28],
        popupAnchor: [0, -26],
      });
      const marker = L.marker([dest.latitude, dest.longitude], { icon, title: dest.name });
      marker.bindPopup(
        `<div class="map-popup"><span class="popup-cat">Stop ${index + 1}</span><h4>${BT.esc(dest.name)}</h4>
         <a href="/destination.html?slug=${encodeURIComponent(dest.slug)}">View details</a></div>`
      );
      markerLayer.addLayer(marker);
    });
    map.addLayer(markerLayer);
    if (points.length > 1) {
      L.polyline(points, { color: "#16866a", weight: 2, dashArray: "6 6", opacity: 0.8 }).addTo(map);
    }
    if (points.length) {
      map.fitBounds(markerLayer.getBounds().pad(0.2));
    } else {
      map.setView([20.3, 84.8], 6);
    }
    setTimeout(() => map.invalidateSize(), 120);
  }

  function bindEvents() {
    const save = document.getElementById("save-order");
    if (save) {
      save.addEventListener("click", () => {
        BT.qsa("[data-stop-note]").forEach((area) => {
          const index = Number(area.dataset.stopNote);
          if (trip.stops[index]) trip.stops[index].notes = area.value.trim() || null;
        });
        persistStops("Stop order and notes saved.");
      });
    }
    BT.qsa("[data-move-up]").forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number(button.dataset.moveUp);
        if (index <= 0) return;
        const [item] = trip.stops.splice(index, 1);
        trip.stops.splice(index - 1, 0, item);
        persistStops();
      });
    });
    BT.qsa("[data-move-down]").forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number(button.dataset.moveDown);
        if (index >= trip.stops.length - 1) return;
        const [item] = trip.stops.splice(index, 1);
        trip.stops.splice(index + 1, 0, item);
        persistStops();
      });
    });
    BT.qsa("[data-remove-stop]").forEach((button) => {
      button.addEventListener("click", async () => {
        const index = Number(button.dataset.removeStop);
        const stop = trip.stops[index];
        const ok = await BT.confirm({
          title: "Remove this stop?",
          message: `${stop.destination.name} will be removed from this itinerary. The place itself is not deleted.`,
          confirmLabel: "Remove stop",
          danger: true,
        });
        if (!ok) return;
        trip.stops.splice(index, 1);
        persistStops("Stop removed.");
      });
    });
    document.getElementById("print-trip").addEventListener("click", () => window.print());
    document.getElementById("copy-trip").addEventListener("click", async () => {
      const lines = [
        trip.title,
        trip.travel_date ? `Date: ${BT.fmtDate(trip.travel_date)}` : "Date: not set",
        "",
        ...trip.stops.map(
          (stop, index) =>
            `${index + 1}. ${stop.destination.name}${stop.destination.district ? ` (${stop.destination.district})` : ""}${stop.notes ? ` — ${stop.notes}` : ""}`
        ),
        "",
        trip.disclaimer,
      ];
      const ok = await BT.copy(lines.join("\n"));
      BT.toast(ok ? "Plan copied" : "Copy failed", ok ? "The itinerary text is on your clipboard." : "Select the text manually.", ok ? "success" : "error");
    });
    document.getElementById("edit-trip").addEventListener("click", editModal);
    document.getElementById("delete-trip").addEventListener("click", async () => {
      const ok = await BT.confirm({
        title: "Delete this itinerary?",
        message: "The plan and its stop order will be removed permanently.",
        confirmLabel: "Delete itinerary",
        danger: true,
      });
      if (!ok) return;
      try {
        await BT.api(`/api/itineraries/${trip.id}`, { method: "DELETE" });
        BT.toast("Itinerary deleted", "", "success", 2600);
        window.location.href = "/saved.html";
      } catch (err) {
        BT.errorToast(err);
      }
    });
    setupSearch();
  }

  function setupSearch() {
    const input = document.getElementById("stop-search");
    const host = document.getElementById("stop-suggestions");
    if (!input || !host) return;
    input.addEventListener("input", () => {
      clearTimeout(searchTimer);
      const q = input.value.trim();
      if (q.length < 2) {
        host.classList.add("hidden");
        host.innerHTML = "";
        return;
      }
      searchTimer = setTimeout(async () => {
        try {
          const data = await BT.api(`/api/tourism/destinations?${new URLSearchParams({ q, page_size: "8", sort: "featured" }).toString()}`);
          if (!data.items.length) {
            host.innerHTML = `<div class="suggestion-empty">No destinations match “${BT.esc(q)}”.</div>`;
          } else {
            host.innerHTML = data.items
              .map(
                (item) => `<button class="suggestion" type="button" data-add-stop="${item.id}" data-add-name="${BT.esc(item.name)}">
                  <span class="suggestion-icon">${BT.icon(BT.category(item.category).icon)}</span>
                  <span class="suggestion-text"><strong>${BT.esc(item.name)}</strong><span>${BT.esc(BT.category(item.category).label)} · ${BT.esc(item.district || "district not recorded")}</span></span>
                </button>`
              )
              .join("");
          }
          host.classList.remove("hidden");
          BT.qsa("[data-add-stop]", host).forEach((button) => {
            button.addEventListener("click", () => addStop(Number(button.dataset.addStop), button.dataset.addName));
          });
          BT.refreshIcons();
        } catch (err) {
          BT.errorToast(err);
        }
      }, 240);
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest("#stop-suggestions") && !event.target.closest("#stop-search")) {
        host.classList.add("hidden");
      }
    });
  }

  async function addStop(destinationId, name) {
    if (trip.stops.some((stop) => stop.destination.id === destinationId)) {
      BT.toast("Already in this trip", `${name} is already a stop.`, "info");
      return;
    }
    if (trip.stops.length >= 30) {
      BT.toast("Stop limit reached", "An itinerary can contain at most 30 stops.", "error");
      return;
    }
    try {
      const updated = await BT.api(`/api/itineraries/${trip.id}`, {
        method: "PUT",
        body: {
          stops: currentStops().concat([{ destination_id: destinationId, notes: null }]),
        },
      });
      trip = updated;
      render();
      BT.toast("Stop added", `${name} was added to the end of the itinerary.`, "success");
    } catch (err) {
      BT.errorToast(err);
    }
  }

  function editModal() {
    const body = `
      <div class="field">
        <label for="edit-title">Trip title</label>
        <input class="input" id="edit-title" maxlength="160" value="${BT.esc(trip.title)}" />
      </div>
      <div class="field">
        <label for="edit-date">Travel date (optional)</label>
        <input class="input" id="edit-date" type="date" value="${trip.travel_date || ""}" />
      </div>
      <div class="field">
        <label for="edit-notes">Notes</label>
        <textarea class="textarea" id="edit-notes" maxlength="2000">${BT.esc(trip.notes || "")}</textarea>
      </div>`;
    const modal = BT.modal({
      title: "Edit itinerary details",
      body,
      footer: `<button class="btn btn-secondary" data-close type="button">Cancel</button>
               <button class="btn btn-primary" id="save-details" type="button">Save changes</button>`,
    });
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    const button = modal.element.querySelector("#save-details");
    button.addEventListener("click", async () => {
      const title = modal.element.querySelector("#edit-title").value.trim();
      if (title.length < 2) {
        BT.toast("Title required", "Enter at least 2 characters.", "error");
        return;
      }
      BT.setBusy(button, true, "Saving…");
      try {
        trip = await BT.api(`/api/itineraries/${trip.id}`, {
          method: "PUT",
          body: {
            title,
            travel_date: modal.element.querySelector("#edit-date").value || null,
            notes: modal.element.querySelector("#edit-notes").value.trim() || null,
          },
        });
        BT.closeModal();
        render();
        BT.toast("Details saved", "", "success", 2600);
      } catch (err) {
        BT.setBusy(button, false);
        BT.errorToast(err);
      }
    });
  }

  async function loadTrip(id) {
    try {
      trip = await BT.api(`/api/itineraries/${id}`);
      document.title = `${trip.title} — My Utkal Heritage itinerary`;
      render();
    } catch (err) {
      document.getElementById("trip-root").innerHTML = `<div class="state error" style="margin:60px auto">
        <div class="state-icon">${BT.icon("route")}</div>
        <h3>Itinerary not found</h3>
        <p>${BT.esc(err.message)}</p>
        <a class="btn btn-primary" href="/saved.html">Back to saved trips</a>
      </div>`;
      BT.refreshIcons();
      if (err.status !== 404) BT.errorToast(err);
    }
  }

  async function renderPicker() {
    try {
      const trips = await BT.api("/api/itineraries");
      const root = document.getElementById("trip-root");
      if (!trips.length) {
        root.innerHTML = `<div class="state">
          <div class="state-icon">${BT.icon("route")}</div>
          <h3>No itineraries yet</h3>
          <p>Create a trip from Saved Places, then add stops from destination pages.</p>
          <a class="btn btn-primary" href="/saved.html">Create an itinerary</a>
        </div>`;
        BT.refreshIcons();
        return;
      }
      root.innerHTML = `<span class="eyebrow">Your trips</span><h1>Choose an itinerary</h1>
        <div class="grid grid-2" style="margin-top:24px;max-width:860px">
          ${trips
            .map(
              (item) => `<a class="trip-card" href="/itinerary.html?id=${item.id}">
                <h4>${BT.esc(item.title)}</h4>
                <p>${item.stops.length} stop${item.stops.length === 1 ? "" : "s"} · ${item.travel_date ? BT.fmtDate(item.travel_date) : "no date"}</p>
              </a>`
            )
            .join("")}
        </div>`;
      BT.refreshIcons();
    } catch (err) {
      BT.errorToast(err);
    }
  }

  async function init() {
    await BT.loadTaxonomy();
    const id = new URLSearchParams(location.search).get("id");
    if (!id) {
      renderPicker();
      return;
    }
    loadTrip(id);
    BT.refreshIcons();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
