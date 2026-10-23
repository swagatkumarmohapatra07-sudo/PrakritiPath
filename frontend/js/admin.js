/* ==========================================================================
   BioTrace — reviewer console
   Authenticates against /api/admin/login, keeps the signed bearer token in
   sessionStorage, and drives observation/destination/report review.
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;
  const TOKEN_KEY = "biotrace_admin_token";
  const USER_KEY = "biotrace_admin_user";

  const SECTIONS = {
    overview: {
      title: "Overview",
      subtitle: "Live review workload and recent activity.",
      icon: "layout-dashboard",
    },
    observations: {
      title: "Observations",
      subtitle: "Verify, correct classification, or reject consented records.",
      icon: "scan-eye",
    },
    destinations: {
      title: "Destinations",
      subtitle: "Update the verification status of tourism records.",
      icon: "map-pinned",
    },
    reports: {
      title: "Reports",
      subtitle: "Triage problems reported by visitors.",
      icon: "flag",
    },
  };

  const state = {
    section: "overview",
    token: null,
    username: null,
    observationStatus: "",
    destinationStatus: "",
    reportStatus: "",
    overview: null,
    destinations: [],
  };

  /* ------------------------------------------------------------- Auth token */
  function readToken() {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch (err) {
      return null;
    }
  }

  function readUser() {
    try {
      return sessionStorage.getItem(USER_KEY);
    } catch (err) {
      return null;
    }
  }

  function storeAuth(token, username) {
    state.token = token;
    state.username = username;
    try {
      sessionStorage.setItem(TOKEN_KEY, token);
      sessionStorage.setItem(USER_KEY, username || "reviewer");
    } catch (err) {
      /* sessionStorage can be blocked; the in-memory token still works */
    }
  }

  function clearAuth() {
    state.token = null;
    state.username = null;
    try {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
    } catch (err) {
      /* ignore */
    }
  }

  async function adminApi(path, options = {}) {
    if (!state.token) throw new BT.ApiError("Please sign in to the reviewer console.", 401);
    const headers = Object.assign({}, options.headers || {}, {
      Authorization: `Bearer ${state.token}`,
    });
    try {
      return await BT.api(path, Object.assign({}, options, { headers }));
    } catch (err) {
      if (err.status === 401) {
        clearAuth();
        showLogin("Your reviewer session expired or was rejected. Please sign in again.");
      }
      throw err;
    }
  }

  /* ------------------------------------------------------------ Login screen */
  function showLogin(message) {
    const login = document.getElementById("admin-login");
    const app = document.getElementById("admin-app");
    if (!login || !app) return;
    login.classList.remove("hidden");
    app.classList.add("hidden");
    const error = document.getElementById("admin-login-error");
    if (error) {
      if (message) {
        error.classList.remove("hidden");
        error.innerHTML = `${BT.icon("alert-circle")}<div>${BT.esc(message)}</div>`;
      } else {
        error.classList.add("hidden");
        error.innerHTML = "";
      }
    }
    BT.refreshIcons();
    const user = document.getElementById("admin-username");
    if (user) user.focus();
  }

  function showApp() {
    const login = document.getElementById("admin-login");
    const app = document.getElementById("admin-app");
    if (!login || !app) return;
    login.classList.add("hidden");
    app.classList.remove("hidden");
    const user = document.getElementById("admin-user");
    if (user) user.textContent = state.username || "reviewer";
    BT.refreshIcons();
  }

  async function handleLogin(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const username = form.querySelector("#admin-username").value.trim();
    const password = form.querySelector("#admin-password").value;
    const error = document.getElementById("admin-login-error");
    const submit = document.getElementById("admin-login-submit");

    error.classList.add("hidden");
    if (username.length < 2 || password.length < 6) {
      error.classList.remove("hidden");
      error.innerHTML = `${BT.icon("alert-circle")}<div>Enter the administrator username and a password of at least 6 characters.</div>`;
      BT.refreshIcons();
      return;
    }

    BT.setBusy(submit, true, "Signing in…");
    try {
      const data = await BT.api("/api/admin/login", {
        method: "POST",
        body: { username, password },
      });
      storeAuth(data.access_token, data.username);
      form.querySelector("#admin-password").value = "";
      showApp();
      await setSection("overview");
      BT.toast("Signed in", "You can review observations, destinations and reports.", "success", 3200);
    } catch (err) {
      error.classList.remove("hidden");
      error.innerHTML = `${BT.icon("alert-circle")}<div>${BT.esc(err.message)}</div>`;
      BT.refreshIcons();
    } finally {
      BT.setBusy(submit, false);
    }
  }

  function logout(silent) {
    clearAuth();
    state.overview = null;
    state.destinations = [];
    showLogin("");
    if (!silent) BT.toast("Signed out", "The reviewer token was removed from this tab.", "info", 2800);
  }

  /* ------------------------------------------------------------- Shared HTML */
  function loadingPanel(lines) {
    const count = lines || 4;
    return `<div class="panel">${Array.from({ length: count })
      .map((_, index) => `<div class="skeleton skeleton-line ${index % 3 === 0 ? "w-40" : index % 3 === 1 ? "" : "w-60"}"></div>`)
      .join("")}</div>`;
  }

  function errorPanel(error, retryAction) {
    return `<div class="panel">${BT.emptyState(
      "This section could not load",
      error.message || "The server did not return the requested data.",
      "cloud-off",
      `<button class="btn btn-secondary" type="button" data-retry="${BT.esc(retryAction || "")}">${BT.icon("refresh-cw")}Try again</button>`
    )}</div>`;
  }

  function statusSelect(id, value, includeEmpty, emptyLabel) {
    const options = [
      ...(includeEmpty ? [`<option value="" ${value === "" ? "selected" : ""}>${BT.esc(emptyLabel || "All statuses")}</option>`] : []),
      ["pending", "Pending review"],
      ["verified", "Verified"],
      ["needs_review", "Needs review"],
      ["rejected", "Rejected"],
    ];
    return `<select class="select" id="${id}" style="width:auto;min-width:170px">
      ${options
        .map((entry) => {
          const [optionValue, label] = Array.isArray(entry) ? entry : [null, entry];
          if (optionValue === null) return label;
          return `<option value="${optionValue}" ${value === optionValue ? "selected" : ""}>${BT.esc(label)}</option>`;
        })
        .join("")}
    </select>`;
  }

  function categoryLabel(slug) {
    return BT.category(slug).label || slug;
  }

  function placeLabel(item) {
    return [item.district, item.city, item.locality].filter(Boolean)[0] || "No location";
  }

  /* ------------------------------------------------------------------ Overview */
  function overviewMarkup(data) {
    const stat = (value, label) =>
      `<div class="admin-stat"><strong>${BT.num(value)}</strong><span>${BT.esc(label)}</span></div>`;

    const recentObservations = data.recent_observations.length
      ? `<div class="admin-list">${data.recent_observations
          .map(
            (item) => `<button class="admin-list-row" type="button" data-review-observation="${item.id}">
              <span class="admin-list-main">
                <strong>${BT.esc(item.label || "Unlabelled record")}</strong>
                <span class="small muted">${BT.esc(item.category === "bird" ? "Bird" : "Plant")} · AI confidence ${BT.pct(item.confidence)} · ${BT.relative(item.created_at)}</span>
              </span>
              ${BT.statusBadge(item.status)}
            </button>`
          )
          .join("")}</div>`
      : `<p class="small muted" style="margin:0">No observations have been submitted yet.</p>`;

    const recentReports = data.recent_reports.length
      ? `<div class="admin-list">${data.recent_reports
          .map(
            (item) => `<button class="admin-list-row" type="button" data-open-report="${item.id}">
              <span class="admin-list-main">
                <strong>${BT.esc(item.record_label || `${item.record_type} #${item.record_id || "?"}`)}</strong>
                <span class="small muted">${BT.esc(String(item.reason || "report").replace(/_/g, " "))} · ${BT.relative(item.created_at)}</span>
              </span>
              ${BT.statusBadge(item.status)}
            </button>`
          )
          .join("")}</div>`
      : `<p class="small muted" style="margin:0">No reports have been filed. That is not proof everything is correct.</p>`;

    return `
      <div class="admin-stat-grid">
        ${stat(data.pending_observations, "Observations pending")}
        ${stat(data.open_reports, "Open reports")}
        ${stat(data.unverified_destinations, "Destinations unverified")}
        ${stat(data.total_observations, "Observations total")}
      </div>
      <div class="grid grid-2">
        <div class="panel">
          <div class="panel-head">
            <div><h3>Recent observations</h3><p>Newest consented submissions.</p></div>
            <button class="btn btn-ghost btn-sm" type="button" data-goto="observations">Open queue ${BT.icon("arrow-right")}</button>
          </div>
          ${recentObservations}
        </div>
        <div class="panel">
          <div class="panel-head">
            <div><h3>Recent reports</h3><p>Visitor-reported data problems.</p></div>
            <button class="btn btn-ghost btn-sm" type="button" data-goto="reports">Open reports ${BT.icon("arrow-right")}</button>
          </div>
          ${recentReports}
        </div>
      </div>
      <div class="callout info" style="margin-top:20px">
        ${BT.icon("shield-check")}
        <div>
          <strong>${BT.num(data.total_destinations)} tourism records in the catalogue.</strong>
          ${BT.num(data.unverified_destinations)} still need a human source check. Verification is a provenance
          decision, not a claim that every visitor detail is permanently correct.
        </div>
      </div>`;
  }

  async function loadOverview() {
    const host = document.getElementById("admin-content");
    host.innerHTML = loadingPanel(4);
    try {
      const data = await adminApi("/api/admin/overview");
      state.overview = data;
      host.innerHTML = overviewMarkup(data);
      BT.refreshIcons();
      bindAdminContent();
    } catch (err) {
      if (err.status === 401) return;
      host.innerHTML = errorPanel(err, "overview");
      bindAdminContent();
      BT.errorToast(err);
    }
  }

  /* -------------------------------------------------------------- Observations */
  function observationRow(item) {
    const image = item.image_url
      ? `<img src="${BT.esc(item.image_url)}" alt="Observation of ${BT.esc(item.predicted_common_name || item.predicted_species)}" loading="lazy" />`
      : `<div class="obs-thumb-placeholder">${BT.icon(item.category === "bird" ? "bird" : "leaf")}</div>`;
    return `<tr>
      <td>${image}</td>
      <td>
        <strong style="display:block">${BT.esc(item.predicted_common_name || item.predicted_species)}</strong>
        <span class="tiny muted">${BT.esc(item.predicted_species)}</span>
      </td>
      <td>${BT.esc(item.category === "bird" ? "Bird" : "Plant")}</td>
      <td>${BT.pct(item.confidence_score, 1)}</td>
      <td>${BT.esc(item.district || (item.latitude !== null ? `${item.latitude.toFixed(3)}, ${item.longitude.toFixed(3)}` : "None"))}</td>
      <td>${BT.statusBadge(item.verification_status)}</td>
      <td><span class="small muted">${BT.relative(item.created_at)}</span></td>
      <td><button class="btn btn-secondary btn-sm" type="button" data-review-observation="${item.id}">${BT.icon("search-check")}Review</button></td>
    </tr>`;
  }

  async function loadObservations() {
    const host = document.getElementById("admin-content");
    host.innerHTML = loadingPanel(4);
    const query = state.observationStatus ? `?status_filter=${encodeURIComponent(state.observationStatus)}` : "";
    try {
      const rows = await adminApi(`/api/admin/observations${query}`);
      const toolbar = `<div class="row-between" style="margin-bottom:14px">
        <div class="row" style="gap:8px">
          ${statusSelect("admin-observation-status", state.observationStatus, true, "All statuses")}
          <button class="btn btn-secondary btn-sm" type="button" data-reload="observations">${BT.icon("refresh-cw")}Refresh</button>
        </div>
        <span class="small muted">${BT.num(rows.length)} record${rows.length === 1 ? "" : "s"} shown · newest first · max 200</span>
      </div>`;
      if (!rows.length) {
        host.innerHTML =
          toolbar +
          `<div class="panel">${BT.emptyState(
            "No observations match this filter",
            "Try a different status. Saved observations remain pending until a reviewer acts on them.",
            "scan-eye"
          )}</div>`;
      } else {
        host.innerHTML =
          toolbar +
          `<div class="table-wrap"><table class="table">
            <thead><tr><th>Photo</th><th>Prediction</th><th>Type</th><th>Confidence</th><th>Location</th><th>Status</th><th>Submitted</th><th></th></tr></thead>
            <tbody>${rows.map(observationRow).join("")}</tbody>
          </table></div>
          <p class="tiny muted" style="margin:12px 0 0">AI confidence is a model score, not accuracy. Review the photo before verifying.</p>`;
      }
      BT.refreshIcons();
      bindAdminContent();
    } catch (err) {
      if (err.status === 401) return;
      host.innerHTML = errorPanel(err, "observations");
      bindAdminContent();
      BT.errorToast(err);
    }
  }

  function speciesOptions(category, selectedId) {
    const species = (BT.taxonomy && BT.taxonomy.species) || [];
    const matches = species.filter((item) => item.category === category);
    return matches
      .map(
        (item) =>
          `<option value="${item.id}" ${Number(selectedId) === item.id ? "selected" : ""}>${BT.esc(item.common_name)} — ${BT.esc(item.scientific_name)}</option>`
      )
      .join("");
  }

  async function openObservationReview(id) {
    let item;
    try {
      const rows = await adminApi(`/api/admin/observations?limit=200`);
      item = rows.find((row) => row.id === id);
      if (!item) throw new Error("That observation is no longer available.");
      await BT.loadTaxonomy();
    } catch (err) {
      if (err.status !== 401) BT.errorToast(err);
      return;
    }

    const image = item.image_url
      ? `<img class="admin-review-img" src="${BT.esc(item.image_url)}" alt="Observation photo" />`
      : `<div class="admin-review-img obs-thumb-placeholder">${BT.icon(item.category === "bird" ? "bird" : "leaf")}</div>`;

    const body = `
      <div class="admin-review-head">
        ${image}
        <div>
          <h4 style="margin:0">${BT.esc(item.predicted_common_name || item.predicted_species)}</h4>
          <p class="small muted" style="margin:4px 0 0">${BT.esc(item.predicted_species)} · ${BT.esc(item.category === "bird" ? "Bird" : "Plant")}</p>
          <div class="row" style="gap:6px;margin-top:8px">
            ${BT.statusBadge(item.verification_status)}
            <span class="badge badge-neutral">${BT.icon("gauge")}AI ${BT.pct(item.confidence_score, 1)}</span>
            <span class="badge badge-neutral">${BT.icon("map-pin")}${BT.esc(placeLabel(item))}</span>
          </div>
        </div>
      </div>
      <div class="callout neutral" style="margin:16px 0">
        ${BT.icon("info")}
        <div>
          <strong>Evidence from the submitter.</strong>
          ${BT.esc(item.observer_notes || "No observer notes were provided.")}
          ${item.model_version ? `<br><span class="tiny muted">Model: ${BT.esc(item.model_version)} · image quality: ${BT.esc(item.image_quality_status)}</span>` : ""}
        </div>
      </div>
      <div class="field">
        <label for="review-status">Review status</label>
        <select class="select" id="review-status">
          <option value="pending" ${item.verification_status === "pending" ? "selected" : ""}>Pending review</option>
          <option value="verified" ${item.verification_status === "verified" ? "selected" : ""}>Verified — a human checked it</option>
          <option value="needs_review" ${item.verification_status === "needs_review" ? "selected" : ""}>Needs review — more evidence required</option>
          <option value="rejected" ${item.verification_status === "rejected" ? "selected" : ""}>Rejected — identification is wrong</option>
        </select>
      </div>
      <div class="field">
        <label for="review-species">Correct identification (optional)</label>
        <select class="select" id="review-species">
          <option value="">Leave the AI label unchanged</option>
          ${speciesOptions(item.category, item.species_id)}
        </select>
        <span class="field-hint">Choosing a catalogue species replaces the stored label and links the record to that species.</span>
      </div>
      <div class="field">
        <label for="review-sensitive">Coordinate sensitivity</label>
        <select class="select" id="review-sensitive">
          <option value="">Leave unchanged</option>
          <option value="true">Mark sensitive — obscure the location</option>
          <option value="false">Not sensitive — show recorded precision</option>
        </select>
        <span class="field-hint">Use this for threatened species or nests. Location obscuration is applied server-side when map data is returned.</span>
      </div>
      <div class="field">
        <label for="review-notes">Review notes</label>
        <textarea class="textarea" id="review-notes" maxlength="1000" placeholder="What evidence did you check? e.g. leaf venation visible; matches species description.">${BT.esc(item.review_notes || "")}</textarea>
        <span class="field-hint">Notes are stored with the record and the audit entry.</span>
      </div>`;

    const modal = BT.modal({
      title: "Review observation",
      subtitle: `Record #${item.id} · submitted ${BT.datetime(item.created_at)}`,
      body,
      size: "lg",
      footer: `<button class="btn btn-secondary" type="button" data-close>Cancel</button>
               <button class="btn btn-primary" type="button" id="review-save">${BT.icon("save")}Save review</button>`,
    });
    BT.refreshIcons();
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    modal.element.querySelector("#review-save").addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const sensitiveValue = modal.element.querySelector("#review-sensitive").value;
      const speciesValue = modal.element.querySelector("#review-species").value;
      const payload = {
        verification_status: modal.element.querySelector("#review-status").value,
        review_notes: modal.element.querySelector("#review-notes").value.trim() || null,
      };
      if (speciesValue) payload.species_id = Number(speciesValue);
      if (sensitiveValue === "true") payload.sensitive = true;
      if (sensitiveValue === "false") payload.sensitive = false;

      BT.setBusy(button, true, "Saving…");
      try {
        await adminApi(`/api/admin/observations/${item.id}`, { method: "PATCH", body: payload });
        BT.closeModal();
        BT.toast("Review saved", "The observation status was updated and an audit entry recorded.", "success");
        if (state.section === "overview") loadOverview();
        else loadObservations();
      } catch (err) {
        BT.setBusy(button, false);
        if (err.status !== 401) BT.errorToast(err);
      }
    });
  }

  /* --------------------------------------------------------------- Destinations */
  function destinationRow(item) {
    const hasPin = item.latitude !== null && item.longitude !== null;
    return `<tr>
      <td><strong style="display:block">${BT.esc(item.name)}</strong><span class="tiny muted">${BT.esc(item.slug)}</span></td>
      <td>${BT.esc(categoryLabel(item.category))}</td>
      <td>${BT.esc(item.district || "Not recorded")}</td>
      <td>${hasPin ? BT.icon("map-pin") + " Pin recorded" : `<span class="muted">No pin</span>`}</td>
      <td>${BT.statusBadge(item.verification_status)}</td>
      <td>${item.last_verified_at ? BT.fmtDate(item.last_verified_at) : `<span class="muted">Never</span>`}</td>
      <td><button class="btn btn-secondary btn-sm" type="button" data-review-destination="${item.id}">${BT.icon("pencil")}Status</button></td>
    </tr>`;
  }

  async function loadDestinations() {
    const host = document.getElementById("admin-content");
    host.innerHTML = loadingPanel(4);
    const query = state.destinationStatus ? `?status_filter=${encodeURIComponent(state.destinationStatus)}` : "";
    try {
      const rows = await adminApi(`/api/admin/destinations${query}`);
      state.destinations = rows;
      const statuses = [
        ["", "All statuses"],
        ["provisional", "Provisional"],
        ["needs_review", "Needs review"],
        ["verified", "Verified"],
        ["rejected", "Rejected"],
      ];
      const toolbar = `<div class="row-between" style="margin-bottom:14px">
        <div class="row" style="gap:8px">
          <select class="select" id="admin-destination-status" style="width:auto;min-width:170px">
            ${statuses
              .map(([value, label]) => `<option value="${value}" ${state.destinationStatus === value ? "selected" : ""}>${label}</option>`)
              .join("")}
          </select>
          <button class="btn btn-secondary btn-sm" type="button" data-reload="destinations">${BT.icon("refresh-cw")}Refresh</button>
        </div>
        <span class="small muted">${BT.num(rows.length)} record${rows.length === 1 ? "" : "s"} shown</span>
      </div>`;
      if (!rows.length) {
        host.innerHTML =
          toolbar +
          `<div class="panel">${BT.emptyState("No destinations match", "Change the status filter to see other records.", "map-pinned")}</div>`;
      } else {
        host.innerHTML =
          toolbar +
          `<div class="table-wrap"><table class="table">
            <thead><tr><th>Destination</th><th>Category</th><th>District</th><th>Map</th><th>Status</th><th>Last verified</th><th></th></tr></thead>
            <tbody>${rows.map(destinationRow).join("")}</tbody>
          </table></div>
          <p class="tiny muted" style="margin:12px 0 0">Seed records are provisional. Changing a status does not edit hours, fees or coordinates — those require a separate source check.</p>`;
      }
      BT.refreshIcons();
      bindAdminContent();
    } catch (err) {
      if (err.status === 401) return;
      host.innerHTML = errorPanel(err, "destinations");
      bindAdminContent();
      BT.errorToast(err);
    }
  }

  function openDestinationReview(id) {
    const item = state.destinations.find((row) => row.id === id);
    if (!item) {
      BT.errorToast(new Error("That destination is no longer in the loaded list. Refresh and try again."));
      return;
    }
    const body = `
      <div class="callout neutral" style="margin-bottom:16px">
        ${BT.icon("info")}
        <div><strong>${BT.esc(item.name)}</strong><br>
          ${BT.esc(categoryLabel(item.category))} · ${BT.esc(item.district || "district not recorded")}
        </div>
      </div>
      <div class="field">
        <label for="destination-status">Verification status</label>
        <select class="select" id="destination-status">
          <option value="provisional" ${item.verification_status === "provisional" ? "selected" : ""}>Provisional — not yet source-checked</option>
          <option value="needs_review" ${item.verification_status === "needs_review" ? "selected" : ""}>Needs review — a concern was raised</option>
          <option value="verified" ${item.verification_status === "verified" ? "selected" : ""}>Verified — a human checked the source</option>
          <option value="rejected" ${item.verification_status === "rejected" ? "selected" : ""}>Rejected — should not be shown as a place</option>
        </select>
      </div>
      <div class="field">
        <label for="destination-note">Reason / source note (optional)</label>
        <textarea class="textarea" id="destination-note" maxlength="1000"
          placeholder="e.g. Checked against the official district tourism page on 2026-10-20."></textarea>
        <span class="field-hint">A note is stored as an audit record when provided. Never mark a record verified without checking a source.</span>
      </div>`;
    const modal = BT.modal({
      title: "Update destination status",
      subtitle: `Record #${item.id}`,
      body,
      footer: `<button class="btn btn-secondary" type="button" data-close>Cancel</button>
               <button class="btn btn-primary" type="button" id="destination-save">${BT.icon("save")}Save status</button>`,
    });
    BT.refreshIcons();
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    modal.element.querySelector("#destination-save").addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const payload = {
        verification_status: modal.element.querySelector("#destination-status").value,
        note: modal.element.querySelector("#destination-note").value.trim() || null,
      };
      BT.setBusy(button, true, "Saving…");
      try {
        await adminApi(`/api/admin/destinations/${item.id}`, { method: "PATCH", body: payload });
        BT.closeModal();
        BT.toast("Status updated", `${item.name} is now “${payload.verification_status.replace(/_/g, " ")}”.`, "success");
        loadDestinations();
      } catch (err) {
        BT.setBusy(button, false);
        if (err.status !== 401) BT.errorToast(err);
      }
    });
  }

  /* ------------------------------------------------------------------- Reports */
  function reportRow(item) {
    return `<tr>
      <td>#${item.id}</td>
      <td>${BT.esc(item.record_type)}</td>
      <td><strong>${BT.esc(item.record_label || `#${item.record_id || "?"}`)}</strong></td>
      <td>${BT.esc(String(item.reason || "").replace(/_/g, " "))}</td>
      <td>${BT.statusBadge(item.status)}</td>
      <td><span class="small muted">${BT.relative(item.created_at)}</span></td>
      <td><button class="btn btn-secondary btn-sm" type="button" data-open-report="${item.id}">${BT.icon("inbox")}Open</button></td>
    </tr>`;
  }

  async function loadReports() {
    const host = document.getElementById("admin-content");
    host.innerHTML = loadingPanel(4);
    const query = state.reportStatus ? `?status_filter=${encodeURIComponent(state.reportStatus)}` : "";
    try {
      const rows = await adminApi(`/api/admin/reports${query}`);
      const statuses = [
        ["", "All statuses"],
        ["open", "Open"],
        ["in_review", "In review"],
        ["resolved", "Resolved"],
        ["dismissed", "Dismissed"],
      ];
      const toolbar = `<div class="row-between" style="margin-bottom:14px">
        <div class="row" style="gap:8px">
          <select class="select" id="admin-report-status" style="width:auto;min-width:170px">
            ${statuses
              .map(([value, label]) => `<option value="${value}" ${state.reportStatus === value ? "selected" : ""}>${label}</option>`)
              .join("")}
          </select>
          <button class="btn btn-secondary btn-sm" type="button" data-reload="reports">${BT.icon("refresh-cw")}Refresh</button>
        </div>
        <span class="small muted">${BT.num(rows.length)} report${rows.length === 1 ? "" : "s"} shown</span>
      </div>`;
      if (!rows.length) {
        host.innerHTML =
          toolbar +
          `<div class="panel">${BT.emptyState(
            "No reports match this filter",
            "Visitor reports appear here when someone flags wrong information or an incorrect identification.",
            "flag"
          )}</div>`;
      } else {
        host.innerHTML =
          toolbar +
          `<div class="table-wrap"><table class="table">
            <thead><tr><th>ID</th><th>Type</th><th>Record</th><th>Reason</th><th>Status</th><th>Created</th><th></th></tr></thead>
            <tbody>${rows.map(reportRow).join("")}</tbody>
          </table></div>`;
      }
      BT.refreshIcons();
      bindAdminContent();
    } catch (err) {
      if (err.status === 401) return;
      host.innerHTML = errorPanel(err, "reports");
      bindAdminContent();
      BT.errorToast(err);
    }
  }

  async function openReport(id) {
    let report;
    try {
      report = await adminApi(`/api/admin/reports/${id}`);
    } catch (err) {
      if (err.status !== 401) BT.errorToast(err);
      return;
    }
    const body = `
      <div class="row" style="gap:6px;margin-bottom:14px">
        ${BT.statusBadge(report.status)}
        <span class="badge badge-neutral">${BT.icon("tag")}${BT.esc(report.record_type)}</span>
        <span class="badge badge-neutral">${BT.icon("hash")}${BT.esc(report.record_label || `#${report.record_id || "?"}`)}</span>
      </div>
      <div class="field">
        <label>Reason</label>
        <p class="small" style="margin:0">${BT.esc(String(report.reason || "").replace(/_/g, " "))}</p>
      </div>
      <div class="field">
        <label>Details from the reporter</label>
        <p class="small muted" style="margin:0;white-space:pre-wrap">${BT.esc(report.details || "No extra details were provided.")}</p>
      </div>
      <div class="field">
        <label>Filed</label>
        <p class="small" style="margin:0">${BT.datetime(report.created_at)}</p>
      </div>
      <div class="field">
        <label for="report-status">Set status</label>
        <select class="select" id="report-status">
          <option value="open" ${report.status === "open" ? "selected" : ""}>Open</option>
          <option value="in_review" ${report.status === "in_review" ? "selected" : ""}>In review</option>
          <option value="resolved" ${report.status === "resolved" ? "selected" : ""}>Resolved</option>
          <option value="dismissed" ${report.status === "dismissed" ? "selected" : ""}>Dismissed</option>
        </select>
        <span class="field-hint">Use “Resolved” only after the underlying record was checked. This action does not edit the record itself.</span>
      </div>`;
    const modal = BT.modal({
      title: `Report #${report.id}`,
      subtitle: "Visitor-submitted problem report",
      body,
      footer: `<button class="btn btn-secondary" type="button" data-close>Close</button>
               <button class="btn btn-primary" type="button" id="report-save">${BT.icon("save")}Update status</button>`,
    });
    BT.refreshIcons();
    modal.element.querySelector("[data-close]").addEventListener("click", BT.closeModal);
    modal.element.querySelector("#report-save").addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const status = modal.element.querySelector("#report-status").value;
      BT.setBusy(button, true, "Saving…");
      try {
        await adminApi(`/api/admin/reports/${report.id}`, { method: "PATCH", body: { status } });
        BT.closeModal();
        BT.toast("Report updated", `Marked as ${status.replace(/_/g, " ")}.`, "success");
        if (state.section === "overview") loadOverview();
        else loadReports();
      } catch (err) {
        BT.setBusy(button, false);
        if (err.status !== 401) BT.errorToast(err);
      }
    });
  }

  /* ------------------------------------------------------------- Event wiring */
  function bindAdminContent() {
    const host = document.getElementById("admin-content");
    if (!host || host.dataset.bound === "true") return;
    host.dataset.bound = "true";

    host.addEventListener("click", (event) => {
      const goto = event.target.closest("[data-goto]");
      if (goto) {
        setSection(goto.dataset.goto);
        return;
      }
      const reviewObs = event.target.closest("[data-review-observation]");
      if (reviewObs) {
        openObservationReview(Number(reviewObs.dataset.reviewObservation));
        return;
      }
      const reviewDest = event.target.closest("[data-review-destination]");
      if (reviewDest) {
        openDestinationReview(Number(reviewDest.dataset.reviewDestination));
        return;
      }
      const openReportButton = event.target.closest("[data-open-report]");
      if (openReportButton) {
        openReport(Number(openReportButton.dataset.openReport));
        return;
      }
      const reload = event.target.closest("[data-reload]");
      if (reload) {
        setSection(reload.dataset.reload);
        return;
      }
      const retry = event.target.closest("[data-retry]");
      if (retry) {
        setSection(retry.dataset.retry || state.section);
      }
    });

    host.addEventListener("change", (event) => {
      if (event.target.id === "admin-observation-status") {
        state.observationStatus = event.target.value;
        loadObservations();
      } else if (event.target.id === "admin-destination-status") {
        state.destinationStatus = event.target.value;
        loadDestinations();
      } else if (event.target.id === "admin-report-status") {
        state.reportStatus = event.target.value;
        loadReports();
      }
    });
  }

  function setSection(name) {
    if (!SECTIONS[name]) name = "overview";
    state.section = name;
    const meta = SECTIONS[name];
    const title = document.getElementById("admin-section-title");
    const sub = document.getElementById("admin-section-sub");
    if (title) title.textContent = meta.title;
    if (sub) sub.textContent = meta.subtitle;

    BT.qsa(".admin-nav [data-section]").forEach((button) => {
      const active = button.dataset.section === name;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    });

    if (name === "overview") loadOverview();
    else if (name === "observations") loadObservations();
    else if (name === "destinations") loadDestinations();
    else if (name === "reports") loadReports();
  }

  function setupLoginEvents() {
    const form = document.getElementById("admin-login-form");
    if (form) form.addEventListener("submit", handleLogin);

    const toggle = document.getElementById("admin-password-toggle");
    const password = document.getElementById("admin-password");
    if (toggle && password) {
      toggle.addEventListener("click", () => {
        const showing = password.type === "text";
        password.type = showing ? "password" : "text";
        toggle.setAttribute("aria-pressed", String(!showing));
        toggle.setAttribute("aria-label", showing ? "Show password" : "Hide password");
        toggle.innerHTML = `<i data-lucide="${showing ? "eye" : "eye-off"}" aria-hidden="true"></i>`;
        BT.refreshIcons();
      });
    }

    BT.qsa(".admin-nav [data-section]").forEach((button) => {
      button.addEventListener("click", () => setSection(button.dataset.section));
    });

    const logoutButton = document.getElementById("admin-logout");
    if (logoutButton) logoutButton.addEventListener("click", () => logout(false));

    const refresh = document.getElementById("admin-refresh");
    if (refresh) refresh.addEventListener("click", () => setSection(state.section));
  }

  async function init() {
    BT.refreshIcons();
    setupLoginEvents();
    state.token = readToken();
    state.username = readUser();

    if (!state.token) {
      showLogin("");
      return;
    }
    showApp();
    await setSection("overview");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
