/* ==========================================================================
   BioTrace — destination detail page
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;
  let destination = null;

  function infoRow(icon, key, value) {
    const missing = value === null || value === undefined || value === "" ||
      (Array.isArray(value) && value.length === 0);
    return `<div class="info-row">
      ${BT.icon(icon)}
      <div class="info-key">${BT.esc(key)}</div>
      <div class="info-val ${missing ? "unverified" : ""}">${
        missing
          ? "Not verified — information unavailable"
          : Array.isArray(value)
          ? value.map((item) => `<span class="chip">${BT.esc(item)}</span>`).join(" ")
          : BT.esc(value)
      }</div>
    </div>`;
  }

  function renderHero(dest) {
    const meta = BT.category(dest.category);
    const saved = BT.favouriteIds && BT.favouriteIds.has(dest.id);
    const place = [dest.locality, dest.city, dest.district].filter(Boolean).join(", ");
    const images = dest.images || [];
    const hero = images[0];
    return `<div class="detail-hero ${hero ? "has-photo" : ""}">
      ${
        hero
          ? `<img class="detail-hero-photo" data-photo src="${BT.esc(hero.url)}"
                 alt="${BT.esc(hero.title || dest.name)}" decoding="async" referrerpolicy="no-referrer">`
          : `<div class="detail-art ${BT.art(dest.category)}">
        <i data-lucide="${BT.esc(meta.icon)}" class="detail-icon" aria-hidden="true"></i>
      </div>`
      }
      <div class="detail-hero-top">
        <button class="btn btn-secondary btn-sm ${saved ? "is-saved" : ""}" id="save-dest" type="button" aria-pressed="${saved ? "true" : "false"}">
          ${BT.icon("heart")}<span>${saved ? "Saved" : "Save"}</span>
        </button>
        <button class="btn btn-secondary btn-sm" id="trip-dest" type="button">${BT.icon("route")}<span>Add to trip</span></button>
        <button class="btn btn-secondary btn-sm" id="share-dest" type="button">${BT.icon("share-2")}<span>Share</span></button>
        <button class="btn btn-secondary btn-sm" id="report-dest" type="button">${BT.icon("flag")}<span>Report</span></button>
      </div>
      <div>
        <div class="breadcrumbs">
          <a href="/">Home</a>${BT.icon("chevron-right")}
          <a href="/tourism.html">Tourism</a>${BT.icon("chevron-right")}
          <a href="/tourism.html?category=${encodeURIComponent(dest.category)}">${BT.esc(meta.label)}</a>
        </div>
        <div class="row" style="gap:8px;margin-bottom:10px">
          <span class="badge badge-neutral" style="background:rgba(255,255,255,.14);color:#fff">${BT.icon(meta.icon)}${BT.esc(meta.label)}</span>
          ${BT.statusBadge(dest.verification_status)}
          ${dest.featured ? `<span class="badge badge-featured">${BT.icon("sparkles")}Featured</span>` : ""}
        </div>
        <h1>${BT.esc(dest.name)}</h1>
        <div class="detail-sub">
          ${BT.icon("map-pin")}<span>${BT.esc(place || "Location not recorded")}</span>
          ${dest.estimated_visit_minutes ? `<span class="dot-sep"></span>${BT.icon("clock")}<span>About ${dest.estimated_visit_minutes} min (estimate)</span>` : ""}
        </div>
      </div>
    </div>`;
  }

  function renderGallery(dest) {
    const images = dest.images || [];
    if (!images.length) return "";
    const items = images
      .map((image, index) => {
        const credit = BT.photoCredit(image.credit, image.licence);
        return `<button class="gallery-item ${index === 0 ? "is-lead" : ""}" type="button"
                  data-gallery-index="${index}"
                  aria-label="Open photograph ${index + 1} of ${images.length}: ${BT.esc(image.title || dest.name)}">
          <img data-photo src="${BT.esc(image.thumbnail_url || image.url)}"
               alt="${BT.esc(image.title || dest.name)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">
          ${credit ? `<span class="gallery-cap">${BT.esc(credit)}</span>` : ""}
        </button>`;
      })
      .join("");
    return `<div class="detail-section photo-gallery">
        <div class="gallery-head">
          <h2>Photographs</h2>
          <span class="gallery-count">${images.length} open-source photo${images.length === 1 ? "" : "s"} · Wikimedia Commons</span>
        </div>
        <div class="gallery-grid">${items}</div>
        <p class="tiny muted" style="margin:12px 0 0">
          ${BT.icon("info")} Each photograph is reused under its own free licence and is credited on the image.
          Open a photo to see the photographer, licence and source file.
        </p>
      </div>`;
  }

  function sourceLinks(dest) {
    const query = encodeURIComponent(dest.name);
    const links = [
      ["Wikipedia search", `https://en.wikipedia.org/w/index.php?search=${query}`],
      ["Wikimedia Commons", `https://commons.wikimedia.org/w/index.php?search=${query}`],
    ];
    if (dest.latitude !== null && dest.latitude !== undefined && dest.longitude !== null && dest.longitude !== undefined) {
      links.push([
        "OpenStreetMap",
        `https://www.openstreetmap.org/?mlat=${dest.latitude}&mlon=${dest.longitude}#map=14/${dest.latitude}/${dest.longitude}`,
      ]);
    }
    return `<div class="source-links">
      ${links
        .map(
          ([label, url]) =>
            `<a class="source-link" href="${BT.esc(url)}" target="_blank" rel="noopener">${BT.icon("external-link")}${BT.esc(label)}</a>`
        )
        .join("")}
    </div>`;
  }

  function renderMain(dest) {
    const gaps = dest.data_gaps || [];
    return `${renderGallery(dest)}
      <div class="detail-section detail-copy">
        <h2>About this place</h2>
        <p>${BT.esc(dest.description || "No description has been recorded for this place yet.")}</p>
        ${dest.significance ? `<p>${BT.esc(dest.significance)}</p>` : ""}
        <div class="row" style="gap:6px;margin-top:14px">
          ${(dest.tags || []).map((tag) => `<span class="chip">${BT.esc(tag.replace(/_/g, " "))}</span>`).join("")}
        </div>
      </div>

      <div class="detail-section">
        <h2>Visitor information</h2>
        <div class="info-list">
          ${infoRow("clock", "Visiting hours", dest.visiting_hours)}
          ${infoRow("calendar-x", "Closed days", dest.closed_days)}
          ${infoRow("ticket", "Entry fee", dest.entry_fee)}
          ${infoRow("timer", "Suggested visit", dest.estimated_visit_minutes ? `${dest.estimated_visit_minutes} minutes (planning estimate, not an official duration)` : null)}
          ${infoRow("shirt", "Dress code", dest.dress_code)}
          ${infoRow("camera", "Photography", dest.photography_policy)}
          ${infoRow("accessibility", "Accessibility", dest.accessibility_information)}
          ${infoRow("concierge-bell", "Facilities", dest.facilities)}
        </div>
        <p class="tiny muted" style="margin:14px 0 0">
          ${BT.icon("info")} Fields marked “Not verified” were absent from the source record. BioTrace does not fill them with guesses. If you know a sourced correction, use the correction form.
        </p>
      </div>

      ${dest.visitor_guidelines ? `<div class="detail-section">
        <h2>Visitor guidelines</h2>
        <p class="small muted" style="line-height:1.8;margin:0">${BT.esc(dest.visitor_guidelines)}</p>
      </div>` : ""}

      <div class="detail-section">
        <h2>What is still missing</h2>
        ${
          gaps.length
            ? `<div class="callout warning">${BT.icon("alert-triangle")}<div>
                 <strong>${gaps.length} field${gaps.length === 1 ? "" : "s"} not recorded:</strong>
                 ${BT.esc(gaps.join(", "))}. These are intentionally left blank rather than guessed.
               </div></div>`
            : `<div class="callout success">${BT.icon("check-circle-2")}<div><strong>All core visitor fields in this project's checklist are recorded.</strong> Still verify before travelling; details can change.</div></div>`
        }
      </div>

      <div class="detail-section">
        <h2>Provenance and licensing</h2>
        <div class="info-list">
          ${infoRow("database", "Source", dest.source_name || dest.source_url)}
          ${infoRow("link", "Source URL", dest.source_url)}
          ${infoRow("scale", "Licence", dest.licence_information)}
          ${infoRow("calendar-check", "Last verified", dest.last_verified_at ? BT.fmtDate(dest.last_verified_at) : null)}
          ${infoRow("badge-check", "Verification", dest.verification_status === "verified" ? "Human verified" : dest.verification_status === "provisional" ? "Provisional — not fully checked" : dest.verification_status)}
          ${infoRow("image", "Photographs", (dest.images && dest.images.length)
            ? `${dest.images.length} open-source photo${dest.images.length === 1 ? "" : "s"} from Wikimedia Commons — credited individually in the gallery`
            : dest.image_reference
            ? `${dest.image_reference}${dest.image_credit ? ` · ${dest.image_credit}` : ""}${dest.image_licence ? ` · ${dest.image_licence}` : ""}`
            : null)}
        </div>
        <p class="data-provenance" style="margin:14px 0 0">
          Coordinates, where present, were checked against OpenStreetMap/Photon and are displayed under the
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap ODbL licence</a>.
          Descriptive text and project-curated metadata are academic seed data and should be independently verified before publication or travel decisions.
        </p>
        <h3 style="margin:18px 0 6px;font-size:1rem">Sources to learn more</h3>
        <p class="tiny muted" style="margin:0 0 8px">These are external search pages, not records verified by BioTrace. Read them alongside the provenance above.</p>
        ${sourceLinks(dest)}
      </div>`;
  }

  function nearbyMarkup(nearby) {
    if (!nearby || !nearby.length) {
      return `<p class="small muted" style="margin:0">No nearby records were found in the catalogue.</p>`;
    }
    return `<div class="nearby-list">${nearby
      .map((item) => {
        const meta = BT.category(item.category);
        return `<a class="nearby-item" href="/destination.html?slug=${encodeURIComponent(item.slug)}">
          <span class="nb-cat">${BT.icon(meta.icon)}</span>
          <span class="nb-body"><strong>${BT.esc(item.name)}</strong><span>${BT.esc(meta.label)} · ${BT.esc(item.district || "district not recorded")}</span></span>
          ${item.distance_km !== null && item.distance_km !== undefined ? `<span class="nb-dist">${item.distance_km} km</span>` : ""}
        </a>`;
      })
      .join("")}</div>`;
  }

  function renderSidebar(dest) {
    const hasCoords = dest.latitude !== null && dest.latitude !== undefined && dest.longitude !== null && dest.longitude !== undefined;
    return `<div class="detail-section">
        <h2>Location</h2>
        ${
          hasCoords
            ? `<div class="map-shell map-sm" id="dest-map" aria-label="Map showing ${BT.esc(dest.name)}"></div>
               <div class="row" style="margin-top:10px;gap:8px">
                 <a class="btn btn-secondary btn-sm" href="${BT.directionsUrl(dest)}" target="_blank" rel="noopener">${BT.icon("navigation")}Open directions</a>
                 <span class="tiny muted">${dest.latitude.toFixed(4)}, ${dest.longitude.toFixed(4)}</span>
               </div>
               <p class="tiny muted" style="margin:10px 0 0">Pin checked against OpenStreetMap. It is not a guarantee that the entrance is at this exact point.</p>`
            : `<div class="callout warning">${BT.icon("map-pin-off")}<div>
                 <strong>Location unavailable.</strong>
                 This record has no reliable coordinates, so no pin is shown. It remains listed in the catalogue; the district is
                 ${BT.esc(dest.district || "not recorded")}.
               </div></div>`
        }
      </div>

      <div class="detail-section">
        <h2>Nearby in the catalogue</h2>
        ${nearbyMarkup(dest.nearby)}
      </div>

      <div class="detail-section">
        <h2>Help improve this record</h2>
        <p class="small muted">If a detail is wrong or out of date, submit a correction with a source. Reviewers check it before anything changes.</p>
        <div class="stack-sm">
          <button class="btn btn-secondary btn-block" id="correct-dest" type="button">${BT.icon("pencil-line")}Suggest a correction</button>
          <button class="btn btn-ghost btn-block" id="report-dest-2" type="button">${BT.icon("flag")}Report a problem</button>
        </div>
      </div>

      <div class="detail-section">
        <h2>Plan your visit</h2>
        <div class="stack-sm">
          <button class="btn btn-primary btn-block" id="trip-dest-2" type="button">${BT.icon("route")}Add to itinerary</button>
          <button class="btn btn-secondary btn-block" id="save-dest-2" type="button">${BT.icon("heart")}Save place</button>
        </div>
        <p class="tiny muted" style="margin:12px 0 0">Opening hours, fees and travel times can change. Verify with the destination before travelling. BioTrace does not provide live traffic or route optimisation.</p>
      </div>`;
  }

  function openLightbox(images, startIndex) {
    let index = startIndex;
    const overlay = document.createElement("div");
    overlay.className = "lightbox";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Photograph viewer");
    document.body.appendChild(overlay);
    document.body.classList.add("lightbox-open");

    function close() {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("lightbox-open");
      overlay.remove();
    }

    function step(delta) {
      index = (index + delta + images.length) % images.length;
      paint();
    }

    function onKey(event) {
      if (event.key === "Escape") close();
      else if (event.key === "ArrowLeft") step(-1);
      else if (event.key === "ArrowRight") step(1);
    }

    function paint() {
      const image = images[index];
      const credit = BT.photoCredit(image.credit, image.licence);
      overlay.innerHTML = `
        <button class="lightbox-close" type="button" aria-label="Close photo viewer">${BT.icon("x")}</button>
        ${images.length > 1 ? `<button class="lightbox-nav prev" type="button" aria-label="Previous photo">${BT.icon("chevron-left")}</button>` : ""}
        <figure class="lightbox-figure">
          <img data-photo src="${BT.esc(image.url)}" alt="${BT.esc(image.title || "Photograph")}" referrerpolicy="no-referrer">
          <figcaption>
            <strong>${BT.esc(image.title || "Photograph")}</strong>
            <span class="lightbox-credit">${BT.esc(credit || image.source_name || "Wikimedia Commons")}</span>
            <span class="lightbox-links">
              ${image.licence_url ? `<a href="${BT.esc(image.licence_url)}" target="_blank" rel="noopener">Licence</a>` : ""}
              <a href="${BT.esc(image.page_url)}" target="_blank" rel="noopener">Source file on Wikimedia Commons</a>
            </span>
            <span class="lightbox-count">${index + 1} / ${images.length}</span>
          </figcaption>
        </figure>
        ${images.length > 1 ? `<button class="lightbox-nav next" type="button" aria-label="Next photo">${BT.icon("chevron-right")}</button>` : ""}`;
      BT.refreshIcons();
      overlay.querySelector(".lightbox-close").addEventListener("click", close);
      const prev = overlay.querySelector(".prev");
      const next = overlay.querySelector(".next");
      if (prev) prev.addEventListener("click", () => step(-1));
      if (next) next.addEventListener("click", () => step(1));
    }

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) close();
    });
    document.addEventListener("keydown", onKey);
    paint();
  }

  function bindActions(dest) {
    const toggleSave = async (button) => {
      if (button) await BT.toggleFavourite(dest.id, button);
      const saved = BT.favouriteIds && BT.favouriteIds.has(dest.id);
      BT.qsa("#save-dest, #save-dest-2").forEach((item) => {
        item.classList.toggle("is-saved", saved);
        item.setAttribute("aria-pressed", String(saved));
        if (item.id === "save-dest") item.innerHTML = `${BT.icon("heart")}<span>${saved ? "Saved" : "Save"}</span>`;
        if (item.id === "save-dest-2") item.innerHTML = `${BT.icon("heart")}${saved ? "Saved" : "Save place"}`;
      });
      BT.refreshIcons();
    };
    BT.qsa("#save-dest, #save-dest-2").forEach((button) => button.addEventListener("click", () => toggleSave(button)));
    BT.qsa("#trip-dest, #trip-dest-2").forEach((button) => button.addEventListener("click", () => BT.addToTripModal(dest)));
    BT.qsa("#report-dest, #report-dest-2").forEach((button) =>
      button.addEventListener("click", () =>
        BT.reportModal({ recordType: "destination", recordId: dest.id, label: dest.name, title: "Report a destination problem" })
      )
    );
    document.getElementById("share-dest").addEventListener("click", () => BT.share(dest.name, BT.shareUrl(dest.slug)));
    document.getElementById("correct-dest").addEventListener("click", () => correctionModal(dest));

    const gallery = document.querySelector(".photo-gallery");
    if (gallery && dest.images && dest.images.length) {
      gallery.addEventListener("click", (event) => {
        const item = event.target.closest("[data-gallery-index]");
        if (!item) return;
        event.preventDefault();
        openLightbox(dest.images, Number(item.dataset.galleryIndex));
      });
    }
  }

  function correctionModal(dest) {
    const fields = [
      ["visiting_hours", "Visiting hours"],
      ["closed_days", "Closed days"],
      ["entry_fee", "Entry fee"],
      ["official_website", "Official website"],
      ["accessibility_information", "Accessibility information"],
      ["contact_information", "Contact details"],
      ["facilities", "Visitor facilities"],
      ["latitude", "Map latitude"],
      ["longitude", "Map longitude"],
      ["description", "Description"],
      ["other", "Other"],
    ];
    const body = `
      <div class="callout info" style="margin-bottom:16px">${BT.icon("info")}
        <div>A reviewer checks your source before any public change is made. Corrections are not applied automatically.</div>
      </div>
      <div class="field">
        <label for="correction-field">Which field?</label>
        <select class="select" id="correction-field">
          ${fields.map(([value, label]) => `<option value="${value}">${BT.esc(label)}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label for="correction-value">Suggested value</label>
        <textarea class="textarea" id="correction-value" maxlength="1000" placeholder="What should it say? Include units, dates and conditions where relevant."></textarea>
      </div>
      <div class="field">
        <label for="correction-explanation">What is wrong with the current value? (optional)</label>
        <textarea class="textarea" id="correction-explanation" maxlength="1000"></textarea>
      </div>
      <div class="field">
        <label for="correction-source">Source URL (strongly recommended)</label>
        <input class="input" id="correction-source" type="url" maxlength="500" placeholder="https://…" />
      </div>`;
    const modal = BT.modal({
      title: "Suggest a correction",
      subtitle: dest.name,
      body,
      size: "lg",
      footer: `<button class="btn btn-secondary" data-close type="button">Cancel</button>
               <button class="btn btn-primary" id="correction-submit" type="button">Submit for review</button>`,
    });
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    const submit = modal.element.querySelector("#correction-submit");
    submit.addEventListener("click", async () => {
      const suggested = modal.element.querySelector("#correction-value").value.trim();
      if (suggested.length < 2) {
        BT.toast("Correction required", "Enter the value you believe is correct.", "error");
        return;
      }
      const field = modal.element.querySelector("#correction-field").value;
      const currentMap = {
        visiting_hours: dest.visiting_hours,
        closed_days: dest.closed_days,
        entry_fee: dest.entry_fee,
        official_website: dest.official_website,
        accessibility_information: dest.accessibility_information,
        contact_information: dest.contact_information,
        facilities: (dest.facilities || []).join(", "),
        latitude: dest.latitude,
        longitude: dest.longitude,
        description: dest.description,
      };
      BT.setBusy(submit, true, "Sending…");
      try {
        const result = await BT.api("/api/tourism/corrections", {
          method: "POST",
          body: {
            destination_id: dest.id,
            field_name: field,
            current_value: currentMap[field] !== undefined && currentMap[field] !== null ? String(currentMap[field]).slice(0, 500) : null,
            suggested_value: suggested,
            explanation: modal.element.querySelector("#correction-explanation").value.trim() || null,
            source_url: modal.element.querySelector("#correction-source").value.trim() || null,
          },
        });
        BT.closeModal();
        BT.toast("Correction submitted", result.detail || result.message, "success", 7000);
      } catch (err) {
        BT.setBusy(submit, false);
        BT.errorToast(err);
      }
    });
  }

  function initMap(dest) {
    if (!dest.latitude || !dest.longitude || !window.L) return;
    const host = document.getElementById("dest-map");
    if (!host) return;
    const map = L.map(host, { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    const marker = L.marker([dest.latitude, dest.longitude]).addTo(map);
    marker.bindPopup(`<div class="map-popup"><h4>${BT.esc(dest.name)}</h4><div class="tiny muted">${BT.esc(dest.district || "Odisha")}</div></div>`);
    map.setView([dest.latitude, dest.longitude], 13);
    setTimeout(() => map.invalidateSize(), 120);
  }

  function renderError(message) {
    const root = document.getElementById("destination-root");
    if (!root) return;
    root.innerHTML = `<div class="state error" style="margin:60px auto">
      <div class="state-icon">${BT.icon("map-pin-off")}</div>
      <h3>Destination not found</h3>
      <p>${BT.esc(message)}</p>
      <div class="row" style="justify-content:center">
        <a class="btn btn-primary" href="/tourism.html">Browse the catalogue</a>
        <a class="btn btn-secondary" href="/map.html">Open the map</a>
      </div>
    </div>`;
    BT.refreshIcons();
  }

  async function init() {
    const params = new URLSearchParams(location.search);
    const identifier = params.get("slug") || params.get("id");
    if (!identifier) {
      renderError("No destination was specified in the link.");
      return;
    }
    try {
      await BT.loadTaxonomy();
      await BT.loadFavourites();
      destination = await BT.api(`/api/tourism/destinations/${encodeURIComponent(identifier)}`);
      document.title = `${destination.name} — BioTrace`;
      const description = document.querySelector('meta[name="description"]');
      if (description) description.setAttribute("content", `${destination.name}, ${destination.district || "Odisha"} — sourced visitor information, provenance and data gaps.`);
      const root = document.getElementById("destination-root");
      root.innerHTML = `${renderHero(destination)}
        <div class="detail-layout">
          <div>${renderMain(destination)}</div>
          <div>${renderSidebar(destination)}</div>
        </div>`;
      bindActions(destination);
      initMap(destination);
      BT.refreshIcons();
    } catch (err) {
      renderError(err.message);
      if (err.status !== 404) BT.errorToast(err);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
