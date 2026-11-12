
/* Static PE evidence viewer for Sentinel.
 * Uses only the stored API stage report.
 * No HTML injection, file execution, network calls, or synthetic fallbacks.
 */
"use strict";

window.StaticEvidence = (() => {
  const $ = id => document.getElementById(id);

  const isObject = value =>
    value !== null && typeof value === "object" && !Array.isArray(value);

  const isCount = value =>
    Number.isSafeInteger(value) && value >= 0;

  const present = value =>
    value !== null && value !== undefined && value !== "";

  const asText = value =>
    !present(value)
      ? "Unavailable"
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);

  const num = value =>
    isCount(value) ? value.toLocaleString() : "Unavailable";

  const listCount = value =>
    Array.isArray(value) ? value.length : null;

  const bytes = value => {
    if (!isCount(value)) return "Unavailable";
    if (value < 1024) return `${value.toLocaleString()} bytes`;

    const unit = value < 1048576 ? "KiB" : "MiB";
    const scaled = value < 1048576
      ? value / 1024
      : value / 1048576;

    return `${scaled.toLocaleString(undefined, {
      maximumFractionDigits: 2
    })} ${unit} (${value.toLocaleString()} bytes)`;
  };

  const node = (tag, value, className) => {
    const element = document.createElement(tag);
    if (value !== undefined) element.textContent = asText(value);
    if (className) element.className = className;
    return element;
  };

  const appendNote = (container, message, warning = false) => {
    const item = node(
      "p",
      message,
      `static-pe-notice${warning ? " warning" : ""}`
    );
    container.append(item);
    return item;
  };

  const objectValue = (value, key) =>
    isObject(value) ? value[key] : undefined;

  let currentSample = null;

  function findStage(sample) {
    const rows = Array.isArray(sample.results) ? sample.results : [];
    return rows.filter(result =>
      result && result.stage === "static_analysis"
    ).at(-1) || null;
  }

  function status(state, label) {
    const badge = $("static-pe-status");
    badge.className = "badge";
    badge.dataset.state = state;
    badge.textContent = label;
  }

  function field(label, value, options = {}) {
    const box = node("div", undefined, "static-pe-field");

    if (options.warning)
      box.dataset.emphasis = "warning";

    box.append(
      node("span", label, "static-pe-label"),
      node(
        "span",
        asText(value),
        `static-pe-value${options.mono ? " mono" : ""}`
      )
    );

    return box;
  }

  function metaField(group, label, value) {
    const row = node("div");
    const dt = node("dt", label);
    const dd = node("dd", value);
    row.append(dt, dd);
    group.append(row);
  }

  function detailsFactory(container, openKeys) {
    return (key, title, renderContents) => {
      const details = node("details");
      details.dataset.peKey = key;
      details.append(node("summary", title));

      const content = node("div", undefined, "static-pe-content");
      details.append(content);

      let loaded = false;

      details.addEventListener("toggle", () => {
        if (!details.open || loaded) return;
        loaded = true;
        renderContents(content);
      });

      container.append(details);

      if (openKeys.has(key))
        details.open = true;

      return details;
    };
  }

  // Build tables only when expanded, with limited DOM batches.
  function table(container, headers, rows, valueAt, emptyMessage, pageSize = 75) {
    if (!Array.isArray(rows)) {
      container.append(node("p", "No table data was returned.", "muted"));
      return;
    }

    if (rows.length === 0) {
      container.append(node("p", emptyMessage, "muted"));
      return;
    }

    const wrapper = node("div", undefined, "static-pe-table-scroll");
    wrapper.tabIndex = 0;
    wrapper.setAttribute("aria-label", headers.join(", "));

    const tbl = node("table");
    const thead = node("thead");
    const heading = node("tr");
    const tbody = node("tbody");

    for (const label of headers) {
      const th = node("th", label);
      th.scope = "col";
      heading.append(th);
    }

    thead.append(heading);
    tbl.append(thead, tbody);
    wrapper.append(tbl);

    const more = node("button", undefined, "static-pe-more");
    more.type = "button";

    let shown = 0;

    function addBatch() {
      const end = Math.min(shown + pageSize, rows.length);
      const fragment = document.createDocumentFragment();

      for (; shown < end; shown++) {
        const tr = node("tr");
        const values = valueAt(rows[shown]);

        for (const value of values)
          tr.append(node("td", value));

        fragment.append(tr);
      }

      tbody.append(fragment);
      more.hidden = shown >= rows.length;
      more.textContent =
        `Show more (${shown.toLocaleString()} / ${rows.length.toLocaleString()})`;
    }

    more.addEventListener("click", addBatch);
    container.append(wrapper, more);
    addBatch();
  }

  function textList(container, items, options = {}) {
    if (!Array.isArray(items)) {
      container.append(node("p", "Not collected.", "muted"));
      return;
    }

    if (!items.length) {
      container.append(node(
        "p",
        options.empty || "No entries reported.",
        "muted"
      ));
      return;
    }

    const controls = node("div", undefined, "static-pe-controls");
    const counter = node("span", "", "muted");
    let input = null;
    let matching = items;
    let shown = 0;

    if (options.searchable) {
      input = node("input");
      input.type = "search";
      input.placeholder = "Search extracted strings";
      input.setAttribute("aria-label", "Search extracted strings");
      controls.append(input);
    }

    controls.append(counter);

    const ul = node("ul", undefined, "static-pe-list");
    const more = node("button", "Show more", "static-pe-more");
    more.type = "button";

    function addBatch() {
      const end = Math.min(shown + 100, matching.length);
      const fragment = document.createDocumentFragment();

      for (; shown < end; shown++)
        fragment.append(node("li", matching[shown]));

      ul.append(fragment);
      more.hidden = shown >= matching.length;
      more.textContent =
        `Show more (${shown.toLocaleString()} / ${matching.length.toLocaleString()})`;

      counter.textContent =
        `${matching.length.toLocaleString()} matching / ${items.length.toLocaleString()} available`;
    }

    more.addEventListener("click", addBatch);

    if (input) {
      input.addEventListener("input", () => {
        const q = input.value.toLocaleLowerCase();

        matching = q
          ? items.filter(value =>
              String(value).toLocaleLowerCase().includes(q))
          : items;

        shown = 0;
        ul.replaceChildren();
        addBatch();

        if (!matching.length)
          ul.append(node("li", "No strings match your search."));
      });
    }

    container.append(controls, ul, more);
    addBatch();
  }

  function renderOverview(sample, report) {
    const overview = $("static-pe-overview");

    const pe = isObject(report.pe) ? report.pe : {};
    const imports = isObject(report.imports) ? report.imports : {};
    const delayed = isObject(report.delay_imports)
      ? report.delay_imports : {};
    const sum = isObject(report.summary) ? report.summary : {};
    const reputation = isObject(report.hash_reputation)
      ? report.hash_reputation : null;
    const yara = isObject(report.yara) ? report.yara : null;

    const sectionCount = listCount(report.sections);
    const warningCount = listCount(report.parser_warnings);

    const yaraStatus = !yara
      ? "Not collected"
      : yara.status === "completed"
        ? `${num(listCount(yara.matches))} match(es) · scan completed`
        : `Unavailable (${asText(yara.status)})`;

    const reputationStatus = !reputation
      ? "Not collected"
      : reputation.status === "match"
        ? "Known hash match"
        : reputation.status === "no_match"
          ? "No match in local snapshot"
          : "Unavailable";

    overview.replaceChildren(
      field("Analyzed file",
        report.filename || sample.original_filename || "Unavailable"),

      field("File size", bytes(report.file_size)),
      field("PE format", pe.format),
      field("Architecture", pe.architecture),
      field("COFF machine", pe.machine, { mono: true }),

      field("File type",
        typeof pe.is_dll === "boolean"
          ? pe.is_dll ? "DLL" : "EXE / non-DLL PE"
          : "Unavailable"),

      field("PE header timestamp · unverified",
        pe.compile_timestamp || "Unavailable"),

      field("Entry point (RVA)", pe.entry_point, { mono: true }),
      field("Image base", pe.image_base, { mono: true }),

      field("Sections",
        sectionCount ?? (isCount(sum.section_count)
          ? sum.section_count : "Unavailable")),

      field("Imported DLLs",
        isCount(sum.imported_dll_count)
          ? sum.imported_dll_count
          : listCount(imports.dlls) ?? "Unavailable"),

      field("Imported APIs",
        isCount(sum.imported_api_count)
          ? sum.imported_api_count
          : listCount(imports.apis) ?? "Unavailable"),

      field("Delay-load DLLs / APIs",
        `${num(listCount(delayed.dlls))} / ${num(listCount(delayed.apis))}`),

      field("Extracted strings",
        isCount(objectValue(report.strings, "count"))
          ? report.strings.count
          : listCount(objectValue(report.strings, "sample")) ?? "Unavailable"),

      field("Parser warnings",
        warningCount ?? "Unavailable",
        { warning: warningCount > 0 }),

      field("Offline hash reputation",
        reputationStatus,
        { warning: Boolean(reputation && reputation.status === "unavailable") }),

      field("YARA",
        yaraStatus,
        { warning: Boolean(yara && yara.status !== "completed") })
    );

    overview.hidden = false;

    $("static-pe-message").textContent =
      `Stored static analyzer evidence · schema ${asText(report.schema_version)}. ` +
      "These observations alone do not establish whether a file is safe or malicious.";

    const sampleHash =
      typeof sample.sha256 === "string" ? sample.sha256.toLowerCase() : null;
    const analyzerHash =
      typeof report.sha256 === "string" ? report.sha256.toLowerCase() : null;

    if (sampleHash && analyzerHash && sampleHash !== analyzerHash) {
      const warning = appendNote(
        overview,
        "Warning: static analyzer SHA-256 differs from the uploaded sample's SHA-256. Verify the scan record before relying on this report.",
        true
      );
      warning.style.gridColumn = "1 / -1";
    }
  }

  function renderSections(add, report) {
    add(
      "sections",
      `PE sections (${num(listCount(report.sections))})`,
      content => {
        appendNote(
          content,
          "Sizes and R/W/X flags come from PE headers; entropy is an observation, not a malware verdict."
        );

        table(
          content,
          ["Section", "Virtual size", "Raw size", "Entropy (0–8)", "Permissions", "Characteristics"],
          report.sections,
          row => [
            row.name,
            bytes(row.virtual_size),
            bytes(row.raw_size),
            typeof row.entropy === "number"
              ? row.entropy.toFixed(4) : "Unavailable",
            [
              row.readable ? "R" : "-",
              row.writable ? "W" : "-",
              row.executable ? "X" : "-"
            ].join(""),
            row.characteristics
          ],
          "No PE sections reported."
        );
      }
    );
  }

  function renderImports(add, report) {
    add("imports", "Ordinary imports and delay-loaded imports", content => {
      appendNote(
        content,
        "Imports indicate declared dependencies, not proof that an API executed."
      );

      const ordinary = isObject(report.imports) ? report.imports : null;
      const delayed = isObject(report.delay_imports)
        ? report.delay_imports : null;

      for (const [name, source] of [
        ["Ordinary DLLs", ordinary && ordinary.dlls],
        ["Ordinary APIs", ordinary && ordinary.apis],
        ["Delay-loaded DLLs", delayed && delayed.dlls],
        ["Delay-loaded APIs", delayed && delayed.apis]
      ]) {
        content.append(
          node(
            "h4",
            `${name} · ${num(listCount(source))}`,
            "static-pe-subtitle"
          )
        );
        textList(content, source);
      }
    });
  }

  function renderStrings(add, report) {
    const strings = isObject(report.strings) ? report.strings : null;
    const listed = strings && Array.isArray(strings.sample)
      ? strings.sample : null;

    add(
      "strings",
      `Extracted strings (${num(strings && strings.count)})`,
      content => {
        appendNote(
          content,
          "Searchable extraction of ASCII and printable UTF-16LE strings. All strings delivered in the stored report remain available; the page displays them in batches."
        );

        if (strings && strings.truncated === true) {
          appendNote(
            content,
            `This stored report declares omitted strings: ${num(listCount(listed))} shown of ${num(strings.count)} total. The frontend cannot recover omitted source data.`,
            true
          );
        } else if (
          strings &&
          isCount(strings.count) &&
          listed &&
          strings.count !== listed.length
        ) {
          appendNote(
            content,
            `The report declares ${num(strings.count)} strings but contains ${num(listed.length)} entries. Verify the analyzer output.`,
            true
          );
        }

        textList(content, listed, {
          searchable: true,
          empty: "No extracted strings were reported."
        });
      }
    );
  }

  function renderResources(add, report) {
    const entries = isObject(report.resources) &&
      Array.isArray(report.resources.entries)
        ? report.resources.entries
        : null;

    add(
      "resources",
      `PE resources (${num(listCount(entries))})`,
      content => {
        appendNote(
          content,
          "Resource hashes apply only when capture status is complete. A truncated/unavailable resource is not a clean result."
        );

        table(
          content,
          [
            "Path", "RVA", "Size", "Code page",
            "File offset", "Captured", "Status", "SHA-256 / Error"
          ],
          entries,
          r => [
            Array.isArray(r.path) ? r.path.join(" / ") : "Unavailable",
            r.rva,
            bytes(r.size),
            r.code_page,
            r.file_offset,
            bytes(r.captured_size),
            r.status,
            r.status === "complete" ? r.sha256 : r.error
          ],
          "No PE resources were reported.",
          50
        );
      }
    );
  }

  function renderWarnings(add, report) {
    const warnings = Array.isArray(report.parser_warnings)
      ? report.parser_warnings : null;

    add(
      "warnings",
      `Parser warnings (${num(listCount(warnings))})`,
      content => {
        appendNote(
          content,
          "These are nonfatal parser diagnostics, not malware detections. Treat parsing completeness accordingly."
        );

        textList(content, warnings, {
          empty: "No parser warnings were reported."
        });
      }
    );
  }

  function renderReputation(add, report) {
    add("reputation", "Offline SHA-256 reputation", content => {
      const rep = report.hash_reputation;

      if (!isObject(rep)) {
        appendNote(
          content,
          "Reputation evidence was not collected. No safety inference is possible.",
          true
        );
        return;
      }

      if (rep.status === "unavailable") {
        appendNote(
          content,
          "Offline reputation database unavailable. This is NOT a no-match result.",
          true
        );
      } else if (rep.status === "no_match") {
        appendNote(
          content,
          "No match in the available local hash snapshot. This does not establish that the file is safe."
        );
      } else if (rep.status === "match") {
        appendNote(
          content,
          "The SHA-256 matches an entry in the locally configured reputation snapshot. Review source and coverage.",
          true
        );
      }

      const group = node("dl", undefined, "static-pe-meta");

      for (const [label, value] of [
        ["Status", rep.status],
        ["Matched", rep.matched],
        ["Source", rep.source],
        ["Coverage", rep.coverage],
        ["Snapshot updated", rep.updated_at],
        ["Hash count", isCount(rep.hash_count) ? num(rep.hash_count) : null],
        ["Error", rep.error]
      ]) {
        metaField(group, label, value);
      }

      content.append(group);
    });
  }

  function renderYara(add, report) {
    const result = report.yara;
    const matches = isObject(result) && Array.isArray(result.matches)
      ? result.matches : null;

    add(
      "yara",
      `YARA rules (${num(listCount(matches))} matches reported)`,
      content => {
        if (!isObject(result)) {
          appendNote(
            content,
            "YARA evidence was not collected. No safety inference is possible.",
            true
          );
          return;
        }

        if (result.status === "completed") {
          appendNote(
            content,
            "YARA scan completed. A lack of matches only means this configured ruleset did not match; it does not prove safety."
          );
        } else {
          appendNote(
            content,
            `YARA did not complete successfully (${asText(result.status)}). Do not treat this as zero findings.`,
            true
          );
        }

        const group = node("dl", undefined, "static-pe-meta");

        for (const [label, value] of [
          ["Status", result.status],
          ["Engine version", result.engine_version],
          ["Rules file", result.rules_file],
          ["Rules SHA-256", result.rules_sha256],
          ["Error", result.error === null ? "None" : result.error]
        ]) {
          metaField(group, label, value);
        }

        content.append(group);
        content.append(
          node("h4", "Rule matches", "static-pe-subtitle")
        );

        table(
          content,
          ["Rule", "Namespace", "Tags", "Metadata"],
          matches,
          match => [
            match.rule,
            match.namespace,
            Array.isArray(match.tags)
              ? match.tags.join(", ") : "Unavailable",
            match.meta
          ],
          result.status === "completed"
            ? "No rules matched this file."
            : "No reliable match list: scan did not complete."
        );

        content.append(
          node("h4", "YARA warnings", "static-pe-subtitle")
        );

        textList(
          content,
          Array.isArray(result.warnings) ? result.warnings : null,
          { empty: "No YARA warnings were reported." }
        );
      }
    );
  }

  function render(sample) {
    const sampleId = String(sample.sample_id ?? "");
    const detailRoot = $("static-pe-details");
    const overview = $("static-pe-overview");

    const preserved = currentSample === sampleId
      ? new Set(
          Array.from(detailRoot.querySelectorAll("details[open]"))
            .map(d => d.dataset.peKey)
        )
      : new Set();

    currentSample = sampleId;

    detailRoot.replaceChildren();
    overview.replaceChildren();
    overview.hidden = true;
    detailRoot.hidden = true;

    const copy = $("copy-fingerprint");
    const hash = sample.sha256;

    copy.disabled =
      typeof hash !== "string" || !/^[a-f\d]{64}$/i.test(hash);

    $("fingerprint-feedback").textContent = "";

    if (sample.submission_type !== "file") {
      status("not_run", "Not applicable");
      $("static-pe-message").textContent =
        "Static PE analysis applies to uploaded Windows executable files, not URL submissions.";
      return;
    }

    const result = findStage(sample);

    if (!result) {
      status(
        sample.status === "running" || sample.status === "queued"
          ? "pending" : "not_run",
        "Not run"
      );
      $("static-pe-message").textContent =
        "This scan has no stored static-analysis result yet.";
      return;
    }

    if (result.status === "failed") {
      status("failed", "Failed");
      $("static-pe-message").textContent =
        `Static analyzer failed: ${asText(
          objectValue(result.error, "message") ||
          result.error ||
          "No error details returned"
        )}`;
      return;
    }

    if (result.status !== "complete") {
      status(
        result.status === "running" ? "running" : "pending",
        result.status === "running" ? "Running" : "Pending"
      );
      $("static-pe-message").textContent =
        "Static analysis has not completed.";
      return;
    }

    if (!isObject(result.report)) {
      status("failed", "No report");
      $("static-pe-message").textContent =
        "The stage completed without a usable stored JSON report.";
      return;
    }

    const report = result.report;

    if (!isObject(report.pe) || !Array.isArray(report.sections)) {
      status("complete", "Limited report");
      $("static-pe-message").textContent =
        "A static-analysis report exists, but it does not contain the full PE evidence contract (possibly a mock or legacy report). Rescan using the real analyzer to populate File Intelligence.";
      return;
    }

    status("complete", "Evidence collected");
    renderOverview(sample, report);

    const add = detailsFactory(detailRoot, preserved);

    renderSections(add, report);
    renderImports(add, report);
    renderStrings(add, report);
    renderResources(add, report);
    renderWarnings(add, report);
    renderReputation(add, report);
    renderYara(add, report);

    detailRoot.hidden = false;
  }

  $("copy-fingerprint").addEventListener("click", async () => {
    const hash = $("sample-hash").textContent.trim();

    if (!/^[a-f\d]{64}$/i.test(hash)) return;

    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText)
        throw new Error("Clipboard API unavailable");

      await navigator.clipboard.writeText(hash);
      $("fingerprint-feedback").textContent = "Copied.";
    } catch (_) {
      $("fingerprint-feedback").textContent =
        "Clipboard unavailable; select the fingerprint to copy manually.";
    }
  });

  return { render };
})();
