
/* global ReportsData, scans, renderAccount, errorMessage, StaticEvidence */
"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const text = (id, value) => { $(id).textContent = value; };
  const element = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  };

  const labels = {
    queued: "Queued",
    running: "Running",
    completed: "Completed",
    complete: "Complete",
    failed: "Failed",
    pending: "Pending",
    not_run: "Not run"
  };

  const badge = (node, status, label) => {
    node.className = "badge";
    node.dataset.state = status;
    node.textContent = label || labels[status] || "Unknown";
  };

  const date = value => {
    const parsed = value ? new Date(value) : null;
    return parsed && !Number.isNaN(parsed.getTime())
      ? parsed.toLocaleString()
      : "Date unavailable";
  };

  const percent = value => Number((value * 100).toFixed(1));
  const PAGE_SIZE = 20;
  let page = 1, selected = null, historyRows = [], total = 0;
  let historyRequest = 0, detailRequest = 0;
  let timer = null, lastSample = null, paused = false;

  const { revealInChunks, finishReveal, finishAllReveals } = window.RetroLoading;

  function syncUrl(replace = false) {
    const url = new URL(location.href);
    if (selected) url.searchParams.set("sample_id", selected);
    else url.searchParams.delete("sample_id");
    if (page > 1) url.searchParams.set("page", page);
    else url.searchParams.delete("page");
    history[replace ? "replaceState" : "pushState"]({}, "", url);
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    const id = params.get("sample_id");
    selected = id && /^\d{1,9}$/.test(id) ? id : null;
    const value = Number(params.get("page"));
    page = Number.isSafeInteger(value) && value > 0 && value <= 1000000 ? value : 1;
    return id !== null && selected === null;
  }

  function notice(message, retry = false) {
    text("detail-message", message);
    $("detail-message").hidden = !message;
    $("retry-detail").hidden = !retry;
  }

  function renderHistory() {
    const list = $("history-list");
    list.replaceChildren();

    for (const sample of historyRows) {
      const li = element("li");
      const button = element("button", undefined, "history-item");
      button.dataset.sampleId = String(sample.sample_id);
      button.setAttribute("aria-current", String(String(sample.sample_id) === selected));
      button.append(
        element("span", ReportsData.name(sample), "history-name"),
        element("span", date(sample.created_at), "history-date")
      );
      const status = element("span");
      badge(status, sample.status);
      button.append(status);
      button.addEventListener("click", () => select(String(sample.sample_id)));
      li.append(button);
      list.append(li);
    }

    text("page-label", `Page ${page} of ${Math.max(1, Math.ceil(total / PAGE_SIZE))}`);
    $("previous-page").disabled = page <= 1;
    $("next-page").disabled = page * PAGE_SIZE >= total;
  }

  async function loadHistory() {
    const request = ++historyRequest;
    $("retry-history").hidden = true;
    text("history-message", "Loading scans…");
    $("previous-page").disabled = $("next-page").disabled = true;

    const response = await scans.list(PAGE_SIZE, (page - 1) * PAGE_SIZE);
    if (request !== historyRequest) return;

    if (!response.ok || !response.data || !Array.isArray(response.data.samples)) {
      text("history-message", errorMessage(response, "Could not load scan history."));
      $("retry-history").hidden = false;
      return;
    }

    total = Number.isSafeInteger(response.data.total) && response.data.total >= 0
      ? response.data.total : 0;

    const maxPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (page > maxPage) {
      page = maxPage;
      syncUrl(true);
      return loadHistory();
    }

    historyRows = response.data.samples;
    renderHistory();
    text("history-message", total
      ? `${total} scan${total === 1 ? "" : "s"} · newest first`
      : "No scans yet. Start a new scan from Home.");

    if (!selected && historyRows.length)
      select(String(historyRows[0].sample_id), true);
  }

  function select(id, replace = false) {
    finishReveal("scan");
    clearTimeout(timer);
    detailRequest++;
    paused = false;
    lastSample = null;
    selected = id;
    syncUrl(replace);
    renderHistory();
    $("scan-content").hidden = true;
    notice("Loading scan…");
    loadDetail();
  }

  async function loadDetail() {
    clearTimeout(timer);
    if (!selected) return;

    const request = ++detailRequest;
    const id = selected;
    $("retry-detail").hidden = true;
    const response = await scans.get(id);

    if (request !== detailRequest || id !== selected) return;

    if (!response.ok || !response.data || String(response.data.sample_id) !== id) {
      paused = true;
      if (response.status === 404) {
        $("scan-content").hidden = true;
        notice("This scan is unavailable or belongs to another account.");
      } else {
        notice(lastSample
          ? "Updates paused. Showing the last received results. Retry to reconnect."
          : errorMessage(response, "Could not load this scan."), true);
      }
      return;
    }

    paused = false;
    const sample = response.data;
    if (JSON.stringify(lastSample) !== JSON.stringify(sample)) render(sample);
    lastSample = sample;

    const button = document.querySelector(`.history-item[data-sample-id="${id}"] .badge`);
    if (button) badge(button, sample.status);

    const row = historyRows.find(item => String(item.sample_id) === id);
    if (row) row.status = sample.status;

    notice(ReportsData.active(sample)
      ? "Scan in progress — results update every 2 seconds."
      : "");

    if (ReportsData.active(sample) && !document.hidden)
      timer = setTimeout(loadDetail, 2000);
  }

  function render(sample) {
    const vm = ReportsData.view(sample);
    $("scan-content").hidden = false;

    text("sample-label",
      `SCAN ${sample.sample_id} · ${sample.submission_type === "link" ? "LINK" : "FILE"}`);
    text("sample-name", vm.name);
    text("sample-date", `Submitted ${date(sample.created_at)}`);
    text("sample-hash", sample.sha256 || "Unavailable");
    badge($("job-status"), sample.status);

    // NEW: render the complete stored static PE evidence.
    StaticEvidence.render(sample);

    $("signature-alert").hidden = vm.signatureMatch !== true;
    text("signature-alert",
      `Known signature matched${vm.signatureName ? ": " + vm.signatureName : ""}. Review this finding separately from the behavioral score.`);
    $("synthetic-notice").hidden = !vm.synthetic;

    $("stage-list").replaceChildren(...vm.stages.map(stage => {
      const li = element("li");
      li.append(element("span", stage.label, "stage-name"));
      const status = element("span");
      badge(status, stage.status);
      li.append(status);
      if (stage.error) li.append(element("p", stage.error, "stage-error"));
      return li;
    }));

    const score = vm.risk === null ? null : percent(vm.risk);
    text("risk-value", score === null ? "—" : score);
    text("risk-scale", score === null ? "Unavailable" : "out of 100");

    $("risk-gauge").setAttribute(
      "aria-label",
      score === null ? "Risk score unavailable"
        : `Behavioral risk score: ${score} out of 100. ${vm.level}.`
    );
    $("gauge-fill").setAttribute("stroke-dasharray", `${score ?? 0} 100`);
    $("gauge-fill").dataset.level = vm.level;

    badge($("risk-level"), vm.level,
      vm.level === "Unavailable"
        ? vm.level
        : vm.level.charAt(0).toUpperCase() + vm.level.slice(1));

    text("risk-source", score === null
      ? "No usable behavioral verdict"
      : `Source: ${vm.source}`);

    text("risk-threshold", vm.threshold === null
      ? "Decision threshold unavailable"
      : `Decision threshold: ${percent(vm.threshold)} / 100`);

    text("activity-message", vm.telemetry.message);
    const max = Math.max(1, ...vm.telemetry.counts.map(c => c.value ?? 0));

    $("activity-bars").replaceChildren(...vm.telemetry.counts.map(item => {
      const row = element("div", undefined, "bar-row");
      const label = element("div", undefined, "bar-label");

      label.append(
        element("span", item.label),
        element("strong", item.value === null ? "Unavailable" : item.value.toLocaleString())
      );

      const track = element("div", undefined, "bar-track");
      const fill = element("div", undefined, "bar-fill");
      fill.style.width = `${(item.value ?? 0) / max * 100}%`;
      track.append(fill);
      row.append(label, track);
      return row;
    }));

    $("activity-counts").replaceChildren(...vm.telemetry.counts.map(item => {
      const row = element("tr");
      const heading = element("th", item.label);
      heading.scope = "row";
      row.append(heading, element("td",
        item.value === null ? "Unavailable" : item.value));
      return row;
    }));

    text("anomaly-result", vm.anomaly === "anomaly"
      ? "Unusual behavior detected"
      : vm.anomaly === "known"
        ? "Within learned baseline"
        : "Unavailable");

    text("anomaly-score", vm.anomalyScore === null
      ? "Raw anomaly score unavailable"
      : `Raw anomaly score: ${vm.anomalyScore}`);

    text("signature-result", vm.signatureMatch === true
      ? `Signature match${vm.signatureName ? ": " + vm.signatureName : ""}.`
      : vm.signatureMatch === false
        ? "No known signature matched. This alone does not establish safety."
        : "Signature result unavailable.");

    $("ml-evidence").replaceChildren(
      ...(vm.evidence.length ? vm.evidence : ["No behavioral evidence was returned."])
        .map(value => element("li", value))
    );

    renderEvents(vm.telemetry.counts);

    if (!lastSample || lastSample.sample_id !== sample.sample_id)
      revealInChunks("scan", [...$("scan-content").children]);
  }

  const columns = {
    processes: [
      ["Image", "image"],
      ["Command line", "command_line", "commandline", "cmdline", "command"],
      ["Parent", "parent"],
      ["PID", "pid"]
    ],
    network: [
      ["Image", "image"],
      ["Destination", "dest_ip"],
      ["Port", "dest_port"],
      ["Protocol", "protocol"]
    ],
    dns: [
      ["Query", "query_name", "query"],
      ["Results", "results"]
    ],
    file_drops: [
      ["File", "target_filename"],
      ["Image", "image"]
    ],
    registry: [
      ["Registry path", "target_object", "path", "key_path", "key"],
      ["Details", "details"],
      ["Event", "event_type"]
    ]
  };

  function renderEvents(counts) {
    const open = new Set(
      Array.from($("event-tables").querySelectorAll("details[open]"))
        .map(node => node.dataset.key)
    );

    $("event-tables").replaceChildren(...counts.map(item => {
      const details = element("details", undefined, "event-details");
      details.dataset.key = item.key;
      details.open = open.has(item.key);
      details.append(element("summary",
        `${item.label} · ${item.events ? item.events.length + " returned events" : "Unavailable"}`));

      if (!item.events || !item.events.length) {
        details.append(element("p",
          !item.events
            ? "No usable event data was returned."
            : item.value > 0
              ? "The summary reports activity, but event details were omitted."
              : "No events of this type were returned.",
          "muted"));
        return details;
      }

      const wrapper = element("div", undefined, "table-scroll");
      wrapper.tabIndex = 0;
      wrapper.setAttribute("aria-label", item.label + " events");

      const table = element("table");
      const header = element("tr");
      table.append(element("caption",
        `${item.label}: returned events (may be a subset of the total)`, "sr-only"));

      for (const [label] of columns[item.key]) {
        const th = element("th", label);
        th.scope = "col";
        header.append(th);
      }

      const head = element("thead");
      head.append(header);
      table.append(head);

      const body = element("tbody");
      let shown = 0;
      const more = element("button", "Show more events");

      const addRows = () => {
        const end = Math.min(shown + 100, item.events.length);
        for (; shown < end; shown++) {
          const event = item.events[shown];
          const row = element("tr");

          for (const [, ...keys] of columns[item.key]) {
            const key = keys.find(key =>
              event[key] !== null && event[key] !== undefined);
            const value = key ? event[key] : "Unavailable";
            row.append(element("td",
              typeof value === "object" ? JSON.stringify(value) : String(value)));
          }
          body.append(row);
        }

        more.hidden = shown >= item.events.length;
        more.textContent = `Show more events (${shown} of ${item.events.length} shown)`;
      };

      more.addEventListener("click", addRows);
      addRows();
      table.append(body);
      wrapper.append(table);
      details.append(wrapper, more);
      return details;
    }));
  }

  function navigatePage(delta) {
    page += delta;
    syncUrl();
    loadHistory();
  }

  $("previous-page").addEventListener("click", () => navigatePage(-1));
  $("next-page").addEventListener("click", () => navigatePage(1));
  $("refresh-history").addEventListener("click", loadHistory);
  $("retry-history").addEventListener("click", loadHistory);
  $("retry-detail").addEventListener("click", () => {
    notice("Reconnecting…");
    loadDetail();
  });

  window.addEventListener("popstate", () => {
    finishReveal("scan");
    clearTimeout(timer);
    detailRequest++;
    lastSample = null;
    paused = false;
    initialize();
  });

  window.addEventListener("pagehide", () => {
    finishAllReveals();
    clearTimeout(timer);
    detailRequest++;
    historyRequest++;
  });

  window.addEventListener("pageshow", event => {
    if (event.persisted) {
      lastSample = null;
      paused = false;
      initialize();
    }
  });

  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer);
    if (document.hidden) finishAllReveals();
    if (!document.hidden && !paused && lastSample &&
        ReportsData.active(lastSample)) loadDetail();
  });

  function initialize() {
    const invalid = readUrl();
    $("scan-content").hidden = true;
    notice(invalid ? "Invalid scan ID. Select a scan from history."
      : selected ? "Loading scan…"
      : "Select a scan to see its results.");
    if (selected) loadDetail();
    loadHistory();
  }

  renderAccount("account", "../index.html");
  revealInChunks("page", [
    ...document.querySelectorAll(".sidebar, .page-heading, .welcome-strip, .history, .retro-footer")
  ]);
  initialize();
})();
