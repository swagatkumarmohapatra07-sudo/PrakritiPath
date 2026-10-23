/* ==========================================================================
   BioTrace — shared UI components: destination cards, favourites, reports,
   observation cards, trip planner modal and comparison.
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;

  /* ---------------------------------------------------------- Destination card */
  BT.destinationCard = function (dest, options = {}) {
    const meta = BT.category(dest.category);
    const saved = BT.favouriteIds && BT.favouriteIds.has(dest.id);
    const place = [dest.locality, dest.city, dest.district].filter(Boolean).slice(0, 2).join(", ");
    const tags = (dest.tags || []).slice(0, 2);
    return `<article class="card destination-card" data-destination-id="${dest.id}">
      <a class="card-link" href="/destination.html?slug=${encodeURIComponent(dest.slug)}" aria-label="View ${BT.esc(dest.name)}">
        <div class="card-media">
          ${BT.categoryArt(dest.category)}
          ${dest.featured ? `<span class="card-flag">${BT.icon("sparkles")}Featured</span>` : ""}
          <span class="save-btn ${saved ? "is-saved" : ""}" role="button" tabindex="0"
                data-save-id="${dest.id}" aria-label="${saved ? "Remove from saved places" : "Save place"}"
                aria-pressed="${saved ? "true" : "false"}">
            <i data-lucide="heart" aria-hidden="true"></i>
          </span>
          <span class="save-btn compare-btn" role="button" tabindex="0"
                data-compare-id="${dest.id}" aria-label="Add ${BT.esc(dest.name)} to comparison"
                aria-pressed="false" title="Compare this place">
            <i data-lucide="columns-3" aria-hidden="true"></i>
          </span>
        </div>
        <div class="card-body">
          <div class="card-kicker">${BT.icon(meta.icon)}${BT.esc(meta.label || dest.category)}</div>
          <h3 class="card-title">${BT.esc(dest.name)}</h3>
          <p class="card-copy">${BT.esc(dest.description || "No description recorded yet. Open the detail page for verified visitor information.")}</p>
          <div class="card-meta">
            ${place ? `${BT.icon("map-pin")}<span>${BT.esc(place)}</span>` : `<span>Location not recorded</span>`}
            ${dest.verification_status ? `<span class="dot-sep"></span>${BT.statusBadge(dest.verification_status)}` : ""}
          </div>
          <div class="card-footer">
            <div class="row" style="gap:6px">
              ${tags.map((tag) => `<span class="chip">${BT.esc(tag.replace(/_/g, " "))}</span>`).join("")}
            </div>
            <span class="small strong" style="color:var(--emerald-deep);display:inline-flex;align-items:center;gap:4px">
              Details ${BT.icon("arrow-right")}
            </span>
          </div>
        </div>
      </a>
    </article>`;
  };

  BT.bindDestinationCards = function (root) {
    if (!root) return;
    root.addEventListener("click", async (event) => {
      const save = event.target.closest("[data-save-id]");
      if (save) {
        event.preventDefault();
        event.stopPropagation();
        await BT.toggleFavourite(Number(save.dataset.saveId), save);
      }
      const compare = event.target.closest("[data-compare-id]");
      if (compare) {
        event.preventDefault();
        event.stopPropagation();
        BT.toggleCompare(Number(compare.dataset.compareId), compare);
      }
    });
    root.addEventListener("keydown", (event) => {
      const save = event.target.closest("[data-save-id]");
      if (save && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        BT.toggleFavourite(Number(save.dataset.saveId), save);
      }
    });
  };

  /* -------------------------------------------------------------- Favourites */
  BT.loadFavourites = async function () {
    try {
      const rows = await BT.api("/api/favourites");
      BT.favouriteIds = new Set(rows.map((row) => row.destination.id));
      BT.favouritesCache = rows;
    } catch (err) {
      BT.favouriteIds = BT.favouriteIds || new Set();
      BT.favouritesCache = BT.favouritesCache || [];
    }
    return BT.favouriteIds;
  };

  BT.toggleFavourite = async function (destinationId, button) {
    const isSaved = BT.favouriteIds && BT.favouriteIds.has(destinationId);
    try {
      if (isSaved) {
        await BT.api(`/api/favourites/${destinationId}`, { method: "DELETE" });
        BT.favouriteIds.delete(destinationId);
        if (BT.favouritesCache) {
          BT.favouritesCache = BT.favouritesCache.filter((row) => row.destination.id !== destinationId);
        }
        BT.toast("Removed from saved places", "", "info", 2600);
      } else {
        await BT.api(`/api/favourites/${destinationId}`, { method: "POST" });
        BT.favouriteIds.add(destinationId);
        BT.toast("Saved", "Find it under Saved Places.", "success", 2600);
      }
      if (button) {
        const nowSaved = BT.favouriteIds.has(destinationId);
        button.classList.toggle("is-saved", nowSaved);
        button.setAttribute("aria-pressed", String(nowSaved));
        button.setAttribute("aria-label", nowSaved ? "Remove from saved places" : "Save place");
      }
      window.dispatchEvent(
        new CustomEvent("biotrace:favourites-changed", { detail: { destinationId, saved: BT.favouriteIds.has(destinationId) } })
      );
    } catch (err) {
      BT.errorToast(err);
    }
  };

  /* ----------------------------------------------------------- Report dialog */
  BT.reportModal = function ({ recordType, recordId, label, reasons, title }) {
    const defaults = {
      observation: [
        ["incorrect_identification", "The identification looks wrong"],
        ["wrong_location", "The location is wrong"],
        ["duplicate", "This is a duplicate"],
        ["low_quality", "Image or evidence is inadequate"],
        ["other", "Something else"],
      ],
      destination: [
        ["incorrect_information", "Incorrect information"],
        ["closed", "Place appears closed or inaccessible"],
        ["wrong_location", "Wrong map location"],
        ["outdated", "Opening hours or fees are outdated"],
        ["other", "Something else"],
      ],
      prediction: [["incorrect_identification", "The AI identification is wrong"], ["other", "Something else"]],
    };
    const list = reasons || defaults[recordType] || defaults.observation;
    const body = `
      <div class="callout neutral" style="margin-bottom:16px">
        ${BT.icon("info")}
        <div>Reporting <strong>${BT.esc(label || "this record")}</strong>. Reports are reviewed by a human; the public record is not changed automatically.</div>
      </div>
      <div class="field">
        <label for="report-reason">What is wrong?</label>
        <select class="select" id="report-reason">
          ${list.map(([value, text]) => `<option value="${value}">${BT.esc(text)}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label for="report-details">Details (optional, but helpful)</label>
        <textarea class="textarea" id="report-details" maxlength="2000"
          placeholder="What did you observe? If possible, cite a source such as an official website."></textarea>
        <span class="field-hint">Do not include personal contact details unless you are happy for reviewers to see them.</span>
      </div>`;
    const modal = BT.modal({
      title: title || "Report a problem",
      subtitle: "Help keep BioTrace accurate.",
      body,
      footer: `<button class="btn btn-secondary" data-close type="button">Cancel</button>
               <button class="btn btn-primary" id="report-submit" type="button">Submit report</button>`,
    });
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    const submit = modal.element.querySelector("#report-submit");
    submit.addEventListener("click", async () => {
      const reason = modal.element.querySelector("#report-reason").value;
      const details = modal.element.querySelector("#report-details").value.trim();
      BT.setBusy(submit, true, "Sending…");
      try {
        await BT.api("/api/reports", {
          method: "POST",
          body: {
            record_type: recordType,
            record_id: recordId || null,
            record_label: label || null,
            report_reason: reason,
            report_details: details || null,
          },
        });
        BT.closeModal();
        BT.toast("Report received", "Thank you. A reviewer will look into it.", "success");
      } catch (err) {
        BT.setBusy(submit, false);
        BT.errorToast(err);
      }
    });
  };

  /* ---------------------------------------------------------- Add to itinerary */
  BT.addToTripModal = async function (destination) {
    let itineraries = [];
    try {
      itineraries = await BT.api("/api/itineraries");
    } catch (err) {
      BT.errorToast(err);
      return;
    }
    const existingOptions = itineraries
      .map((trip) => `<option value="${trip.id}">${BT.esc(trip.title)}${trip.travel_date ? ` · ${BT.fmtDate(trip.travel_date)}` : ""}</option>`)
      .join("");
    const body = `
      <div class="callout info" style="margin-bottom:16px">${BT.icon("route")}
        <div>Stops are ordered manually. BioTrace does not optimise routes or provide live travel times.</div>
      </div>
      ${
        itineraries.length
          ? `<div class="field">
              <label for="trip-existing">Add to an existing trip</label>
              <select class="select" id="trip-existing">
                ${existingOptions}
                <option value="new">+ Create a new trip</option>
              </select>
            </div>`
          : ""
      }
      <div id="trip-new-fields" ${itineraries.length ? 'class="hidden"' : ""}>
        <div class="field">
          <label for="trip-title">Trip title</label>
          <input class="input" id="trip-title" maxlength="160" placeholder="e.g. Temples and coast — 3 days" />
        </div>
        <div class="field">
          <label for="trip-date">Travel date (optional)</label>
          <input class="input" id="trip-date" type="date" />
        </div>
      </div>
      <div class="field">
        <label for="trip-note">Note for this stop (optional)</label>
        <textarea class="textarea" id="trip-note" maxlength="1000" placeholder="e.g. Go early; check opening hours before travelling."></textarea>
      </div>`;
    const modal = BT.modal({
      title: "Add to itinerary",
      subtitle: `${destination.name} · ${destination.district || "Odisha"}`,
      body,
      footer: `<button class="btn btn-secondary" data-close type="button">Cancel</button>
               <button class="btn btn-primary" id="trip-add" type="button">Add stop</button>`,
    });
    const select = modal.element.querySelector("#trip-existing");
    const newFields = modal.element.querySelector("#trip-new-fields");
    if (select) {
      select.addEventListener("change", () => {
        newFields.classList.toggle("hidden", select.value !== "new");
      });
    }
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    const button = modal.element.querySelector("#trip-add");
    button.addEventListener("click", async () => {
      const note = modal.element.querySelector("#trip-note").value.trim() || null;
      const choice = select ? select.value : "new";
      BT.setBusy(button, true, "Adding…");
      try {
        if (choice === "new") {
          const title = modal.element.querySelector("#trip-title").value.trim();
          const travelDate = modal.element.querySelector("#trip-date").value || null;
          if (title.length < 2) {
            throw new Error("Give your trip a title (at least 2 characters).");
          }
          const trip = await BT.api("/api/itineraries", {
            method: "POST",
            body: {
              title,
              travel_date: travelDate,
              stops: [{ destination_id: destination.id, notes: note }],
            },
          });
          BT.closeModal();
          BT.toast("Itinerary created", `Added ${destination.name}. Open Saved Places to plan the order.`, "success");
          window.location.href = `/itinerary.html?id=${trip.id}`;
          return;
        }
        const tripId = Number(choice);
        const trip = await BT.api(`/api/itineraries/${tripId}`);
        const stops = trip.stops.map((stop) => ({
          destination_id: stop.destination.id,
          notes: stop.notes,
        }));
        if (stops.some((stop) => stop.destination_id === destination.id)) {
          BT.closeModal();
          BT.toast("Already in this trip", "That destination is already a stop.", "info");
          return;
        }
        stops.push({ destination_id: destination.id, notes: note });
        await BT.api(`/api/itineraries/${tripId}`, { method: "PUT", body: { stops } });
        BT.closeModal();
        BT.toast("Stop added", `${destination.name} was added to “${trip.title}”.`, "success");
        window.dispatchEvent(new CustomEvent("biotrace:trip-updated"));
      } catch (err) {
        BT.setBusy(button, false);
        BT.errorToast(err);
      }
    });
  };

  /* ------------------------------------------------------------- Observations */
  BT.observationCard = function (obs, options = {}) {
    const image = obs.image_url
      ? `<img class="obs-thumb" src="${BT.esc(obs.image_url)}" alt="Observation photo of ${BT.esc(obs.predicted_common_name || obs.predicted_species)}" loading="lazy" />`
      : `<div class="obs-thumb-placeholder">${BT.icon(obs.category === "bird" ? "bird" : "leaf")}</div>`;
    const place = obs.district || (obs.latitude !== null ? `${obs.latitude.toFixed(3)}, ${obs.longitude.toFixed(3)}` : "No location");
    return `<article class="obs-item" data-observation-id="${obs.id}">
      ${image}
      <div class="obs-body">
        <div class="row-between" style="gap:8px">
          <div style="min-width:0">
            <h3 class="obs-title">${BT.esc(obs.predicted_common_name || obs.predicted_species)}</h3>
            <div class="obs-sci">${BT.esc(obs.predicted_species)}</div>
          </div>
          ${BT.statusBadge(obs.verification_status)}
        </div>
        <div class="obs-meta">
          <span>${BT.icon(obs.category === "bird" ? "bird" : "leaf")} ${obs.category === "bird" ? "Bird" : "Plant"}</span>
          <span class="dot-sep"></span>
          <span>AI confidence ${BT.pct(obs.confidence_score)}</span>
          <span class="dot-sep"></span>
          <span>${BT.icon("map-pin")} ${BT.esc(place)}</span>
          <span class="dot-sep"></span>
          <span>${BT.relative(obs.created_at)}</span>
        </div>
        ${obs.observer_notes ? `<p class="small muted" style="margin:8px 0 0">${BT.esc(obs.observer_notes)}</p>` : ""}
        ${obs.location_note ? `<p class="tiny muted" style="margin:6px 0 0">${BT.icon("info")} ${BT.esc(obs.location_note)}</p>` : ""}
        <div class="row" style="margin-top:10px;gap:6px">
          <button class="btn btn-ghost btn-sm" data-report-obs="${obs.id}" data-report-label="${BT.esc(obs.predicted_species)}" type="button">
            ${BT.icon("flag")}Report ID
          </button>
          ${
            obs.can_delete || options.admin
              ? `<button class="btn btn-ghost btn-sm" data-delete-obs="${obs.id}" type="button" style="color:var(--danger)">${BT.icon("trash-2")}Delete</button>`
              : ""
          }
        </div>
      </div>
    </article>`;
  };

  BT.bindObservationCards = function (root, options = {}) {
    if (!root) return;
    root.addEventListener("click", async (event) => {
      const report = event.target.closest("[data-report-obs]");
      if (report) {
        BT.reportModal({
          recordType: "observation",
          recordId: Number(report.dataset.reportObs),
          label: report.dataset.reportLabel,
          title: "Report an incorrect identification",
        });
      }
      const del = event.target.closest("[data-delete-obs]");
      if (del) {
        const id = Number(del.dataset.deleteObs);
        const ok = await BT.confirm({
          title: "Delete this observation?",
          message: "This permanently removes the record and its uploaded image. This cannot be undone.",
          confirmLabel: "Delete observation",
          danger: true,
        });
        if (!ok) return;
        try {
          await BT.api(`/api/biodiversity/observations/${id}`, { method: "DELETE" });
          const item = del.closest("[data-observation-id]");
          if (item) item.remove();
          BT.toast("Observation deleted", "The record and image were removed.", "success");
          window.dispatchEvent(new CustomEvent("biotrace:observation-deleted", { detail: { id } }));
        } catch (err) {
          BT.errorToast(err);
        }
      }
    });
  };

  /* --------------------------------------------------------------- Comparison */
  BT.compareIds = BT.compareIds || [];

  BT.initCompare = function () {
    if (document.getElementById("compare-bar")) return;
    const bar = document.createElement("div");
    bar.id = "compare-bar";
    bar.className = "compare-bar hidden";
    bar.innerHTML = `
      <span>${BT.icon("columns-3")} <strong><span id="compare-count">0</span> selected</strong></span>
      <button class="btn btn-primary" id="compare-open" type="button">Compare</button>
      <button class="btn btn-secondary" id="compare-clear" type="button">Clear</button>`;
    document.body.appendChild(bar);
    bar.querySelector("#compare-open").addEventListener("click", BT.openCompare);
    bar.querySelector("#compare-clear").addEventListener("click", () => {
      BT.compareIds = [];
      BT.refreshCompareBar();
      BT.qsa("[data-compare-id]").forEach((el) => el.classList.remove("is-active"));
    });
  };

  BT.toggleCompare = function (id, button) {
    const index = BT.compareIds.indexOf(id);
    if (index >= 0) {
      BT.compareIds.splice(index, 1);
      if (button) button.classList.remove("is-active");
    } else {
      if (BT.compareIds.length >= 3) {
        BT.toast("Compare up to 3 places", "Remove one before adding another.", "info");
        return;
      }
      BT.compareIds.push(id);
      if (button) button.classList.add("is-active");
    }
    BT.refreshCompareBar();
  };

  BT.refreshCompareBar = function () {
    const bar = document.getElementById("compare-bar");
    if (!bar) return;
    const count = document.getElementById("compare-count");
    if (count) count.textContent = String(BT.compareIds.length);
    bar.classList.toggle("hidden", BT.compareIds.length === 0);
  };

  BT.openCompare = async function () {
    if (!BT.compareIds.length) return;
    const loading = BT.modal({
      title: "Comparing places",
      body: `<div class="stack"><div class="skeleton skeleton-line w-60"></div><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line w-40"></div></div>`,
    });
    try {
      const places = await Promise.all(BT.compareIds.map((id) => BT.api(`/api/tourism/destinations/${id}`)));
      const rows = [
        ["Category", (p) => BT.esc(BT.category(p.category).label)],
        ["District", (p) => BT.esc(p.district || "Not verified")],
        ["Visiting hours", (p) => BT.esc(p.visiting_hours || "Not verified")],
        ["Entry fee", (p) => BT.esc(p.entry_fee || "Not verified")],
        ["Estimated visit", (p) => (p.estimated_visit_minutes ? `${p.estimated_visit_minutes} min (estimate)` : "No estimate")],
        ["Accessibility", (p) => BT.esc(p.accessibility_information || "Not verified")],
        ["Facilities", (p) => (p.facilities.length ? BT.esc(p.facilities.join(", ")) : "Not verified")],
        ["Verification", (p) => p.verification_status],
      ];
      loading.close();
      BT.modal({
        title: "Compare places",
        subtitle: "Only recorded fields are shown. Missing information is never guessed.",
        size: "lg",
        body: `<div class="table-wrap"><table class="compare-table">
          <thead><tr><th></th>${places.map((p) => `<th><a href="/destination.html?slug=${encodeURIComponent(p.slug)}">${BT.esc(p.name)}</a></th>`).join("")}</tr></thead>
          <tbody>${rows
            .map(
              ([label, render]) => `<tr><th>${label}</th>${places
                .map((p) => {
                  const value = render(p);
                  return `<td>${label === "Verification" ? BT.statusBadge(p.verification_status) : value}</td>`;
                })
                .join("")}</tr>`
            )
            .join("")}</tbody>
        </table></div>`,
        footer: `<button class="btn btn-secondary" data-close type="button">Close</button>`,
      });
      BT.qs('.modal [data-close]').addEventListener("click", BT.closeModal);
    } catch (err) {
      loading.close();
      BT.errorToast(err);
    }
  };
})();
