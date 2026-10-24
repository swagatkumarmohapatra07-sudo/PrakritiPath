/* ==========================================================================
   My Utkal Heritage — about page
   Populates live database counts and the real model registry status.
   Nothing on this page may be hard-coded as a performance claim.
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;

  const METRIC_LABELS = {
    top1_accuracy: "Top-1 accuracy",
    top3_accuracy: "Top-3 accuracy",
    macro_f1: "Macro F1",
    coverage: "Coverage above threshold",
    selective_accuracy: "Accuracy above threshold",
    test_loss: "Test loss",
    val_accuracy: "Validation accuracy",
    val_loss: "Validation loss",
    temperature: "Fitted temperature",
    threshold: "Abstention threshold",
    num_classes: "Classes",
    train_images: "Training images",
    val_images: "Validation images",
    test_images: "Test images",
  };

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function renderStats(stats) {
    setText("about-destinations", BT.num(stats.destinations_total));
    setText("about-species", BT.num(stats.species_catalogued));
    setText("about-observations", BT.num(stats.observations_total));
    setText("about-districts", BT.num(stats.districts_covered));
    const note = document.getElementById("about-verified-note");
    if (note) {
      note.textContent =
        `${BT.num(stats.destinations_verified)} verified destinations · ` +
        `${BT.num(stats.observations_verified)} verified observations`;
    }
  }

  function metricRows(source) {
    if (!source || typeof source !== "object") return "";
    const rows = [];
    Object.keys(METRIC_LABELS).forEach((key) => {
      const value = source[key];
      if (value === null || value === undefined) return;
      let display;
      if (key === "temperature") display = Number(value).toFixed(2);
      else if (key === "threshold") display = BT.pct(value, 1);
      else if (key === "num_classes" || key.endsWith("_images")) display = BT.num(value);
      else if (key === "test_loss" || key === "val_loss") display = Number(value).toFixed(3);
      else if (typeof value === "number" && value >= 0 && value <= 1) display = BT.pct(value, 1);
      else display = BT.esc(value);
      rows.push(`<div class="metric-row"><span>${BT.esc(METRIC_LABELS[key])}</span><strong>${display}</strong></div>`);
    });
    return rows.join("");
  }

  function modelCard(category, info) {
    const isPlant = category === "plant";
    const title = isPlant ? "Plant classifier" : "Bird classifier";
    const icon = isPlant ? "leaf" : "bird";
    const architecture = info.version || "MobileNetV3-small";
    if (!info.available) {
      const reason = info.reason || (info.installed
        ? "The checkpoint exists but could not be loaded."
        : "No checkpoint is installed.");
      return `<article class="panel" data-model="${category}">
        <div class="panel-head">
          <div class="row" style="gap:10px">
            <span class="cc-icon cc-green" style="width:38px;height:38px;margin:0">${BT.icon(icon)}</span>
            <div><h3 style="margin:0">${title}</h3><p style="margin:0">${BT.esc(architecture)}</p></div>
          </div>
          <span class="badge badge-neutral">${BT.icon("circle-slash")}Not installed</span>
        </div>
        <div class="callout warning" style="margin:0">
          ${BT.icon("alert-triangle")}
          <div>
            <strong>Identification is unavailable for this category.</strong>
            <p class="small" style="margin:6px 0 0">${BT.esc(reason)} My Utkal Heritage returns an
            “unavailable” decision instead of inventing a label. No accuracy figure is shown
            because no real evaluation exists for this checkpoint.</p>
          </div>
        </div>
        <p class="tiny muted" style="margin:14px 0 0">
          Expected checkpoint: <span class="mono">${BT.esc(info.path || `models/${category}/model.pt`)}</span>.
          Train it with <span class="mono">python -m backend.scripts.train_classifier --category ${category}</span>.
        </p>
      </article>`;
    }

    const classes = info.classes || 0;
    const metrics = metricRows(info.test_metrics);
    return `<article class="panel" data-model="${category}">
      <div class="panel-head">
        <div class="row" style="gap:10px">
          <span class="cc-icon cc-green" style="width:38px;height:38px;margin:0">${BT.icon(icon)}</span>
          <div><h3 style="margin:0">${title}</h3><p style="margin:0">${BT.esc(architecture)}</p></div>
        </div>
        <span class="badge badge-verified">${BT.icon("check-circle-2")}Installed</span>
      </div>
      <div class="metric-row"><span>Classes covered</span><strong>${BT.num(classes)}</strong></div>
      <div class="metric-row"><span>Abstention threshold</span><strong>${BT.pct(info.threshold, 1)}</strong></div>
      <div class="metric-row"><span>Trained</span><strong>${BT.esc(info.trained_at || "Not recorded")}</strong></div>
      ${metrics}
      ${
        metrics
          ? ""
          : `<div class="callout neutral" style="margin-top:14px">${BT.icon("info")}<div>
               <strong>No held-out metrics recorded.</strong>
               <p class="small" style="margin:6px 0 0">The checkpoint loads, but its model card does not contain
               evaluation results. Treat predictions as unvalidated.</p>
             </div></div>`
      }
      <p class="tiny muted" style="margin:14px 0 0">
        Metrics come from the checkpoint’s own model card. They describe a small demonstration
        dataset and are not field accuracy.
      </p>
    </article>`;
  }

  function renderModels(data) {
    const host = document.getElementById("model-cards");
    if (!host) return;
    host.innerHTML = [modelCard("plant", data.plant || {}), modelCard("bird", data.bird || {})].join("");
    BT.refreshIcons();
  }

  function renderModelError(error) {
    const host = document.getElementById("model-cards");
    if (!host) return;
    host.innerHTML = `<div class="panel" style="grid-column:1/-1">
      ${BT.emptyState(
        "Model status could not be read",
        error.message || "The model registry endpoint did not respond.",
        "cloud-off",
        `<button class="btn btn-secondary btn-sm" id="model-retry" type="button">${BT.icon("refresh-cw")}Try again</button>`
      )}
    </div>`;
    const retry = document.getElementById("model-retry");
    if (retry) {
      retry.addEventListener("click", () => {
        host.innerHTML =
          `<div class="panel"><div class="skeleton skeleton-line w-40"></div><div class="skeleton skeleton-line"></div></div>` +
          `<div class="panel"><div class="skeleton skeleton-line w-40"></div><div class="skeleton skeleton-line"></div></div>`;
        loadModels();
      });
    }
    BT.refreshIcons();
  }

  async function loadModels() {
    try {
      const data = await BT.api("/api/biodiversity/model-status");
      renderModels(data);
    } catch (err) {
      renderModelError(err);
    }
  }

  function renderSpeciesSummary(taxonomy) {
    const host = document.getElementById("about-species-summary");
    if (!host) return;
    const species = (taxonomy && taxonomy.species) || [];
    if (!species.length) {
      host.innerHTML = `<p class="small muted" style="margin:0">The species catalogue is empty.</p>`;
      return;
    }
    const plants = species.filter((item) => item.category === "plant").length;
    const birds = species.filter((item) => item.category === "bird").length;
    const sensitive = species.filter((item) =>
      /endangered|vulnerable|critically/i.test(item.conservation_status || "")
    ).length;
    host.innerHTML = `
      <div class="metric-row"><span>Plant species in catalogue</span><strong>${BT.num(plants)}</strong></div>
      <div class="metric-row"><span>Bird species in catalogue</span><strong>${BT.num(birds)}</strong></div>
      <div class="metric-row"><span>Flagged as threatened</span><strong>${BT.num(sensitive)}</strong></div>
      <div class="metric-row"><span>Catalogue total</span><strong>${BT.num(species.length)}</strong></div>`;
  }

  async function init() {
    BT.refreshIcons();
    const results = await Promise.allSettled([
      BT.api("/api/stats"),
      BT.loadTaxonomy(),
      BT.api("/api/biodiversity/model-status"),
    ]);

    if (results[0].status === "fulfilled") {
      renderStats(results[0].value);
    } else {
      ["about-destinations", "about-species", "about-observations", "about-districts"].forEach(
        (id) => setText(id, "—")
      );
      const note = document.getElementById("about-verified-note");
      if (note) note.textContent = "Live counts unavailable — server not reachable.";
    }

    if (results[1].status === "fulfilled") {
      renderSpeciesSummary(results[1].value);
    }

    if (results[2].status === "fulfilled") {
      renderModels(results[2].value);
    } else {
      renderModelError(results[2].reason || new Error("Model status unavailable."));
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
