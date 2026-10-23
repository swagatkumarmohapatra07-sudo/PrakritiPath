/* ==========================================================================
   BioTrace — saved places and itinerary index
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;

  function renderSaved() {
    const host = document.getElementById("saved-grid");
    const count = document.getElementById("saved-count");
    const rows = (BT.favouritesCache || []).slice();
    if (!rows.length) {
      if (count) count.textContent = "No places saved yet.";
      host.innerHTML = BT.emptyState(
        "Nothing saved yet",
        "Tap the heart on any destination card to keep it here. Saved places are stored in this browser session.",
        "heart",
        `<a class="btn btn-primary" href="/tourism.html">${BT.icon("compass")}Browse destinations</a>`
      );
      BT.refreshIcons();
      return;
    }
    if (count) count.textContent = `${rows.length} place${rows.length === 1 ? "" : "s"} in this session.`;
    host.innerHTML = rows.map((row) => BT.destinationCard(row.destination)).join("");
    BT.refreshIcons();
  }

  function renderTrips(trips) {
    const host = document.getElementById("trips-list");
    if (!trips.length) {
      host.innerHTML = BT.emptyState(
        "No itineraries yet",
        "Create a trip, then add stops from any destination page or from this planner.",
        "route",
        `<button class="btn btn-primary" id="empty-new-trip" type="button">${BT.icon("plus")}Create an itinerary</button>`
      );
      const button = document.getElementById("empty-new-trip");
      if (button) button.addEventListener("click", newTripModal);
      BT.refreshIcons();
      return;
    }
    host.innerHTML = trips
      .map((trip) => {
        const total = trip.total_estimated_minutes
          ? `${Math.floor(trip.total_estimated_minutes / 60)} h ${trip.total_estimated_minutes % 60} min estimated`
          : "Visit duration not fully estimated";
        return `<div class="trip-card">
          <div class="row-between" style="align-items:flex-start;gap:10px">
            <a href="/itinerary.html?id=${trip.id}" style="text-decoration:none;color:inherit;flex:1;min-width:0">
              <h4>${BT.esc(trip.title)}</h4>
              <p>${trip.stops.length} stop${trip.stops.length === 1 ? "" : "s"} · ${BT.esc(total)}</p>
              <div class="trip-meta">
                <span>${BT.icon("calendar")}${trip.travel_date ? BT.fmtDate(trip.travel_date) : "No travel date"}</span>
                <span>${BT.icon("clock")}Updated ${BT.relative(trip.created_at)}</span>
              </div>
            </a>
            <div class="trip-actions">
              <button class="icon-btn" type="button" data-delete-trip="${trip.id}" data-trip-title="${BT.esc(trip.title)}" aria-label="Delete ${BT.esc(trip.title)}">
                ${BT.icon("trash-2")}
              </button>
            </div>
          </div>
        </div>`;
      })
      .join("");
    BT.qsa("[data-delete-trip]", host).forEach((button) => {
      button.addEventListener("click", async () => {
        const id = Number(button.dataset.deleteTrip);
        const title = button.dataset.tripTitle;
        const ok = await BT.confirm({
          title: "Delete this itinerary?",
          message: `“${title}” and its stop order will be removed. This cannot be undone.`,
          confirmLabel: "Delete itinerary",
          danger: true,
        });
        if (!ok) return;
        try {
          await BT.api(`/api/itineraries/${id}`, { method: "DELETE" });
          BT.toast("Itinerary deleted", "", "success", 2800);
          loadTrips();
        } catch (err) {
          BT.errorToast(err);
        }
      });
    });
    BT.refreshIcons();
  }

  async function loadTrips() {
    try {
      const trips = await BT.api("/api/itineraries");
      renderTrips(trips);
    } catch (err) {
      document.getElementById("trips-list").innerHTML = BT.emptyState(
        "Itineraries could not load",
        err.message,
        "cloud-off",
        `<button class="btn btn-secondary" id="retry-trips" type="button">Try again</button>`
      );
      const retry = document.getElementById("retry-trips");
      if (retry) retry.addEventListener("click", loadTrips);
      BT.refreshIcons();
    }
  }

  function newTripModal() {
    const body = `
      <div class="field">
        <label for="new-trip-title">Trip title</label>
        <input class="input" id="new-trip-title" maxlength="160" placeholder="e.g. Bhubaneswar heritage weekend" />
      </div>
      <div class="field">
        <label for="new-trip-date">Travel date (optional)</label>
        <input class="input" id="new-trip-date" type="date" />
      </div>
      <div class="field">
        <label for="new-trip-notes">Notes (optional)</label>
        <textarea class="textarea" id="new-trip-notes" maxlength="2000" placeholder="What do you want to see? Any constraints?"></textarea>
      </div>
      <div class="callout neutral">${BT.icon("info")}<div>You can add stops from any destination page or from the itinerary editor. Stops are ordered manually.</div></div>`;
    const modal = BT.modal({
      title: "Create an itinerary",
      subtitle: "A private plan for this browser session.",
      body,
      footer: `<button class="btn btn-secondary" data-close type="button">Cancel</button>
               <button class="btn btn-primary" id="create-trip" type="button">Create itinerary</button>`,
    });
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    const button = modal.element.querySelector("#create-trip");
    button.addEventListener("click", async () => {
      const title = modal.element.querySelector("#new-trip-title").value.trim();
      if (title.length < 2) {
        BT.toast("Title required", "Give the itinerary a title of at least 2 characters.", "error");
        return;
      }
      BT.setBusy(button, true, "Creating…");
      try {
        const trip = await BT.api("/api/itineraries", {
          method: "POST",
          body: {
            title,
            travel_date: modal.element.querySelector("#new-trip-date").value || null,
            notes: modal.element.querySelector("#new-trip-notes").value.trim() || null,
            stops: [],
          },
        });
        window.location.href = `/itinerary.html?id=${trip.id}`;
      } catch (err) {
        BT.setBusy(button, false);
        BT.errorToast(err);
      }
    });
  }

  async function init() {
    document.getElementById("new-trip").addEventListener("click", newTripModal);
    await BT.loadFavourites();
    renderSaved();
    await loadTrips();
    const grid = document.getElementById("saved-grid");
    if (grid) BT.bindDestinationCards(grid);
    window.addEventListener("biotrace:favourites-changed", renderSaved);
    window.addEventListener("biotrace:trip-updated", loadTrips);
    BT.refreshIcons();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
