/* ==========================================================================
   My Utkal Heritage — biodiversity identification studio
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;

  const state = {
    category: "plant",
    file: null,
    previewUrl: null,
    prediction: null,
    saved: false,
    species: [],
    speciesById: new Map(),
    speciesFilter: "all",
    speciesQuery: "",
  };

  const DECISION_COPY = {
    accept: {
      icon: "check-circle-2",
      title: "Prediction clears the threshold — still not verified",
      body: "The model's top candidate passed the abstention threshold. Treat this as a lead, not a confirmed record.",
    },
    review: {
      icon: "alert-triangle",
      title: "My Utkal Heritage is abstaining — human review needed",
      body: "The evidence is ambiguous, the image has quality flags, or the location conflicts with the curated range.",
    },
    reject: {
      icon: "x-circle",
      title: "No prediction attempted",
      body: "The photo failed basic quality checks, so the model was not run. Try a closer, brighter, sharper photo.",
    },
    unavailable: {
      icon: "cloud-off",
      title: "Model unavailable",
      body: "No trained model is installed for this category. My Utkal Heritage will not invent a label.",
    },
  };

  function setCategory(category) {
    state.category = category;
    BT.qsa("#category-switch button").forEach((button) => {
      const active = button.dataset.category === category;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function resetUpload() {
    state.file = null;
    state.prediction = null;
    state.saved = false;
    if (state.previewUrl) {
      URL.revokeObjectURL(state.previewUrl);
      state.previewUrl = null;
    }
    const input = document.getElementById("image-input");
    if (input) input.value = "";
    document.getElementById("upload-empty").classList.remove("hidden");
    document.getElementById("upload-preview").classList.add("hidden");
    document.getElementById("upload-zone").classList.remove("has-image");
    const button = document.getElementById("analyse-btn");
    if (button) button.disabled = true;
    renderInitialResult();
  }

  function handleFile(file) {
    if (!file) return;
    const allowed = ["image/jpeg", "image/png", "image/webp"];
    if (!allowed.includes(file.type)) {
      BT.toast("Unsupported file", "Choose a JPEG, PNG or WEBP photograph.", "error");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      BT.toast("Image too large", "The upload limit is 8 MB. Compress the photo and try again.", "error");
      return;
    }
    state.file = file;
    state.prediction = null;
    state.saved = false;
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = URL.createObjectURL(file);
    const image = document.getElementById("preview-image");
    image.src = state.previewUrl;
    document.getElementById("preview-name").textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
    document.getElementById("upload-empty").classList.add("hidden");
    document.getElementById("upload-preview").classList.remove("hidden");
    document.getElementById("upload-zone").classList.add("has-image");
    document.getElementById("analyse-btn").disabled = false;
    renderInitialResult();
    BT.refreshIcons();
  }

  function renderInitialResult() {
    const host = document.getElementById("result-body");
    if (!host) return;
    host.innerHTML = `<div class="state">
      <div class="state-icon">${BT.icon("scan-line")}</div>
      <h3>${state.file ? "Ready to analyse" : "No image analysed yet"}</h3>
      <p>${
        state.file
          ? "Your photo is loaded locally. Press “Analyse image” to run the quality checks and the model. Nothing is uploaded until you do."
          : "Choose a plant or bird photo and press “Analyse image”. The result will explain what the model saw, how confident it is, and why it may be abstaining."
      }</p>
    </div>`;
    BT.refreshIcons();
  }

  function renderModelStatus(status) {
    const host = document.getElementById("model-status");
    if (!host) return;
    const plant = status.plant || {};
    const bird = status.bird || {};
    if (!status.torch_installed) {
      host.className = "callout warning";
      host.innerHTML = `${BT.icon("alert-triangle")}<div><strong>PyTorch is not installed.</strong> Predictions will return “unavailable”. Install the CPU build with <span class="mono">pip install -r requirements-ai.txt</span>.</div>`;
    } else if (!plant.available && !bird.available) {
      host.className = "callout warning";
      host.innerHTML = `${BT.icon("alert-triangle")}<div>
        <strong>No trained model is installed yet.</strong>
        The upload, quality checks and observation workflow still work, but predictions will explicitly return
        <em>unavailable</em> rather than a made-up species. Train the demo models with
        <span class="mono">python -m backend.scripts.train_classifier --category plant</span>.
        <a href="/about.html#models">Read the model documentation</a>.
      </div>`;
    } else {
      const bits = [];
      if (plant.available) bits.push(`plant: ${plant.classes} classes, threshold ${BT.pct(plant.threshold)}`);
      if (bird.available) bits.push(`bird: ${bird.classes} classes, threshold ${BT.pct(bird.threshold)}`);
      host.className = "callout success";
      host.innerHTML = `${BT.icon("check-circle-2")}<div><strong>Model registry ready.</strong> ${BT.esc(bits.join(" · "))}. Predictions remain preliminary and are never displayed as verified records.</div>`;
    }
    BT.refreshIcons();
  }

  function renderQuality(quality) {
    if (!quality) return "";
    const statusClass = quality.status === "good" ? "ok" : quality.status === "warning" ? "warn" : "bad";
    return `<div class="quality-grid" style="margin:14px 0">
      <div class="quality-item"><span>Resolution</span><strong>${quality.width || "?"} × ${quality.height || "?"}</strong></div>
      <div class="quality-item"><span>Brightness</span><strong>${quality.brightness === null || quality.brightness === undefined ? "—" : Number(quality.brightness).toFixed(1)}</strong></div>
      <div class="quality-item"><span>Sharpness</span><strong>${quality.sharpness === null || quality.sharpness === undefined ? "—" : Number(quality.sharpness).toFixed(1)}</strong></div>
    </div>
    <div class="row" style="gap:8px;margin-bottom:8px">
      <span class="badge ${statusClass === "ok" ? "badge-verified" : statusClass === "warn" ? "badge-pending" : "badge-rejected"}">
        ${BT.icon(statusClass === "ok" ? "check" : statusClass === "warn" ? "alert-triangle" : "x-circle")}
        Quality: ${BT.esc(quality.status)}
      </span>
      <span class="tiny muted">${quality.usable ? "Usable for classification" : "Rejected before classification"}</span>
    </div>
    ${quality.issues && quality.issues.length ? `<div class="quality-issues">${quality.issues.map((issue) => `<span class="quality-issue">${BT.esc(issue)}</span>`).join("")}</div>` : ""}
    ${quality.notes && quality.notes.length ? `<p class="tiny muted" style="margin:8px 0 0">${quality.notes.map(BT.esc).join(" ")}</p>` : ""}`;
  }

  function renderPredictions(predictions) {
    if (!predictions || !predictions.length) return "";
    return `<div style="margin:6px 0 4px">${predictions
      .map(
        (item, index) => `<div class="prediction ${index === 0 ? "top" : ""}">
          <div class="pred-rank">${item.rank || index + 1}</div>
          <div>
            <div class="pred-name">${BT.esc(item.common_name || item.scientific_name)}</div>
            <div class="pred-sci">${BT.esc(item.scientific_name)}</div>
          </div>
          <div class="pred-score">${BT.pct(item.confidence, 1)}</div>
          <div class="pred-bar"><span style="width:${Math.max(2, Math.round(item.confidence * 100))}%"></span></div>
        </div>`
      )
      .join("")}</div>`;
  }

  function renderLocation(location) {
    if (!location) return "";
    const map = {
      plausible: ["ok", "check-circle-2", "Location is consistent with the curated distribution record."],
      outside_known_range: ["bad", "map-pin-off", "Location conflicts with the curated distribution record."],
      unavailable: ["warn", "help-circle", "No curated distribution record is available for this species."],
      not_provided: ["warn", "map-pin-off", "No location supplied; the result is image-only."],
    };
    const [cls, icon, fallback] = map[location.status] || ["warn", "help-circle", "Location check unavailable."];
    return `<div class="check-row ${cls}" style="padding:8px 0">
      ${BT.icon(icon)}<span><strong>${BT.esc(location.status.replace(/_/g, " "))}</strong> — ${BT.esc(location.message || fallback)}</span>
    </div>`;
  }

  function renderResult(prediction) {
    const host = document.getElementById("result-body");
    if (!host) return;
    const decision = prediction.decision || "unavailable";
    const copy = DECISION_COPY[decision] || DECISION_COPY.unavailable;
    const canSave = (decision === "accept" || decision === "review") && prediction.top_predictions && prediction.top_predictions.length;

    host.innerHTML = `
      <div class="decision-banner ${BT.esc(decision)}">
        <div class="decision-icon">${BT.icon(copy.icon)}</div>
        <div>
          <h4>${BT.esc(copy.title)}</h4>
          <p>${BT.esc(copy.body)}</p>
        </div>
      </div>
      ${prediction.abstain_reason ? `<div class="callout warning" style="margin-top:14px">${BT.icon("alert-triangle")}<div><strong>Why:</strong> ${BT.esc(prediction.abstain_reason)}</div></div>` : ""}
      <h4 style="margin:20px 0 8px">Image quality</h4>
      ${renderQuality(prediction.quality)}
      ${
        prediction.top_predictions && prediction.top_predictions.length
          ? `<h4 style="margin:18px 0 4px">Top candidates</h4>
             <p class="tiny muted" style="margin:0 0 6px">Softmax scores from the installed ${BT.esc(prediction.category)} model${
               prediction.threshold ? ` · abstention threshold ${BT.pct(prediction.threshold)}` : ""
             }.</p>
             ${renderPredictions(prediction.top_predictions)}`
          : ""
      }
      ${prediction.location_check ? `<h4 style="margin:18px 0 4px">Location plausibility</h4>${renderLocation(prediction.location_check)}` : ""}
      <h4 style="margin:18px 0 6px">What this means</h4>
      <p class="small muted" style="line-height:1.7">${BT.esc(prediction.explanation || "")}</p>
      ${
        prediction.limitations && prediction.limitations.length
          ? `<details style="margin-top:12px"><summary class="small strong" style="cursor:pointer">Known limitations (${prediction.limitations.length})</summary>
             <ul class="small muted" style="margin:10px 0 0;padding-left:20px;line-height:1.7">${prediction.limitations
               .map((item) => `<li>${BT.esc(item)}</li>`)
               .join("")}</ul></details>`
          : ""
      }
      <div class="callout neutral" style="margin-top:16px">${BT.icon("info")}<div>${BT.esc(prediction.disclaimer || "")}</div></div>
      ${
        canSave
          ? `<div style="margin-top:18px" id="save-observation-block">
               <h4 style="margin-bottom:6px">Save as a pending observation</h4>
               <p class="tiny muted" style="margin-bottom:10px">Saving stores the photo and metadata on this server. It becomes publicly visible with a “pending review” badge. You must tick the consent box in the left panel first.</p>
               <button class="btn btn-primary" id="save-observation" type="button">${BT.icon("bookmark-plus")}Save observation</button>
             </div>`
          : `<div class="callout neutral" style="margin-top:16px">${BT.icon("lock")}<div>This result cannot be saved as an observation. ${
              decision === "unavailable"
                ? "Install a trained model first."
                : decision === "reject"
                ? "Use a clearer photograph and analyse again."
                : ""
            }</div></div>`
      }
    `;
    BT.refreshIcons();

    if (canSave) {
      const button = document.getElementById("save-observation");
      if (button) button.addEventListener("click", saveObservation);
    }
  }

  function renderError(message) {
    const host = document.getElementById("result-body");
    if (!host) return;
    host.innerHTML = `<div class="state error">
      <div class="state-icon">${BT.icon("alert-circle")}</div>
      <h3>Analysis failed</h3>
      <p>${BT.esc(message)}</p>
      <button class="btn btn-secondary" type="button" id="retry-analysis">Try again</button>
    </div>`;
    const retry = document.getElementById("retry-analysis");
    if (retry) retry.addEventListener("click", () => document.getElementById("bio-form").requestSubmit());
    BT.refreshIcons();
  }

  async function analyse(event) {
    event.preventDefault();
    if (!state.file) {
      BT.toast("No photograph", "Choose an image first.", "info");
      return;
    }
    const button = document.getElementById("analyse-btn");
    BT.setBusy(button, true, "Checking image…");
    const form = new FormData();
    form.append("file", state.file);
    form.append("category", state.category);
    const district = document.getElementById("bio-district").value;
    const lat = document.getElementById("bio-lat").value;
    const lon = document.getElementById("bio-lon").value;
    if (district) form.append("district", district);
    if (lat && lon) {
      form.append("latitude", lat);
      form.append("longitude", lon);
    }
    try {
      const prediction = await BT.upload("/api/biodiversity/predict", form);
      state.prediction = prediction;
      state.saved = false;
      renderResult(prediction);
      if (prediction.decision === "unavailable") {
        BT.toast("Model unavailable", "The app returned an honest “unavailable” result instead of a fabricated label.", "info", 7000);
      }
      document.getElementById("result-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      renderError(err.message);
      BT.errorToast(err);
    } finally {
      BT.setBusy(button, false);
    }
  }

  async function saveObservation() {
    if (!state.prediction || !state.file) return;
    const consent = document.getElementById("bio-consent");
    if (!consent.checked) {
      BT.toast("Consent required", "Tick the consent checkbox before saving an observation.", "error");
      consent.focus();
      return;
    }
    if (state.saved) return;
    const top = state.prediction.top_predictions[0];
    const button = document.getElementById("save-observation");
    BT.setBusy(button, true, "Saving…");
    const form = new FormData();
    form.append("file", state.file);
    form.append("predicted_species", top.scientific_name);
    if (top.common_name) form.append("predicted_common_name", top.common_name);
    form.append("category", state.category);
    form.append("confidence_score", String(top.confidence));
    form.append("top_predictions", JSON.stringify(state.prediction.top_predictions));
    form.append("image_quality_status", state.prediction.quality.status);
    if (state.prediction.quality.issues && state.prediction.quality.issues.length) {
      form.append("image_quality_notes", state.prediction.quality.issues.join("; "));
    }
    const district = document.getElementById("bio-district").value;
    const lat = document.getElementById("bio-lat").value;
    const lon = document.getElementById("bio-lon").value;
    if (district) form.append("district", district);
    if (lat && lon) {
      form.append("latitude", lat);
      form.append("longitude", lon);
      form.append("location_precision", "exact");
    } else {
      form.append("location_precision", "none");
    }
    const notes = document.getElementById("bio-notes").value.trim();
    if (notes) form.append("observer_notes", notes);
    if (state.prediction.model_version) form.append("model_version", state.prediction.model_version);
    form.append("consent", "true");

    try {
      const saved = await BT.upload("/api/biodiversity/observations", form);
      state.saved = true;
      const block = document.getElementById("save-observation-block");
      if (block) {
        block.innerHTML = `<div class="callout success">${BT.icon("check-circle-2")}<div>
          <strong>Observation saved as pending.</strong> Record #${saved.id}. It is visible in your observations and will stay pending until a human reviews it.
          <div class="row" style="margin-top:8px">
            <a class="btn btn-secondary btn-sm" href="/observations.html">View my observations</a>
            <a class="btn btn-ghost btn-sm" href="/biodiversity.html">Identify another</a>
          </div>
        </div></div>`;
      }
      BT.toast("Observation saved", "Thank you. It is now pending human review.", "success");
      BT.refreshIcons();
    } catch (err) {
      BT.setBusy(button, false);
      BT.errorToast(err);
    }
  }

  function renderSpecies() {
    const host = document.getElementById("species-grid");
    if (!host) return;
    const query = state.speciesQuery.toLowerCase();
    const rows = state.species.filter((item) => {
      const matchesCategory = state.speciesFilter === "all" || item.category === state.speciesFilter;
      const haystack = `${item.common_name} ${item.scientific_name} ${item.description || ""}`.toLowerCase();
      return matchesCategory && (!query || haystack.includes(query));
    });
    const count = document.getElementById("species-count");
    if (count) count.textContent = `${rows.length} of ${state.species.length} species`;
    if (!rows.length) {
      host.innerHTML = BT.emptyState("No matching species", "Try a different search term or category.", "search");
      BT.refreshIcons();
      return;
    }
    host.innerHTML = rows
      .map((item) => {
        const images = item.images || [];
        const cover = images[0];
        return `<button class="species-card" type="button" data-species-id="${item.id}"
                  aria-label="Open photographs and sources for ${BT.esc(item.common_name)}">
          <span class="species-card-media">
            ${
              cover
                ? `<img class="species-cover" src="${BT.esc(cover.thumbnail_url || cover.url)}"
                       alt="${BT.esc(cover.title || item.common_name)}" loading="lazy"
                       decoding="async" referrerpolicy="no-referrer" />`
                : `<span class="sp-icon ${item.category === "bird" ? "bird" : ""}">${BT.icon(item.category === "bird" ? "bird" : "leaf")}</span>`
            }
            ${
              images.length
                ? `<span class="species-photo-count">${BT.icon("images")}${images.length} photo${images.length === 1 ? "" : "s"}</span>`
                : `<span class="species-photo-count is-empty">${BT.icon("image-off")}No free photo</span>`
            }
          </span>
          <span class="species-card-body">
            <strong>${BT.esc(item.common_name)}</strong>
            <em>${BT.esc(item.scientific_name)}</em>
            <span class="sp-desc">${BT.esc(item.description || "No description recorded.")}</span>
            <span class="row" style="gap:6px;margin-top:10px">
              <span class="badge ${item.category === "bird" ? "badge-review" : "badge-verified"}">${item.category === "bird" ? "Bird" : "Plant"}</span>
              ${item.conservation_status ? `<span class="chip">${BT.esc(item.conservation_status)}</span>` : ""}
            </span>
            <span class="species-card-link">Photos &amp; sources ${BT.icon("arrow-right")}</span>
          </span>
        </button>`;
      })
      .join("");
    BT.refreshIcons();
  }

  async function init() {
    const input = document.getElementById("image-input");
    const zone = document.getElementById("upload-zone");
    const form = document.getElementById("bio-form");

    zone.addEventListener("click", (event) => {
      if (event.target.closest("#remove-image")) return;
      input.click();
    });
    zone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        input.click();
      }
    });
    input.addEventListener("change", () => handleFile(input.files[0]));
    document.getElementById("remove-image").addEventListener("click", (event) => {
      event.stopPropagation();
      resetUpload();
    });
    ["dragenter", "dragover"].forEach((name) => {
      zone.addEventListener(name, (event) => {
        event.preventDefault();
        zone.classList.add("is-dragging");
      });
    });
    ["dragleave", "drop"].forEach((name) => {
      zone.addEventListener(name, (event) => {
        event.preventDefault();
        zone.classList.remove("is-dragging");
      });
    });
    zone.addEventListener("drop", (event) => {
      if (event.dataTransfer.files && event.dataTransfer.files.length) handleFile(event.dataTransfer.files[0]);
    });

    BT.qsa("#category-switch button").forEach((button) => {
      button.addEventListener("click", () => setCategory(button.dataset.category));
    });
    form.addEventListener("submit", analyse);

    document.getElementById("use-location").addEventListener("click", async () => {
      try {
        const position = await BT.geolocate();
        document.getElementById("bio-lat").value = position.lat.toFixed(5);
        document.getElementById("bio-lon").value = position.lon.toFixed(5);
        BT.toast("Location added", `Accuracy about ${Math.round(position.accuracy)} m. You can still clear or edit it.`, "success");
      } catch (err) {
        BT.toast("Location unavailable", err.message, "error");
      }
    });

    const speciesGrid = document.getElementById("species-grid");
    if (speciesGrid) {
      speciesGrid.addEventListener("click", (event) => {
        const card = event.target.closest("[data-species-id]");
        if (!card) return;
        const species = state.speciesById.get(Number(card.dataset.speciesId));
        if (species) BT.speciesModal(species);
      });
    }

    const search = document.getElementById("species-search");
    if (search) {
      search.addEventListener(
        "input",
        BT.debounce(() => {
          state.speciesQuery = search.value.trim();
          renderSpecies();
        }, 180)
      );
    }
    BT.qsa("#species-filter button").forEach((button) => {
      button.addEventListener("click", () => {
        state.speciesFilter = button.dataset.speciesFilter;
        BT.qsa("#species-filter button").forEach((item) => item.classList.toggle("is-active", item === button));
        renderSpecies();
      });
    });

    try {
      const [status, taxonomy, species] = await Promise.all([
        BT.api("/api/biodiversity/model-status"),
        BT.loadTaxonomy(),
        BT.api("/api/biodiversity/species"),
      ]);
      renderModelStatus(status);
      const select = document.getElementById("bio-district");
      (taxonomy.districts || []).forEach((district) => {
        const option = document.createElement("option");
        option.value = district;
        option.textContent = district;
        select.appendChild(option);
      });
      state.species = species;
      state.speciesById = new Map(species.map((item) => [Number(item.id), item]));
      renderSpecies();
    } catch (err) {
      renderModelStatus({ torch_installed: true, plant: {}, bird: {} });
      BT.errorToast(err);
    }

    // Shareable deep link: /biodiversity.html?species=<id or scientific name>
    const speciesParam = new URLSearchParams(location.search).get("species");
    if (speciesParam) {
      const species = /^\d+$/.test(speciesParam)
        ? state.speciesById.get(Number(speciesParam))
        : state.species.find(
            (item) =>
              item.scientific_name.toLowerCase() === speciesParam.trim().toLowerCase()
          );
      if (species) BT.speciesModal(species);
    }
    BT.refreshIcons();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
