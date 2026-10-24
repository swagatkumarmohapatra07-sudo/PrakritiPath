/* ==========================================================================
   BioTrace — observation list
   ========================================================================== */
(function () {
  "use strict";

  const BT = window.BT;
  const PAGE_SIZE = 12;

  const state = {
    scope: "mine",
    category: "",
    status: "",
    district: "",
    page: 1,
  };

  function renderPagination(total) {
    const host = document.getElementById("obs-pagination");
    const pages = Math.ceil(total / PAGE_SIZE);
    if (pages <= 1) {
      host.innerHTML = "";
      return;
    }
    const buttons = [];
    buttons.push(`<button type="button" data-page="${state.page - 1}" ${state.page <= 1 ? "disabled" : ""} aria-label="Previous page">${BT.icon("chevron-left")}</button>`);
    for (let page = 1; page <= pages; page += 1) {
      if (pages > 7 && Math.abs(page - state.page) > 2 && page !== 1 && page !== pages) continue;
      buttons.push(`<button type="button" data-page="${page}" class="${page === state.page ? "is-active" : ""}" aria-current="${page === state.page ? "page" : "false"}">${page}</button>`);
    }
    buttons.push(`<button type="button" data-page="${state.page + 1}" ${state.page >= pages ? "disabled" : ""} aria-label="Next page">${BT.icon("chevron-right")}</button>`);
    host.innerHTML = `<span class="page-info">Page ${state.page} of ${pages}</span>${buttons.join("")}`;
    BT.qsa("button[data-page]", host).forEach((button) => {
      button.addEventListener("click", () => {
        const page = Number(button.dataset.page);
        if (page >= 1 && page <= pages) {
          state.page = page;
          load();
        }
      });
    });
    BT.refreshIcons();
  }

  function scopeNote() {
    const host = document.getElementById("scope-note");
    if (state.scope === "mine") {
      host.className = "callout info";
      host.innerHTML = `${BT.icon("info")}<div>Showing records submitted from this browser session. Only this browser can delete them. Switch to “All consented” to see public records from every visitor.</div>`;
    } else {
      host.className = "callout neutral";
      host.innerHTML = `${BT.icon("users")}<div>Public view: only consented observations are shown. Sensitive coordinates are approximated server-side before display.</div>`;
    }
    BT.refreshIcons();
  }

  async function load() {
    const host = document.getElementById("obs-list");
    const count = document.getElementById("obs-count");
    host.innerHTML = `<div class="skeleton skeleton-card" aria-hidden="true"></div><div class="skeleton skeleton-card" aria-hidden="true"></div>`;
    count.textContent = "Loading observations…";
    const params = new URLSearchParams({
      page: String(state.page),
      page_size: String(PAGE_SIZE),
    });
    if (state.scope === "mine") params.set("mine", "true");
    if (state.category) params.set("category", state.category);
    if (state.status) params.set("status", state.status);
    if (state.district) params.set("district", state.district);
    try {
      const data = await BT.api(`/api/biodiversity/observations?${params.toString()}`);
      count.textContent = `${BT.num(data.total)} record${data.total === 1 ? "" : "s"}`;
      if (!data.items.length) {
        host.innerHTML = BT.emptyState(
          state.scope === "mine" ? "No observations from this browser yet" : "No consented observations yet",
          state.scope === "mine"
            ? "Run an identification and save it with consent. Saved records appear here and stay pending until reviewed."
            : "Once visitors consent to share observations, they will appear here. Nothing is displayed without consent.",
          "notebook-pen",
          `<a class="btn btn-primary" href="/biodiversity.html">${BT.icon("camera")}Identify a plant or bird</a>`
        );
      } else {
        host.innerHTML = data.items.map((item) => BT.observationCard(item)).join("");
      }
      renderPagination(data.total);
      BT.refreshIcons();
    } catch (err) {
      host.innerHTML = BT.emptyState("Observations could not load", err.message, "cloud-off", `<button class="btn btn-secondary" id="obs-retry" type="button">Try again</button>`);
      const retry = document.getElementById("obs-retry");
      if (retry) retry.addEventListener("click", load);
      count.textContent = "Could not load observations";
      BT.errorToast(err);
      BT.refreshIcons();
    }
  }

  function setupEvents() {
    BT.qsa("#scope-switch button").forEach((button) => {
      button.addEventListener("click", () => {
        state.scope = button.dataset.scope;
        state.page = 1;
        BT.qsa("#scope-switch button").forEach((item) => {
          const active = item === button;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        scopeNote();
        load();
      });
    });
    document.getElementById("obs-category").addEventListener("change", (event) => {
      state.category = event.target.value;
      state.page = 1;
      load();
    });
    document.getElementById("obs-status").addEventListener("change", (event) => {
      state.status = event.target.value;
      state.page = 1;
      load();
    });
    document.getElementById("obs-district").addEventListener("change", (event) => {
      state.district = event.target.value;
      state.page = 1;
      load();
    });
    document.getElementById("obs-reset").addEventListener("click", () => {
      state.category = "";
      state.status = "";
      state.district = "";
      state.page = 1;
      document.getElementById("obs-category").value = "";
      document.getElementById("obs-status").value = "";
      document.getElementById("obs-district").value = "";
      load();
    });
    window.addEventListener("biotrace:observation-deleted", load);
  }

  async function init() {
    try {
      const taxonomy = await BT.loadTaxonomy();
      const select = document.getElementById("obs-district");
      (taxonomy.districts || []).forEach((district) => {
        const option = document.createElement("option");
        option.value = district;
        option.textContent = district;
        select.appendChild(option);
      });
    } catch (err) {
      BT.errorToast(err);
    }
    setupEvents();
    scopeNote();
    BT.bindObservationCards(document.getElementById("obs-list"));
    await load();

    const openId = new URLSearchParams(location.search).get("open");
    if (openId && /^\d+$/.test(openId)) {
      BT.openObservation(Number(openId));
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
