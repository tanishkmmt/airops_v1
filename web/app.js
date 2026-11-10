const state = {
  stage: "contract", contractSource: null, contractTemplate: null,
  blockSource: null, blockTemplate: null, aisContracts: [],
  contractRows: [], blockRows: [], lastContract: null, lastBlocks: null,
  profiles: [], activeProfile: null, contractProfile: null, selectedProfile: null, selectedProfileVersion: null, profileFields: [], contractTemplateSource: "demo", contractPrepared: false, configView: "tnc",
  blockProfiles: [], blockProfileFields: [], blockFieldMetadata: [], blockSchemaFields: [], blockSchemaMetadata: [], selectedBlockProfile: null,
  demoContractTemplate: null, demoBlockTemplate: null, profileSaveAttempted: false,
};

const $ = (id) => document.getElementById(id);
const norm = (value) => String(value ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const val = (row, header) => row?.[header] ?? "";
let selectControlId = 0;

function setFileSelectionVisual(input, hasFile = Boolean(input?.files?.length)) {
  input?.closest(".file-drop, .compact-file")?.classList.toggle("has-file", hasFile);
}

document.addEventListener("change", (event) => {
  if (event.target instanceof HTMLInputElement && event.target.type === "file") setFileSelectionVisual(event.target);
}, true);

function syncEnhancedSelect(select) { select?._syncCustomSelect?.(); }

function enhanceSelect(select) {
  if (select.dataset.customSelect === "true") return;
  select.dataset.customSelect = "true";
  const wrapper = document.createElement("div"); wrapper.className = "select-control";
  select.parentNode.insertBefore(wrapper, select); wrapper.append(select);
  const trigger = document.createElement("button");
  trigger.type = "button"; trigger.className = "select-trigger"; trigger.setAttribute("role", "combobox");
  trigger.setAttribute("aria-haspopup", "listbox"); trigger.setAttribute("aria-expanded", "false");
  const label = select.labels?.[0]?.textContent?.trim() || select.closest("label")?.querySelector("span")?.textContent?.trim();
  if (label) trigger.setAttribute("aria-label", label);
  const valueText = document.createElement("span"); valueText.className = "select-trigger-value";
  const chevron = document.createElement("span"); chevron.className = "select-trigger-chevron"; chevron.setAttribute("aria-hidden", "true");
  trigger.append(valueText, chevron); wrapper.insertBefore(trigger, select);
  const menu = document.createElement("div"); menu.className = "select-menu"; menu.setAttribute("role", "listbox");
  menu.hidden = true; menu.id = `select-menu-${++selectControlId}`; trigger.setAttribute("aria-controls", menu.id); wrapper.append(menu);
  select.tabIndex = -1; select.setAttribute("aria-hidden", "true");

  const close = (restoreFocus = false) => {
    wrapper.classList.remove("is-open", "opens-up"); menu.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) trigger.focus();
  };
  const sync = () => {
    const current = select.options[select.selectedIndex];
    valueText.textContent = current?.textContent?.trim() || "Choose an option";
    trigger.disabled = select.disabled;
    trigger.setAttribute("aria-invalid", String(select.getAttribute("aria-invalid") === "true"));
    trigger.setAttribute("aria-required", String(select.required));
    menu.replaceChildren();
    [...select.options].forEach((option, index) => {
      const item = document.createElement("button"); item.type = "button"; item.className = "select-option";
      item.setAttribute("role", "option"); item.setAttribute("aria-selected", String(index === select.selectedIndex));
      item.disabled = option.disabled; item.textContent = option.textContent.trim();
      item.addEventListener("click", () => {
        if (option.disabled) return;
        select.value = option.value;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
        sync(); close(true);
      });
      menu.append(item);
    });
  };
  select._syncCustomSelect = sync;
  select.addEventListener("change", sync);
  select.addEventListener("input", sync);
  const optionsObserver = new MutationObserver(sync);
  optionsObserver.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "label", "selected"] });

  const open = () => {
    if (trigger.disabled) return;
    document.querySelectorAll(".select-control.is-open").forEach((other) => {
      if (other !== wrapper) { other.classList.remove("is-open", "opens-up"); other.querySelector(".select-menu").hidden = true; other.querySelector(".select-trigger").setAttribute("aria-expanded", "false"); }
    });
    sync(); menu.hidden = false; wrapper.classList.add("is-open"); trigger.setAttribute("aria-expanded", "true");
    const rect = trigger.getBoundingClientRect();
    if (window.innerHeight - rect.bottom < Math.min(240, menu.scrollHeight) && rect.top > 240) wrapper.classList.add("opens-up");
    const items = [...menu.querySelectorAll('.select-option:not(:disabled)')];
    (items.find((item) => item.getAttribute("aria-selected") === "true") || items[0])?.focus();
  };
  trigger.addEventListener("click", () => menu.hidden ? open() : close());
  trigger.addEventListener("keydown", (event) => {
    if (["ArrowDown", "ArrowUp", "Enter"].includes(event.key)) { event.preventDefault(); open(); }
  });
  menu.addEventListener("keydown", (event) => {
    const items = [...menu.querySelectorAll('.select-option:not(:disabled)')];
    const current = items.indexOf(document.activeElement);
    if (event.key === "Escape") { event.preventDefault(); close(true); }
    else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault(); const delta = event.key === "ArrowDown" ? 1 : -1;
      items[(current + delta + items.length) % items.length]?.focus();
    } else if (event.key === "Home") { event.preventDefault(); items[0]?.focus(); }
    else if (event.key === "End") { event.preventDefault(); items.at(-1)?.focus(); }
  });
  wrapper.addEventListener("focusout", () => setTimeout(() => {
    if (!wrapper.contains(document.activeElement)) close();
  }, 0));
  sync();
}

document.querySelectorAll("select").forEach(enhanceSelect);
const selectInsertObserver = new MutationObserver((records) => records.forEach((record) => record.addedNodes.forEach((node) => {
  if (node.nodeType !== Node.ELEMENT_NODE) return;
  if (node.matches?.("select")) enhanceSelect(node);
  node.querySelectorAll?.("select").forEach(enhanceSelect);
})));
selectInsertObserver.observe(document.body, { childList: true, subtree: true });
document.addEventListener("pointerdown", (event) => {
  if (event.target.closest?.(".select-control")) return;
  document.querySelectorAll(".select-control.is-open").forEach((wrapper) => {
    wrapper.classList.remove("is-open", "opens-up"); wrapper.querySelector(".select-menu").hidden = true;
    wrapper.querySelector(".select-trigger").setAttribute("aria-expanded", "false");
  });
});
const notice = (message, error = false) => {
  const toast = $("toast"); toast.textContent = message; toast.classList.add("is-visible");
  toast.style.background = error ? "#7d292c" : "#192326";
  window.clearTimeout(notice.timer); notice.timer = window.setTimeout(() => toast.classList.remove("is-visible"), 3200);
};

async function request(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("AirOps could not reach its local service. It may still be starting or may have stopped. Refresh the page and retry; if this continues, restart AirOps on port 8080.");
    }
    throw error;
  }
  let data;
  try { data = await response.json(); } catch { throw new Error("The service returned an unreadable response."); }
  if (!response.ok) {
    const detail = data?.detail;
    const messages = Array.isArray(detail)
      ? detail.map((item) => {
        if (typeof item === "string") return item;
        const location = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== "body").join(" → ") : "";
        return [location, item?.msg || item?.message].filter(Boolean).join(": ");
      }).filter(Boolean)
      : typeof detail === "string" ? detail
        : detail && typeof detail === "object" ? (detail.message || detail.msg || JSON.stringify(detail)) : "";
    throw new Error(messages || `Request failed (${response.status}).`);
  }
  return data;
            }

function parseCsv(text, filename) {
  const delimiter = filename.toLowerCase().endsWith(".tsv") ? "\t" : (text.slice(0, 4000).split(";").length > text.slice(0, 4000).split(",").length ? ";" : ",");
  const rows = []; let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === delimiter) { row.push(field); field = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.some((cell) => cell.trim())) rows.push(row);
      row = [];
    } else field += ch;
  }
  row.push(field); if (row.some((cell) => cell.trim())) rows.push(row);
  if (!rows.length) throw new Error("This CSV is empty.");
  const headers = rows[0].map((h) => h.replace(/^\uFEFF/, "").trim());
  return { headers, rows: rows.slice(1).map((cells) => headers.map((_, i) => cells[i] ?? "")), filename };
}

async function readCsv(file) {
  if (!file) throw new Error("Choose a CSV file first.");
  if (file.size > 20 * 1024 * 1024) throw new Error("CSV file exceeds the 20 MB prototype limit.");
  return parseCsv(await file.text(), file.name);
}

async function readStructuredFile(file, purpose) {
  if (!file) throw new Error("Choose a file first.");
  if (/\.(csv|tsv)$/i.test(file.name)) return readCsv(file);
  if (!/\.(xlsx|xlsb)$/i.test(file.name)) throw new Error("Supported formats are CSV, TSV, XLSX, and XLSB.");
  if (file.size > 20 * 1024 * 1024) throw new Error("File exceeds the 20 MB prototype limit.");
  const body = new FormData(); body.append("file", file);
  const parsed = await request("/api/source/inspect", { method: "POST", body });
  const normalizedHeaders = (table) => table.headers.map(norm);
  const matches = (table) => {
    const headers = normalizedHeaders(table);
    if (purpose === "contract-template") return headers.includes("contractname") && headers.includes("journey1from") && !headers.includes("contractid");
    if (purpose === "block-template") return headers.includes("contractid") && headers.includes("airlinepnr") && headers.some((header) => header.startsWith("itineraries1")) && !headers.includes("blockid");
    if (purpose === "contract-result") return headers.includes("contractid") || headers.includes("id");
    if (purpose === "profile-import") return headers.includes("airline") && state.profileFields.some((field) => headers.includes(norm(field)));
    return true;
  };
  const candidates = parsed.tables.filter(matches);
  if (!candidates.length) throw new Error(`No worksheet in ${file.name} matched the expected ${purpose.replaceAll("-", " ")} columns.`);
  if (candidates.length > 1) throw new Error(`More than one worksheet in ${file.name} matches. Please save the required worksheet separately, then upload it.`);
  const table = candidates[0];
  return { headers: table.headers, rows: table.rows, filename: file.name, sheetName: table.name };
}

async function loadDemoTemplate(kind) {
  const isContract = kind === "contract";
  const path = isContract ? "/samples/contract-upload-template.csv" : "/samples/block-upload-template.csv";
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load the built-in ${kind} demo template.`);
  const table = parseCsv(await response.text(), path.split("/").at(-1));
  if (isContract) {
    state.demoContractTemplate = table; state.contractTemplate = table; state.contractTemplateSource = "demo";
    $("contract-template-name").textContent = "Built-in AIS contract demo template";
    $("contract-template-active-name").textContent = "Built-in AIS contract demo template";
    $("contract-template-count").textContent = `${table.headers.length} columns · demo sample headers only`;
    $("contract-template-active-count").textContent = `${table.headers.length} columns · demo sample headers only`;
    $("contract-template-warning").hidden = true;
    renderContractRows();
  } else {
    state.demoBlockTemplate = table;
    if (!state.selectedBlockProfile?.template?.headers?.length) setBlockTemplate(table, "Built-in AIS block demo template");
    $("block-template-warning").hidden = true;
    updateBlockGenerateButton();
  }
}

function setBlockTemplate(table, label = table?.filename || "Built-in AIS block demo template") {
  state.blockTemplate = table || null;
  if (!table) return;
  $("block-template-active-name").textContent = label;
  $("block-template-active-count").textContent = `${table.headers.length} columns · ${table.sheetName ? `${table.sheetName} sheet` : "profile template"}`;
  updateBlockGenerateButton();
}

function tableToObjects(table) {
  return table.rows.map((cells) => Object.fromEntries(table.headers.map((header, i) => [header, cells[i] ?? ""])));
}

function setFileMeta(id, file, suffix = "") {
  const node = $(id); node.hidden = !file;
  const label = node.querySelector("[data-file-name]");
  if (label) label.textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(0)} KB${suffix}` : "";
}

function setClearVisible(inputId, visible) {
  const button = document.querySelector(`[data-clear-file="${inputId}"]`);
  if (button) button.hidden = !visible;
}

function resetUpload(inputId) {
  $(inputId).value = "";
  setFileSelectionVisual($(inputId), false);
  setClearVisible(inputId, false);
  if (inputId === "contract-source-file") {
    state.contractSource = null; state.contractRows = []; state.lastContract = null;
    setFileMeta("contract-source-meta", null); $("contract-source-status").textContent = "";
    $("contract-inspection").hidden = true; $("contract-mapping").hidden = true; $("email-note").hidden = true;
    $("case-context").textContent = "New case"; $("contract-validation").replaceChildren();
  } else if (inputId === "contract-template-file") {
    state.lastContract = null;
    $("contract-mapping").hidden = true; $("contract-validation").replaceChildren();
    loadDemoTemplate("contract").catch((error) => notice(error.message, true));
  } else if (inputId === "block-source-file") {
    state.blockSource = null; state.blockRows = []; state.lastBlocks = null;
    setFileMeta("block-source-meta", null); $("block-source-status").textContent = ""; $("block-build-status").textContent = "";
    $("generate-block-files").disabled = true; $("block-validation").replaceChildren();
  } else if (inputId === "contract-result-file") {
    state.aisContracts = []; state.contractResultTable = null; state.blockRows = []; state.lastBlocks = null;
    setFileMeta("contract-result-meta", null); $("contract-result-name").textContent = "Select the AIS contract result";
    $("contract-result-status").textContent = ""; $("contract-result-status").classList.remove("error");
    $("generate-block-files").disabled = true;
  }
}

async function inspectFile(file, statusId) {
  if (!file) throw new Error("Choose a file first.");
  const status = $(statusId); status.textContent = "Reading in memory…"; status.classList.remove("error");
  const body = new FormData(); body.append("file", file);
  try {
    const data = await request("/api/source/inspect", { method: "POST", body });
    status.textContent = `Read ${data.tables.length} table(s)`;
    return data;
  } catch (error) { status.textContent = error.message; status.classList.add("error"); throw error; }
}

function showSourceInspection(data, sheetsId, findingId, inspectionId, groupsId) {
  $(inspectionId).hidden = false;
  $(sheetsId).replaceChildren(...data.tables.map((table) => {
    const chip = document.createElement("div"); chip.className = "sheet-chip";
    chip.innerHTML = `<strong title="${esc(table.name)}">${esc(table.name)}</strong><span>${table.rowCount} rows · ${table.headers.length} columns · ${esc(table.detectedRole)}</span>`;
    return chip;
  }));
  const groupCount = data.groups.length || data.tables.reduce((sum, table) => sum + (table.contractCandidates?.length || 0), 0);
  $(findingId).textContent = `${groupCount} flight/PNR group(s) found. ${data.tables.filter((t) => t.duplicateHeaders?.length).length ? "Duplicate headers need template review." : ""}${data.tables.some((t) => t.rowsOmittedForPrivacy) ? " Passenger-level rows from Departures are excluded; only route/date groups are used for contracts." : ""}${data.tables.some((t) => t.truncated) ? " A sheet exceeded the 20,000-row limit; export is blocked until the source is split." : ""}`;
  if (groupsId) $(groupsId).textContent = groupCount ? `${groupCount} candidate PNR group(s)` : "No PNR groups detected; source needs manual mapping.";
}

function sourceHasTruncatedSheets(source) {
  return Boolean(source?.tables?.some((table) => table.truncated));
}

function splitRoute(value) {
  const parts = String(value ?? "").split(/\s*(?:-|→|to)\s*/i).filter(Boolean);
  return [parts[0] ?? "", parts.at(-1) ?? ""];
}

function candidateContracts(source) {
  const groups = source.groups || [];
  const termsTables = source.tables.filter((t) => t.detectedRole === "Contract terms source");
  if (termsTables.length) {
    return termsTables.flatMap((table) => {
      const counts = new Map();
      for (const header of table.headers) counts.set(norm(header), (counts.get(norm(header)) || 0) + 1);
      return tableToObjects(table).map((obj, i) => {
        const suggested = {};
        for (const header of table.headers) {
          if (norm(header) === "contractid" || counts.get(norm(header)) > 1) continue;
          const sourceHeader = Object.keys(obj).find((key) => norm(key) === norm(header));
          if (sourceHeader && obj[sourceHeader] !== "") suggested[header] = obj[sourceHeader];
        }
        return { label: `${table.name} row ${i + 2}`, source: obj, sourceKind: "Terms sheet", suggested };
      });
    });
  }
  // Group repeated PNRs sharing the same source sheet and route into one candidate contract.
  const candidates = new Map();
  for (const group of groups) {
    const legs = group.legs || []; if (!legs.length) continue;
    const first = legs[0], last = legs.at(-1);
    const origin = first.origin || "", destination = last.destination || "";
    const signature = [group.sourceSheet, group.airline || "", origin, destination, group.direction || ""].join("|");
    if (!candidates.has(signature)) candidates.set(signature, {
      label: `${group.sourceSheet} · ${origin || "?"} → ${destination || "?"}`,
      sourceKind: "Procurement source",
      suggested: { "journey.1.from": origin, "journey.1.to": destination, airline: group.airline || "" },
      source: group,
    });
  }
  return [...candidates.values()];
}

function preparedContractRows(result, uploadHeaders, sourceKind) {
  return result.rows.map((values) => ({
    label: `${values[1]} → ${values[2]}${values[3] ? ` → ${values[4]}` : ""} · ${values[7]} to ${values[8]}`,
    values: uploadHeaders.map((header) => {
      const index = result.headers.findIndex((generatedHeader) => norm(generatedHeader) === norm(header));
      return index >= 0 ? values[index] || "" : "";
    }),
    suggested: {}, sourceKind,
  }));
}

async function prepareSourceContractRows() {
  const source = state.contractSource;
  const sourceTable = source?.tables?.find((table) => table.name.toLowerCase() === "summary" && table.contractCandidates?.length)
    || source?.tables?.find((table) => table.contractCandidates?.length);
  const candidates = sourceTable?.contractCandidates || source?.contractCandidates;
  if (!state.contractProfile || !candidates?.length) return false;
  if (sourceHasTruncatedSheets(source)) throw new Error("A source sheet exceeded the 20,000-row limit. Split it before preparing contracts.");
  const result = await request("/api/contracts/prepare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ airline: state.selectedProfile, candidates }) });
  const customTemplate = state.contractTemplateSource === "upload";
  const uploadHeaders = customTemplate ? state.contractTemplate.headers : result.headers;
  state.contractTemplate = { ...(state.contractTemplate || {}), headers: uploadHeaders };
  state.contractPrepared = true;
  $("confirm-contract-review").checked = false;
  state.contractRows = preparedContractRows(result, uploadHeaders, `${sourceTable?.name || "Procurement source"} · profile v${result.profileVersion}`);
  if (sourceTable) {
    const cancelled = result.cancelledRows ? ` ${result.cancelledRows} cancelled rows need review before export.` : "";
    $("departures-build-status").textContent = `${result.rowCount} contract row(s) from ${result.matchedSourceRows} source legs in ${sourceTable.name}.${cancelled}`;
  }
  showIssues("contract-validation", result.issues);
  return true;
}

function renderContractRows() {
  const headers = state.contractTemplate?.headers || [];
  const host = $("contract-row-editor"); host.replaceChildren();
  $("contract-row-count").textContent = `${state.contractRows.length} row(s)`;
  $("contract-mapping").hidden = !(headers.length && state.contractRows.length);
  if (!headers.length || !state.contractRows.length) return;
  state.contractRows.forEach((record, rowIndex) => {
    const card = document.createElement("article"); card.className = "contract-record";
      card.innerHTML = `<div class="record-heading"><div><h3>${esc(record.label)}</h3><p>Review the mapped route, dates, and approved airline terms before export.</p></div><span class="record-key">#${rowIndex + 1}</span></div>`;
    const fields = document.createElement("div"); fields.className = "contract-fields";
    headers.forEach((header, colIndex) => {
      const field = document.createElement("div"); field.className = "field";
      const isDuplicate = headers.indexOf(header) !== headers.lastIndexOf(header);
      const inputId = `contract-${rowIndex}-${colIndex}`;
      const profileKey = Object.keys(state.contractProfile?.fields || {}).find((key) => norm(key) === norm(header));
      const profileValue = profileKey ? state.contractProfile.fields[profileKey] : "";
      let initial = profileValue || record.values[colIndex] || "";
      if (!initial && !isDuplicate) {
        const key = norm(header);
        const match = Object.entries(record.suggested || {}).find(([candidate]) => norm(candidate) === key);
        if (match) initial = match[1];
      }
      const fromProfile = Boolean(profileKey && profileValue);
      const hint = initial ? `<small class="field-source">${fromProfile ? `Approved airline profile v${state.contractProfile.version} · locked` : `${esc(record.sourceKind || "Source suggestion")}; verify before upload`}</small>` : "";
      field.innerHTML = `<label for="${inputId}">${esc(header)}${isDuplicate ? ` · occurrence ${headers.slice(0, colIndex + 1).filter((h) => h === header).length}` : ""}</label><input id="${inputId}" data-contract-row="${rowIndex}" data-contract-col="${colIndex}" value="${esc(initial)}" placeholder="${isDuplicate ? "Ambiguous duplicate header" : "Enter confirmed value or leave blank"}" ${fromProfile ? "readonly" : ""} ${initial ? "class=\"is-suggested\"" : ""}>${hint}`;
      fields.append(field);
    });
    card.append(fields); host.append(card);
  });
  $("contract-readiness").textContent = `${state.contractRows.length} contract candidate(s) · draft only`;
  $("contract-readiness-detail").textContent = "Blank or unconfirmed AIS fields will appear in the validation notes. Confirm rules with Air Ops before AIS upload.";
  const requiresReview = state.contractPrepared;
  $("contract-review-line").hidden = !requiresReview;
  $("download-contract").disabled = !state.contractProfile || (requiresReview && !$("confirm-contract-review").checked);
}

function getContractRowsFromForm() {
  const headers = state.contractTemplate.headers;
  const rows = state.contractRows.map((record, rowIndex) => headers.map((_, colIndex) => {
    const input = document.querySelector(`[data-contract-row="${rowIndex}"][data-contract-col="${colIndex}"]`);
    if (input?.value) return input.value.trim();
    if (headers.indexOf(headers[colIndex]) !== headers.lastIndexOf(headers[colIndex])) return "";
    const header = norm(headers[colIndex]);
    const match = Object.entries(record.suggested || {}).find(([candidate]) => norm(candidate) === header);
    return match?.[1] || "";
  }));
  return rows;
}

function showIssues(hostId, issues) {
  const host = $(hostId); host.replaceChildren();
  if (!issues?.length) return;
  const list = document.createElement("ul"); list.className = "issue-list";
  for (const message of issues) { const li = document.createElement("li"); li.textContent = message; list.append(li); }
  host.append(list);
}

function downloadOutput(data, filenameBase, format) {
  let blob, filename;
  if (format === "xlsx") {
    if (!data.fileBase64) throw new Error("The service did not return the requested Excel workbook.");
    const binary = atob(data.fileBase64);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    filename = `${filenameBase}.xlsx`;
  } else {
    blob = new Blob(["\uFEFF", data.csv], { type: "text/csv;charset=utf-8" });
    filename = `${filenameBase}.csv`;
  }
  const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadArchive(data) {
  if (!data.archiveBase64 || !data.archiveFileName) throw new Error("The block service did not return the contract files archive.");
  const binary = atob(data.archiveBase64);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  const blob = new Blob([bytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
  anchor.href = url; anchor.download = data.archiveFileName; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function parseContractResult(table) {
  const idCol = table.headers.findIndex((header) => ["contractid", "id"].includes(norm(header)));
  if (idCol < 0) throw new Error("No contractId column was found. Upload the AIS contract result CSV after submission.");
  const nameCol = table.headers.findIndex((header) => norm(header) === "contractname");
  const records = table.rows.map((row) => ({ id: row[idCol]?.trim(), name: nameCol >= 0 ? row[nameCol]?.trim() : "", row }))
    .filter((item) => item.id && !/^contractid$/i.test(item.id));
  if (!records.length) throw new Error("No generated contract IDs were found in this result file.");
  const ids = records.map((item) => item.id);
  if (new Set(ids).size !== ids.length) throw new Error("The AIS contract result contains duplicate contract IDs. Resolve duplicates before preparing blocks.");
  return records;
}

function getMatchingContract(group) {
  const legs = group.legs || []; if (!legs.length) return "";
  const sourceRoutes = journeys(legs).filter((journey) => journey.length).map((journey) => [norm(journey[0].origin), norm(journey.at(-1).destination)]);
  const departure = parseDay(legs[0].date);
  const matches = state.aisContracts.filter((contract) => {
    const headers = state.contractResultTable.headers;
    const row = contract.row;
    const get = (wanted) => { const i = headers.findIndex((h) => norm(h) === norm(wanted)); return i >= 0 ? norm(row[i]) : ""; };
    const routes = [[get("journey.1.from"), get("journey.1.to")], [get("journey.2.from"), get("journey.2.to")]];
    const routeMatches = sourceRoutes.some(([from, to]) => routes.some(([routeFrom, routeTo]) => routeFrom === from && routeTo === to));
    const airlineMatches = !group.airline || !get("airline") || norm(group.airline) === get("airline");
    const startIndex = headers.findIndex((h) => norm(h) === norm("contractStartDate"));
    const endIndex = headers.findIndex((h) => norm(h) === norm("contractEndDate"));
    const start = startIndex >= 0 ? parseDay(row[startIndex]) : null;
    const end = endIndex >= 0 ? parseDay(row[endIndex]) : null;
    const inDateRange = departure == null || ((!start || departure >= start) && (!end || departure <= end));
    return routeMatches && airlineMatches && inDateRange;
  });
  return matches.length === 1 ? matches[0].id : "";
}

function contractReferences() {
  const headers = state.contractResultTable?.headers || [];
  const value = (row, field) => {
    const index = headers.findIndex((header) => norm(header) === norm(field));
    return index >= 0 ? String(row[index] || "").trim() : "";
  };
  return state.aisContracts.map((contract) => ({
    id: contract.id,
    airline: value(contract.row, "airline"),
    startDate: value(contract.row, "contractStartDate"),
    endDate: value(contract.row, "contractEndDate"),
    dummyContract: value(contract.row, "dummyContract"),
    routes: [1, 2].map((leg) => ({ from: value(contract.row, `journey.${leg}.from`), to: value(contract.row, `journey.${leg}.to`) }))
      .filter((route) => route.from && route.to),
  }));
}

function parseDay(value) {
  const text = String(value || "").trim();
  let match = text.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?:\s+\d{1,2}:\d{2})?$/);
  if (match) { let year = Number(match[3]); if (year < 100) year += year < 70 ? 2000 : 1900; return Date.UTC(year, Number(match[2]) - 1, Number(match[1])); }
  match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (match) return Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return null;
}

function ticketingDeadlineFor(record) {
  const raw = String(record?.group?.timeLimit || "").trim();
  if (!raw) return null;
  const sourceHeader = String(record?.group?.timeLimitHeader || "").trim();
  const expectedMatch = sourceHeader.match(/(?:\bD\s*[- ]?\s*|\bDeadline\s+)(\d+)\b/i);
  const expectedDays = expectedMatch ? Number(expectedMatch[1]) : null;
  const duration = raw.match(/^(?:D\s*-\s*)?(\d+(?:\.\d+)?)\s*(?:days?|d)?$/i);
  if (duration) {
    const days = Number(duration[1]);
    return Number.isFinite(days) && days >= 0
      ? { type: "BEFORE_DEPARTURE", value: `${days} days`, sourceHeader,
        warning: expectedDays != null && days !== expectedDays ? `Column label suggests ${expectedDays} days, but its value is ${days} days.` : "" }
      : null;
  }
  const deadlineDay = parseDay(raw);
  const departureDay = parseDay(record.date || record.group?.legs?.[0]?.date);
  if (deadlineDay == null || departureDay == null || deadlineDay > departureDay) return null;
  const days = Math.round((departureDay - deadlineDay) / 86400000);
  return { type: "BEFORE_DEPARTURE", value: `${days} days`, sourceHeader,
    warning: expectedDays != null && days !== expectedDays ? `Column label suggests ${expectedDays} days, but the deadline date is ${days} days before departure.` : "" };
}

function journeys(legs) {
  let splitAt = -1, largestGap = 1;
  for (let i = 1; i < legs.length; i++) {
    const before = parseDay(legs[i - 1].date), after = parseDay(legs[i].date);
    if (before != null && after != null) {
      const gap = (after - before) / 86400000;
      if (gap > largestGap) { largestGap = gap; splitAt = i; }
    }
  }
  return splitAt > 0 ? [legs.slice(0, splitAt), legs.slice(splitAt)] : [legs, []];
}

function targetValue(header, record) {
  const key = norm(header);
  const configured = state.selectedBlockProfile?.fields?.[header];
  if (key === "bookingstartdate") return contractFieldValue(record.contractId, "contractStartDate");
  if (key === "mmtproductclass") return productClassFor(record);
  if (key === "customerticketingdeadline") return ticketingDeadlineFor(record)?.value || "";
  if (key === "customerticketingdeadlinetype") return ticketingDeadlineFor(record)?.type || "";
  if (key.endsWith("farefamily")) {
    const dummy = contractFieldValue(record.contractId, "dummyContract").trim().toLowerCase();
    if (["yes", "true", "1"].includes(dummy)) return "Tentative";
    if (["no", "false", "0"].includes(dummy)) return "Smart Saver Fare";
    return "";
  }
  const sourceFareField = /\.paxfares\.(adult|child)\.bs$/i.test(header);
  if (!sourceFareField && configured != null && String(configured).trim() !== "") return String(configured);
  if (/\.CHILD\.(fareClass|cabinClass|productClass|fareFamily)$/i.test(header)) {
    const adultHeader = header.replace(/\.CHILD\./i, ".ADULT.");
    const adultValue = state.selectedBlockProfile?.fields?.[adultHeader];
    if (adultValue != null && String(adultValue).trim() !== "") return String(adultValue);
  }
  if (key === "contractid") return record.contractId;
  if (key === "airlinepnr") return record.group.pnr || "";
  if (key === "supplierpnr") return record.group.pnr || "";
  const itineraryMatch = header.match(/^itineraries\.(\d+)\.(from|to|depDate)$/i);
  const flightMatch = header.match(/^itineraries\.(\d+)\.itineraryFlights\.(\d+)\.(.+)$/i);
  const legs = record.group.legs || [];
  const journeyBuckets = journeys(legs);
  if (itineraryMatch) {
    const bucket = journeyBuckets[Number(itineraryMatch[1]) - 1] || [];
    if (Number(itineraryMatch[1]) === 1 && itineraryMatch[2].toLowerCase() === "from") return record.origin || bucket[0]?.origin || "";
    if (Number(itineraryMatch[1]) === 1 && itineraryMatch[2].toLowerCase() === "to") return record.destination || bucket.at(-1)?.destination || "";
    if (Number(itineraryMatch[1]) === 1 && itineraryMatch[2].toLowerCase() === "depdate") return record.date || bucket[0]?.date || "";
    if (itineraryMatch[2].toLowerCase() === "from") return bucket[0]?.origin || "";
    if (itineraryMatch[2].toLowerCase() === "to") return bucket.at(-1)?.destination || "";
    return bucket[0]?.date || "";
  }
  if (flightMatch) {
    const leg = journeyBuckets[Number(flightMatch[1]) - 1]?.[Number(flightMatch[2]) - 1];
    const suffix = flightMatch[3].split(".").at(-1);
    if (!leg) return "";
    const flight = leg.flight || ""; const flightParts = flight.match(/^\s*([A-Za-z0-9]{2})\s*[- ]?\s*([A-Za-z0-9]+)\s*$/);
    const mapped = { mrkAl: flightParts?.[1] || record.group.airline || "", oprAl: "", fltNo: flightParts?.[2] || "", depArpCd: leg.origin, arrArpCd: leg.destination, depTime: leg.departure, arrTime: leg.arrival };
    return mapped[suffix] || "";
  }
  if (key.endsWith("totseats")) return record.seats;
  if (/\.paxfares\.adult\.bs$/i.test(header)) return cleanSourceAmount(record.group.fare);
  return "";
}

function contractFieldValue(contractId, field) {
  const contract = state.aisContracts.find((item) => String(item.id) === String(contractId));
  const headers = state.contractResultTable?.headers || [];
  if (!contract) return "";
  const index = headers.findIndex((header) => norm(header) === norm(field));
  return index >= 0 ? String(contract.row[index] || "").trim() : "";
}

function productClassFor(record) {
  const cities = new Set();
  const legs = [...(record?.group?.legs || [])].map((leg) => ({ ...leg }));
  if (legs.length) {
    legs[0].origin = record.origin || legs[0].origin;
    legs.at(-1).destination = record.destination || legs.at(-1).destination;
  }
  for (const leg of legs) {
    if (leg.origin) cities.add(String(leg.origin).trim().toUpperCase());
    if (leg.destination) cities.add(String(leg.destination).trim().toUpperCase());
  }
  const count = cities.size;
  return count ? `Holiday#${count}` : "";
}

function cleanSourceAmount(value) {
  const text = String(value || "").trim().replace(/[₹$€£,\s]/g, "");
  if (!text || !/^\d+(?:\.\d+)?$/.test(text)) return "";
  return text;
}

function blockConfigName(code) {
  const match = String(code || "").match(/^BC(\d+)$/i);
  return match ? `Block Config ${match[1]}` : String(code || "Block Config");
}

function buildBlockRows() {
  const groups = state.blockSource?.groups || []; const headers = state.blockTemplate?.headers || [];
  state.blockRows = groups.map((group, index) => {
    const first = group.legs?.[0] || {}; const last = group.legs?.at(-1) || {};
    const record = { group, contractId: getMatchingContract(group), seats: group.seats || "", origin: first.origin || "", destination: last.destination || "", date: first.date || "", confirmed: false, index };
    return record;
  });
}

function gatherBlockData() {
  const headers = state.blockTemplate.headers;
  return state.blockRows.map((record) => {
    return headers.map((header) => {
      const value = targetValue(header, record);
      return value !== "" && value != null ? String(value) : "";
    });
  });
}

function blockGenerationIssues() {
  const issues = [];
  const matched = new Set();
  state.blockRows.forEach((record, index) => {
    const leg = record.group.legs?.[0] || {};
    const label = `${record.group.pnr || `source row ${index + 1}`} (${leg.origin || "?"}–${record.group.legs?.at(-1)?.destination || "?"})`;
    if (!record.contractId) issues.push(`${label}: no unique AIS contract matched by route, airline, and departure date.`);
    else matched.add(record.contractId);
    if (!record.group.pnr) issues.push(`${label}: airline PNR is missing.`);
    if (!record.origin || !record.destination) issues.push(`${label}: route airports are incomplete.`);
    if (!record.date) issues.push(`${label}: departure date is missing.`);
    if (!record.seats || !Number.isInteger(Number(record.seats)) || Number(record.seats) <= 0) issues.push(`${label}: procurement does not provide a positive whole-number seat quantity.`);
  });
  const uncovered = state.aisContracts.filter((contract) => !matched.has(contract.id)).map((contract) => contract.id);
  if (uncovered.length) issues.push(`No procurement block rows matched AIS contract ID(s): ${uncovered.join(", ")}. Upload matching departures for every contract.`);
  return issues;
}

function updateBlockGenerateButton() {
  const templateIsExport = state.blockTemplate?.headers?.some((header) => norm(header) === "blockid");
  const ready = Boolean(state.blockSource?.groups?.length && !sourceHasTruncatedSheets(state.blockSource) && state.aisContracts.length && state.blockTemplate?.headers?.length && !templateIsExport && state.selectedBlockProfile);
  $("generate-block-files").disabled = !ready;
}

function renderStage(stage) {
  state.stage = stage;
  $("contract-panel").hidden = stage !== "contract";
  $("departures-builder").hidden = stage !== "contract" || !state.contractSource?.tables?.some((table) => table.contractCandidates);
  $("profiles-panel").hidden = stage !== "profiles";
  setConfigurationView(state.configView);
  $("contract-inspection").hidden = stage !== "contract" || !state.contractSource;
  $("contract-mapping").hidden = stage !== "contract" || !state.contractTemplate || !state.contractRows.length;
  $("blocks-panel").hidden = stage !== "blocks";
  $("contract-terms-gate").hidden = stage !== "contract";
  $("contract-profile-status").textContent = state.contractProfile ? `${state.contractProfile.airline} · approved profile v${state.contractProfile.version}` : "Select a complete profile to continue.";
  $("contract-terms-alert").hidden = Boolean(state.contractProfile);
  $("contract-airline").value = state.selectedProfile || ""; syncEnhancedSelect($("contract-airline"));
  $("departures-airline").value = state.selectedProfile || ""; syncEnhancedSelect($("departures-airline"));
  $("departures-airline").disabled = true;
  syncEnhancedSelect($("departures-airline"));
  $("build-departures-contract").disabled = !state.contractProfile;
  $("download-contract").disabled = !state.contractProfile || (state.contractPrepared && !$("confirm-contract-review").checked);
  const content = {
    contract: ["Prepare contract upload", "Bring procurement details into the AIS contract template, review the gaps, then download a draft."],
    blocks: ["Prepare block upload", "Re-upload procurement, the AIS contract result, and the pre-submit block template."],
  profiles: ["Configuration", "Manage airline T&Cs and AIS upload templates."],
  }[stage];
  if (!content) return;
  $("page-title").textContent = content[0]; $("page-subtitle").textContent = content[1];
}

function setConfigurationView(view) {
  state.configView = ["templates", "block"].includes(view) ? view : "tnc";
  $("tnc-settings-panel").hidden = state.configView !== "tnc";
  $("templates-settings-panel").hidden = state.configView !== "templates";
  $("block-config-settings-panel").hidden = state.configView !== "block";
  document.querySelectorAll("[data-config-view]").forEach((button) => {
    if (button.getAttribute("role") === "tab") {
      const selected = button.dataset.configView === state.configView;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
  });
  document.querySelectorAll("[data-stage-link]").forEach((button) => {
    const selected = state.stage === "profiles"
      ? button.dataset.stageLink === "profiles" && button.dataset.configView === state.configView
      : button.dataset.stageLink === state.stage;
    button.classList.toggle("is-current", selected);
  });
}

const profileLabels = {
  dummyContract: "Dummy contract", isTicketingRequired: "Ticketing required", vendorId: "Vendor ID",
  toEmails: "To email addresses", toNames: "To names", ccEmails: "CC email addresses",
  "tnc.applicable": "T&C applicable to", "tnc.utilizationPercentage": "Utilization percentage",
  "tnc.dummyToRealPNRDeadline": "Dummy to real PNR deadline", "tnc.saleCutOffDeadline": "Sale cut-off deadline",
  "tnc.namingDeadline": "Naming deadline", "tnc.ticketingDeadline": "Ticketing deadline",
  "tnc.minSeatsToOperate": "Minimum seats to operate", "tnc.advancePaidAmount": "Advance paid amount",
  "tnc.advancePaidPercentage": "Advance paid percentage", "tnc.safeReleaseDeadline": "Safe release deadline",
  "tnc.finalReleaseDeadline": "Final release deadline", "tnc.nilCancellationPercentage": "Nil cancellation percentage",
  "tnc.contractPenaltyClause.penaltyType": "Penalty type", "tnc.contractPenaltyClause.basePenalty": "Penalty base",
  "tnc.contractPenaltyClause.penalty": "Penalty value", optionalTicketing: "Optional ticketing",
};

function isProfileFieldRequired(key, fields) {
  return !(key === "tnc.dummyToRealPNRDeadline" && String(fields?.dummyContract ?? "").trim().toLowerCase() === "no");
}

function setProfileStatus(message, isError = false) {
  const status = $("profile-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}
function updateNewBlockProfileAvailability() {
  const button = $("new-block-profile");
  if (button) button.disabled = !state.blockSchemaFields.length;
}
function jsonHeaders() {
  return { "Content-Type": "application/json" };
}
async function refreshBlockProfiles(selectCode = "") {
  const response = await request("/api/blocks/profiles");
  state.blockProfiles = response.profiles || [];
  state.blockSchemaFields = response.configFields || [];
  state.blockSchemaMetadata = response.fieldMetadata || [];
  state.blockProfileFields = [...state.blockSchemaFields];
  state.blockFieldMetadata = [...state.blockSchemaMetadata];
  const defaultProfile = state.blockProfiles.find(profile => profile.code === "BC1") || (state.blockProfiles.length === 1 ? state.blockProfiles[0] : null);
  for (const id of ["block-profile-select", "block-profile-active"]) {
    const select = $(id); const previous = selectCode || select.value || state.selectedBlockProfile?.code || defaultProfile?.code || "";
    select.replaceChildren(new Option("Select a saved Block Config", ""));
    state.blockProfiles.forEach(profile => select.add(new Option(`${blockConfigName(profile.code)} · v${profile.version}`, profile.code)));
    if (state.blockProfiles.some(p => p.code === previous)) select.value = previous;
    syncEnhancedSelect(select);
  }
  $("block-profile-store-status").textContent = `${state.blockProfiles.length} saved block configuration(s)`;
  updateNewBlockProfileAvailability();
  const code = $("block-profile-select").value;
  if (code) await loadBlockProfile(code);
  else {
    state.selectedBlockProfile = null;
    renderBlockConfigFields({});
  }
}
async function loadBlockProfile(code) {
  if (!code) {
    state.selectedBlockProfile = null;
    state.blockProfileFields = [];
    state.blockFieldMetadata = [];
    setBlockTemplate(state.demoBlockTemplate, "Built-in AIS block demo template");
    renderBlockConfigFields({}); updateBlockGenerateButton(); return;
  }
  const profile = await request(`/api/blocks/profiles/${encodeURIComponent(code)}`);
  state.selectedBlockProfile = profile; $("block-profile-code").value = profile.code;
  state.blockProfileFields = profile.configFields || [];
  state.blockFieldMetadata = profile.fieldMetadata || [];
  $("block-profile-version").textContent = `Version ${profile.version}`;
  $("block-profile-title").textContent = `${blockConfigName(profile.code)} · approved defaults`;
  $("block-profile-template-name").textContent = profile.templateName || "No profile template saved · using the built-in demo schema";
  $("block-profile-template-count").textContent = profile.templateColumnCount
    ? `${profile.templateColumnCount} template columns · upload another file to replace this profile's schema.`
    : "Template headers become editable profile fields when they are not supplied by source data or derived rules.";
  const savedTemplate = profile.template?.headers?.length
    ? { headers: profile.template.headers, rows: [], filename: profile.template.fileName }
    : state.demoBlockTemplate;
  if (savedTemplate) setBlockTemplate(savedTemplate, profile.template?.fileName || "Built-in AIS block demo template");
  renderBlockConfigFields(profile.fields, false);
  $("block-profile-active").value = profile.code; syncEnhancedSelect($("block-profile-active"));
  updateBlockGenerateButton();
}

function beginNewBlockProfile() {
  const usedCodes = new Set(state.blockProfiles.map((profile) => String(profile.code || "").toUpperCase()));
  let nextNumber = 1;
  while (usedCodes.has(`BC${nextNumber}`)) nextNumber += 1;
  const code = `BC${nextNumber}`;

  state.selectedBlockProfile = null;
  state.blockProfileFields = [...state.blockSchemaFields];
  state.blockFieldMetadata = [...state.blockSchemaMetadata];
  state.pendingBlockProfileTemplate = null;
  $("block-profile-select").value = "";
  syncEnhancedSelect($("block-profile-select"));
  $("block-profile-active").value = "";
  syncEnhancedSelect($("block-profile-active"));
  $("block-profile-code").value = code;
  $("block-profile-version").textContent = "Not saved";
  $("block-profile-title").textContent = `${blockConfigName(code)} · new profile`;
  $("block-profile-template-file").value = "";
  setFileSelectionVisual($("block-profile-template-file"), false);
  $("block-profile-template-name").textContent = "Choose a pre-submit AIS block template";
  $("block-profile-template-count").textContent = "Template headers become editable profile fields when they are not supplied by source data or derived rules.";
  $("block-profile-template-status").textContent = "";
  $("block-profile-template-status").classList.remove("error");
  $("block-template-warning").hidden = true;
  $("block-profile-import-file").value = "";
  setFileSelectionVisual($("block-profile-import-file"), false);
  $("block-profile-import-name").textContent = "Only consistent values are suggested; review before saving.";
  $("block-profile-import-status").textContent = "";
  $("block-profile-import-status").classList.remove("error");
  if (state.demoBlockTemplate) setBlockTemplate(state.demoBlockTemplate, "Built-in AIS block demo template");
  renderBlockConfigFields({}, false);
  $("block-profile-status").textContent = `${blockConfigName(code)} is ready. Add approved defaults or upload its template, then save.`;
  $("block-profile-status").classList.remove("error");
  updateBlockGenerateButton();
  $("block-profile-code").focus();
}

function renderBlockConfigFields(values = {}, readOnly = false) {
  const host = $("block-profile-fields"); host.replaceChildren();
  const groups = new Map();
  for (const key of state.blockProfileFields) {
    const group = state.blockFieldMetadata.find((item) => item.key === key)?.group || "Block-wide defaults";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(key);
  }
  for (const [title, keys] of groups) {
    const section = document.createElement("details"); section.className = "profile-field-group";
    section.open = title === "Block-wide defaults" || title === "Block timing and ticketing";
    const groupFieldStatus = `${keys.length} configurable value${keys.length === 1 ? "" : "s"}`;
    section.innerHTML = `<summary><span><strong>${esc(title)}</strong><small>${esc(groupFieldStatus)}</small></span><span class="profile-group-chevron" aria-hidden="true">⌄</span></summary>`;
    const grid = document.createElement("div"); grid.className = "profile-fields";
    keys.forEach(key => {
      const wrap = document.createElement("label"); wrap.className = "profile-field";
      const meta = state.blockFieldMetadata.find((item) => item.key === key);
      const required = false;
      const description = meta?.description || "";
      const help = description && !description.startsWith("Optional approved default") ? `<small>${esc(description)}</small>` : "";
      wrap.innerHTML = `<span class="profile-field-label">${esc(meta?.label || key)} ${required ? '<b class="required-star" aria-hidden="true">*</b>' : ""}</span><input data-block-profile-field="${esc(key)}" value="${esc(values[key] || "")}" ${readOnly ? "readonly" : ""}>${help}<details class="ais-field-key"><summary>AIS template field</summary><code>${esc(key)}</code></details><small class="field-error" data-block-profile-error hidden></small>`;
      const input = wrap.querySelector("input");
      input.addEventListener("input", () => {
        input.classList.remove("field-invalid");
        const error = wrap.querySelector("[data-block-profile-error]"); error.hidden = true; error.textContent = "";
      });
      grid.append(wrap);
    });
    section.append(grid); host.append(section);
  }
  $("save-block-profile").disabled = false;
  $("import-block-profile").disabled = !state.selectedBlockProfile || !$("block-profile-import-file").files[0];
}

async function importBlockProfileSuggestions() {
  if (!state.selectedBlockProfile) throw new Error("Select a saved Block Config first. To create a new one, upload its AIS template in “Template for this Block Config”.");
  const file = $("block-profile-import-file").files[0];
  if (!file) throw new Error("Choose a completed block file first.");
  const table = await readStructuredFile(file, "block-profile-import");
  const result = await request("/api/blocks/profiles/import-preview", {
    method: "POST", headers: jsonHeaders(),
    body: JSON.stringify({ profileCode: state.selectedBlockProfile.code, headers: table.headers, rows: table.rows.slice(0, 500) }),
  });
  const values = { ...(state.selectedBlockProfile?.fields || {}), ...result.fields };
  (result.conflicts || []).forEach((field) => { values[field] = ""; });
  renderBlockConfigFields(values, false);
  const conflicts = result.conflicts?.length ? ` ${result.conflicts.length} field(s) vary by row and were left for manual decision.` : "";
  const missing = result.missing?.length ? ` ${result.missing.length} field(s) had no value in the file.` : "";
  const sampleLimit = table.rows.length > 500 ? ` Suggestions examined the first 500 of ${table.rows.length} rows.` : "";
  $("block-profile-import-name").textContent = file.name;
  const conflictNames = result.conflicts?.length ? ` Varying fields: ${result.conflicts.slice(0, 8).join(", ")}${result.conflicts.length > 8 ? ", …" : ""}.` : "";
  $("block-profile-import-status").textContent = `Suggested ${result.consistentCount} consistent value(s); review all fields before saving.${conflicts}${missing}${sampleLimit}${conflictNames}`;
  $("block-profile-import-status").classList.remove("error");
}

async function refreshProfiles(selectCode = "") {
  const response = await request("/api/contracts/profiles");
  state.profiles = response.profiles || []; state.profileFields = response.fields || [];
  const selects = [$("profile-airline"), $("contract-airline"), $("departures-airline")];
  for (const select of selects) {
    const previous = select.value;
    select.replaceChildren(new Option(select.id === "profile-airline" ? "Select or add airline" : "Select an approved airline profile", ""));
    state.profiles.forEach((profile) => select.add(new Option(`${profile.airline} · v${profile.version}`, profile.airline)));
    const next = selectCode || previous;
    if (next && [...select.options].some((option) => option.value === next)) select.value = next;
    syncEnhancedSelect(select);
  }
  $("profile-store-status").textContent = `${state.profiles.length} approved profile(s)`;
}

function selectedAirline() {
  return $("new-airline-code").value.trim().toUpperCase() || $("profile-airline").value;
}

function renderProfileFields(fields = {}, readOnly = false) {
  const host = $("profile-fields"); host.replaceChildren();
  const constants = state.profileFields.filter((key) => !key.startsWith("tnc."));
  const tnc = state.profileFields.filter((key) => key.startsWith("tnc."));
  for (const [title, list] of [["Contract defaults", constants], ["Terms & conditions", tnc]]) {
    const group = document.createElement("section"); group.className = "profile-field-group";
    group.innerHTML = `<h3>${esc(title)}</h3><div class="profile-fields"></div>`;
    const grid = group.querySelector(".profile-fields");
    list.forEach((key) => {
      const field = document.createElement("label"); field.className = "field profile-field";
      const id = `profile-${key.replace(/[^a-z0-9]/gi, "-")}`;
      let control;
      if (["dummyContract", "isTicketingRequired", "optionalTicketing"].includes(key)) {
        control = document.createElement("select");
        ["", "Yes", "No"].forEach((value) => control.add(new Option(value || "Choose…", value)));
      } else {
        control = document.createElement("input"); control.type = "text";
        if (/percentage/i.test(key)) { control.inputMode = "decimal"; control.placeholder = "0–100"; }
        else control.placeholder = "Enter the approved value";
      }
      const required = isProfileFieldRequired(key, fields);
      control.id = id; control.dataset.profileField = key; control.value = fields[key] || ""; control.required = required; control.disabled = readOnly;
      const star = document.createElement("abbr"); star.className = "required-star"; star.title = "Required"; star.setAttribute("aria-label", "required"); star.textContent = "*"; star.hidden = !required;
      const error = document.createElement("small");
      error.className = "field-error"; error.dataset.profileError = key; error.hidden = true;
      field.htmlFor = id; field.append(document.createTextNode(profileLabels[key] || key), document.createTextNode(" "), star, control, error);
      grid.append(field);
    });
    host.append(group);
  }
  syncProfileSaveAvailability();
}

function syncProfileSaveAvailability() {
  const controls = [...document.querySelectorAll("[data-profile-field]")];
  const values = Object.fromEntries(controls.map((control) => [control.dataset.profileField, control.value.trim()]));
  controls.forEach((control) => {
    const required = isProfileFieldRequired(control.dataset.profileField, values);
    control.required = required;
    const star = control.closest("label")?.querySelector(".required-star");
    if (star) star.hidden = !required;
  });
  $("save-profile").disabled = false;
}

function validateProfileFields(fields) {
  const invalid = new Set(); const messages = []; const fieldErrors = {};
  const addError = (key, message) => { invalid.add(key); fieldErrors[key] = message; messages.push(message); };
  for (const key of state.profileFields) {
    const value = String(fields[key] ?? "").trim();
    if (isProfileFieldRequired(key, fields) && !value) {
      addError(key, `${profileLabels[key] || key} is required.`);
    }
  }
  for (const key of ["tnc.utilizationPercentage", "tnc.advancePaidPercentage", "tnc.nilCancellationPercentage"]) {
    const value = String(fields[key] ?? "").trim();
    if (!value) continue;
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0 || number > 100) {
      addError(key, `${profileLabels[key]} must be between 0 and 100.`);
    }
  }
  for (const key of ["tnc.minSeatsToOperate", "tnc.advancePaidAmount"]) {
    const value = String(fields[key] ?? "").trim();
    if (!value) continue;
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) {
      addError(key, `${profileLabels[key]} must be a non-negative number.`);
    }
  }
  return { invalid, messages, fieldErrors };
}

function updateProfileFieldValidation(event) {
  syncProfileSaveAvailability();
  if (event?.target?.matches?.("[data-profile-field]")) event.target.dataset.touched = "true";
  const controls = [...document.querySelectorAll("[data-profile-field]")];
  const fields = Object.fromEntries(controls.map((control) => [control.dataset.profileField, control.value.trim()]));
  const result = validateProfileFields(fields);
  if (!state.profileSaveAttempted) return;
  highlightProfileFields(result);
  if (result.messages.length) setProfileStatus(result.messages[0], true);
  else if ($("profile-status").classList.contains("error")) setProfileStatus("");
}

function highlightProfileFields(validation) {
  document.querySelectorAll("[data-profile-field]").forEach((control) => {
    const key = control.dataset.profileField;
    const invalid = validation.invalid.has(key);
    control.classList.toggle("field-invalid", invalid);
    if (invalid) control.setAttribute("aria-invalid", "true"); else control.removeAttribute("aria-invalid");
    const error = control.closest(".profile-field")?.querySelector("[data-profile-error]");
    if (error) { error.textContent = validation.fieldErrors[key] || ""; error.hidden = !invalid; }
  });
}

async function loadAirlineProfile(code = $("profile-airline").value) {
  state.profileSaveAttempted = false;
  if (!code) { state.activeProfile = null; $("profile-form-title").textContent = "Enter or select an airline code"; $("profile-version").textContent = "No version loaded"; renderProfileFields({}); return; }
  setProfileStatus("Loading profile…");
  try {
    const profile = await request(`/api/contracts/profiles/${encodeURIComponent(code)}`);
    state.activeProfile = profile; $("profile-airline").value = profile.airline; syncEnhancedSelect($("profile-airline"));
    $("profile-form-title").textContent = `${profile.airline} · approved terms`;
    $("profile-version").textContent = `Version ${profile.version}`;
    renderProfileFields(profile.fields);
    $("profile-history").textContent = `${profile.history?.length || 0} earlier version(s) retained for review.`;
    setProfileStatus(`Updated ${new Date(profile.updatedAt).toLocaleString()} · ${profile.updatedBy}`);
  } catch (error) {
    if (error.message.includes("404")) {
      state.activeProfile = null; $("profile-form-title").textContent = `${code} · new profile`;
      $("profile-version").textContent = "Not saved"; renderProfileFields({});
      $("profile-history").textContent = "New airline profile. Complete every field and save to publish it.";
      setProfileStatus("No saved profile yet.");
    } else setProfileStatus(error.message, true);
  }
}

function beginNewAirlineProfile() {
  state.activeProfile = null;
  state.profileSaveAttempted = false;
  $("profile-airline").value = "";
  syncEnhancedSelect($("profile-airline"));
  $("new-airline-code").value = "";
  $("profile-form-title").textContent = "New airline profile";
  $("profile-version").textContent = "Not saved";
  $("profile-history").textContent = "Enter an airline code, complete the required terms, then save the approved profile.";
  $("profile-import-file").value = "";
  setFileSelectionVisual($("profile-import-file"), false);
  renderProfileFields({});
  setProfileStatus("Enter a new airline code to begin.");
  $("new-airline-code").focus();
}

$("new-airline-profile").addEventListener("click", beginNewAirlineProfile);
$("profile-fields").addEventListener("input", updateProfileFieldValidation);
$("profile-fields").addEventListener("change", updateProfileFieldValidation);
$("profile-airline").addEventListener("change", () => { $("new-airline-code").value = ""; loadAirlineProfile(); });
$("new-airline-code").addEventListener("change", () => loadAirlineProfile(selectedAirline()));
$("load-profile").addEventListener("click", () => loadAirlineProfile(selectedAirline()));
$("contract-airline").addEventListener("change", async () => {
  const code = $("contract-airline").value;
  state.selectedProfile = code || null;
  state.contractProfile = null;
  state.lastContract = null;
  state.contractPrepared = false;
  renderContractRows();
  $("contract-mapping").hidden = !(state.contractTemplate && state.contractRows.length);
  $("departures-airline").value = code; syncEnhancedSelect($("departures-airline"));
  $("build-departures-contract").disabled = true;
  if (!code) { renderStage(state.stage); return; }
  $("contract-profile-status").textContent = "Checking approved profile…";
  try {
    const profile = await request(`/api/contracts/profiles/${encodeURIComponent(code)}`);
    const missing = state.profileFields.filter((key) => isProfileFieldRequired(key, profile.fields) && !String(profile.fields?.[key] ?? "").trim());
    if (missing.length) throw new Error(`Profile is incomplete (${missing.join(", ")}). Open Airline T&Cs to complete and approve it.`);
    state.contractProfile = profile; state.selectedProfileVersion = profile.version;
    $("departures-build-status").textContent = `Using ${code} approved profile v${profile.version}.`;
  } catch (error) {
    state.selectedProfile = null; $("contract-airline").value = ""; syncEnhancedSelect($("contract-airline")); $("departures-airline").value = ""; syncEnhancedSelect($("departures-airline"));
    $("contract-profile-status").textContent = "Profile unavailable or incomplete.";
    $("contract-terms-alert").textContent = error.message;
    $("contract-terms-alert").hidden = false;
    renderContractRows();
    renderStage(state.stage);
    return;
  }
  try {
    await prepareSourceContractRows();
    renderContractRows();
  } catch (error) {
    $("departures-build-status").textContent = error.message;
    notice(error.message, true);
  }
  renderStage(state.stage);
});

$("refresh-airlines").addEventListener("click", async () => {
  try { await refreshProfiles(); notice("Airline profiles refreshed."); }
  catch (error) { $("departures-build-status").textContent = error.message; }
});

$("save-profile").addEventListener("click", async () => {
  const airline = selectedAirline();
  if (!airline) { setProfileStatus("Select or enter an airline code first.", true); return; }
  const fields = Object.fromEntries([...document.querySelectorAll("[data-profile-field]")].map((input) => [input.dataset.profileField, input.value.trim()]));
  state.profileSaveAttempted = true;
  const validation = validateProfileFields(fields);
  highlightProfileFields(validation);
  if (validation.messages.length) { setProfileStatus(validation.messages[0], true); return; }
  setProfileStatus("Saving approved profile…");
  try {
    const saved = await request(`/api/contracts/profiles/${encodeURIComponent(airline)}`, { method: "PUT", headers: jsonHeaders(), body: JSON.stringify({ fields }) });
    state.profileSaveAttempted = false; state.activeProfile = saved; $("new-airline-code").value = ""; await refreshProfiles(airline); await loadAirlineProfile(airline);
    notice(`${airline} profile version ${saved.version} saved.`);
  } catch (error) {
    const message = error.message;
    const invalid = new Set(state.profileFields.filter((key) => message.includes(key)));
    const fieldErrors = Object.fromEntries([...invalid].map((key) => [key, message]));
    highlightProfileFields({ invalid, fieldErrors });
    setProfileStatus(message, true);
  }
});

$("profile-import-file").addEventListener("change", async (event) => {
  const file = event.target.files[0]; if (!file) return;
  try {
    const table = await readStructuredFile(file, "profile-import");
    const result = await request("/api/contracts/profiles/import-preview", { method: "POST", headers: jsonHeaders(), body: JSON.stringify({ headers: table.headers, rows: table.rows }) });
    $("new-airline-code").value = result.airline; $("profile-airline").value = [...$("profile-airline").options].some((o) => o.value === result.airline) ? result.airline : ""; syncEnhancedSelect($("profile-airline"));
    state.profileSaveAttempted = false; state.activeProfile = null; renderProfileFields(result.fields);
    $("profile-form-title").textContent = `${result.airline} · imported values`;
    const hasIssues = result.conflicts.length || result.missing.length;
    setProfileStatus(`${result.conflicts.length ? `Conflicting values: ${result.conflicts.join(", ")}. ` : ""}${result.missing.length ? `Complete these fields: ${result.missing.join(", ")}.` : "Imported values are consistent; review and save to approve."}`, Boolean(hasIssues));
  } catch (error) { setProfileStatus(error.message, true); }
  finally { event.target.value = ""; }
});

$("build-departures-contract").addEventListener("click", async () => {
  if (!state.contractProfile) return;
  $("departures-build-status").textContent = "Preparing contracts from sector groups…";
  try {
    await prepareSourceContractRows();
    renderContractRows();
    $("contract-mapping").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { $("departures-build-status").textContent = error.message; }
});


$("confirm-contract-review").addEventListener("change", () => {
  if (state.contractPrepared) $("download-contract").disabled = !state.contractProfile || !$("confirm-contract-review").checked;
});

$("contract-source-file").addEventListener("change", () => {
  const file = $("contract-source-file").files[0]; if (!file) return;
  state.contractSource = null; state.contractRows = []; state.contractPrepared = false; $("contract-inspection").hidden = true; $("contract-mapping").hidden = true; $("email-note").hidden = true;
  setFileMeta("contract-source-meta", file); setClearVisible("contract-source-file", true); $("contract-source-status").textContent = "Ready to inspect";
});
$("block-source-file").addEventListener("change", () => {
  const file = $("block-source-file").files[0]; if (!file) return;
  state.blockSource = null; state.blockRows = [];
  setFileMeta("block-source-meta", file); setClearVisible("block-source-file", true); $("block-source-status").textContent = "Ready to inspect";
  $("generate-block-files").disabled = true; $("block-validation").replaceChildren();
});

$("inspect-contract-source").addEventListener("click", async () => {
  try {
    state.contractSource = await inspectFile($("contract-source-file").files[0], "contract-source-status");
    showSourceInspection(state.contractSource, "contract-sheets", "contract-finding", "contract-inspection", "contract-finding");
    const sourceTable = state.contractSource.tables.find((table) => table.name.toLowerCase() === "summary" && table.contractCandidates?.length)
      || state.contractSource.tables.find((table) => table.contractCandidates?.length);
    if (sourceTable) {
      $("contract-finding").textContent = `${sourceTable.rowCount.toLocaleString()} ${sourceTable.name} rows scanned; ${sourceTable.contractCandidates.length} airline/route groups found. Reciprocal sectors form one return contract only when their PNR matches.`;
      await refreshProfiles();
      $("departures-build-status").textContent = state.profiles.length ? "Choose the airline profile matching this procurement file." : "No approved airline profile exists yet. Create one in Airline T&Cs.";
    }
    state.contractRows = candidateContracts(state.contractSource).map((candidate) => ({ ...candidate, values: [] }));
    if (state.contractProfile) await prepareSourceContractRows();
    $("case-context").textContent = state.contractSource.fileName;
    const email = state.contractSource.email;
    $("email-note").hidden = !email;
    if (email) $("email-note").textContent = `Email: ${email.subject || "(no subject)"}\nAttachments: ${(email.attachments || []).join(", ") || "none parsed"}\n${email.bodyExcerpt || "No plain-text body was found."}`;
    renderContractRows();
    renderStage(state.stage);
  } catch (error) { notice(error.message, true); }
});

$("contract-template-file").addEventListener("change", async (event) => {
  const file = event.target.files[0]; if (!file) return;
  state.contractTemplateSource = "upload";
  state.contractTemplate = null; setClearVisible("contract-template-file", true);
  $("contract-template-name").textContent = file.name; $("contract-template-count").textContent = "Reading template…";
  $("contract-mapping").hidden = true;
  try {
    state.contractTemplate = await readStructuredFile(file, "contract-template");
    $("contract-template-name").textContent = file.name;
    $("contract-template-active-name").textContent = file.name;
    $("contract-template-count").textContent = `${state.contractTemplate.headers.length} columns · ${new Set(state.contractTemplate.headers).size} unique names`;
    $("contract-template-active-count").textContent = `${state.contractTemplate.headers.length} columns`;
    const duplicates = [...new Set(state.contractTemplate.headers.filter((h, i, all) => all.indexOf(h) !== i))];
    $("contract-template-warning").hidden = !duplicates.length;
    $("contract-template-warning").textContent = duplicates.length ? `Duplicate headers: ${duplicates.join(", ")}. Occurrences are preserved; confirm what each represents.` : "";
    renderContractRows();
  } catch (error) {
    $("contract-template-count").textContent = "Template could not be read";
    $("contract-template-warning").hidden = false; $("contract-template-warning").textContent = error.message;
    notice(error.message, true);
  }
});

$("download-contract").addEventListener("click", async () => {
  try {
    if (!state.contractProfile) throw new Error("Select a complete, approved Airline T&C profile before generating contracts.");
    if (sourceHasTruncatedSheets(state.contractSource)) throw new Error("A source sheet exceeded the 20,000-row processing limit. Split the source and inspect it again before exporting.");
    if (state.contractPrepared && !$("confirm-contract-review").checked) throw new Error("Review the route, dates, status counts, profile version, and AIS columns before downloading.");
    const rows = getContractRowsFromForm();
    const format = $("contract-output-format").value;
    const data = await request("/api/contracts/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ headers: state.contractTemplate.headers, rows, airline: state.selectedProfile, format }) });
    state.lastContract = data; showIssues("contract-validation", data.issues);
    if (!data.canDownload) throw new Error("Contract export was blocked by template or CSV safety checks. Review the issues above.");
    downloadOutput(data, "airops-contract-draft", format);
    notice(`Contract draft downloaded as ${format.toUpperCase()}. Upload it in AIS, then return with the generated-ID file.`);
  } catch (error) { notice(error.message, true); }
});

$("clear-contract-case").addEventListener("click", () => {
  resetUpload("contract-source-file"); notice("Contract source cleared from this page session.");
});

$("contract-result-file").addEventListener("change", async (event) => {
  const file = event.target.files[0]; if (!file) return;
  state.aisContracts = []; state.contractResultTable = null; state.blockRows = []; state.lastBlocks = null;
  $("contract-result-name").textContent = file.name; setFileMeta("contract-result-meta", file); setClearVisible("contract-result-file", true);
  $("contract-result-status").textContent = "Reading AIS result…"; $("contract-result-status").classList.remove("error");
  $("generate-block-files").disabled = true;
  try {
    const table = await readStructuredFile(file, "contract-result"); state.contractResultTable = table; state.aisContracts = parseContractResult(table);
    $("contract-result-name").textContent = file.name; setFileMeta("contract-result-meta", file, ` · ${state.aisContracts.length} contract ID(s)`);
    $("contract-result-status").textContent = `Loaded ${state.aisContracts.length} AIS-generated contract ID(s)`; $("contract-result-status").classList.remove("error");
    updateBlockGenerateButton();
  } catch (error) {
    setFileMeta("contract-result-meta", file);
    $("contract-result-status").textContent = error.message; $("contract-result-status").classList.add("error");
    state.aisContracts = []; state.contractResultTable = null; notice(error.message, true);
  }
});

state.pendingBlockProfileTemplate = null;
function updateBlockTemplateSaveButton() {
  $("save-block-template").disabled = !state.pendingBlockProfileTemplate;
}

$("block-profile-template-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  event.currentTarget.value = "";
  state.pendingBlockProfileTemplate = null;
  updateBlockTemplateSaveButton();
  if (!file) return;
  $("block-profile-template-name").textContent = file.name;
  $("block-profile-template-count").textContent = "Reading template headers…";
  $("block-profile-template-status").textContent = "";
  try {
    const table = await readStructuredFile(file, "block-template");
    state.pendingBlockProfileTemplate = table;
    $("block-profile-template-count").textContent = `${table.headers.length} columns · ${table.rows.length} sample row(s). Header schema only is stored in configuration.`;
    updateBlockTemplateSaveButton();
  } catch (error) {
    $("block-profile-template-count").textContent = error.message;
    $("block-profile-template-status").textContent = "Choose a valid pre-submit block template.";
    $("block-profile-template-status").classList.add("error");
  }
});

$("save-block-template").addEventListener("click", async () => {
  const code = ($("block-profile-code").value || $("block-profile-select").value).trim().toUpperCase();
  const table = state.pendingBlockProfileTemplate;
  const status = $("block-profile-template-status");
  status.classList.remove("error");
  try {
    if (!code) throw new Error("Select an existing Block Config or enter a profile ID such as BC2.");
    if (!table) throw new Error("Choose a block upload template first.");
    status.textContent = "Saving template schema…";
    const saved = await request(`/api/blocks/profiles/${encodeURIComponent(code)}/template`, {
      method: "PUT", headers: jsonHeaders(),
      body: JSON.stringify({ headers: table.headers, fileName: table.filename }),
    });
    await refreshBlockProfiles(saved.code);
    const suggestion = await request("/api/blocks/profiles/import-preview", {
      method: "POST", headers: jsonHeaders(),
      body: JSON.stringify({ profileCode: saved.code, headers: table.headers, rows: table.rows.slice(0, 500) }),
    });
    const values = { ...(saved.fields || {}), ...suggestion.fields };
    (suggestion.conflicts || []).forEach((field) => { values[field] = ""; });
    renderBlockConfigFields(values, false);
    const conflictCount = suggestion.conflicts?.length || 0;
    const sampledRows = Math.min(table.rows.length, 500);
    const sampleNote = table.rows.length > sampledRows ? ` Suggestions used the first ${sampledRows} of ${table.rows.length} sample rows.` : "";
    status.textContent = `Template saved to ${blockConfigName(saved.code)} v${saved.version}. ${saved.configFields.length} profile fields are available; ${suggestion.consistentCount} consistent sample value(s) suggested. Review and save approved values below${conflictCount ? `; ${conflictCount} varying field(s) left blank` : ""}.${sampleNote}`;
    $("block-profile-template-name").textContent = saved.templateName || table.filename;
    $("block-profile-import-name").textContent = table.filename;
    state.pendingBlockProfileTemplate = null;
    $("block-profile-template-file").value = "";
    updateBlockTemplateSaveButton();
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  }
});

$("inspect-block-source").addEventListener("click", async () => {
  try {
    state.blockSource = await inspectFile($("block-source-file").files[0], "block-source-status");
    const groupCount = state.blockSource.groups.length;
    const truncated = sourceHasTruncatedSheets(state.blockSource);
    $("block-build-status").textContent = truncated
      ? "A source sheet exceeded the 20,000-row processing limit. Split the source and inspect it again to avoid an incomplete block file."
      : `${state.blockSource.tables.length} worksheet/table(s) · ${groupCount} PNR candidate(s) detected`;
    updateBlockGenerateButton();
  } catch (error) { notice(error.message, true); }
});

$("generate-block-files").addEventListener("click", async () => {
  try {
    $("generate-block-files").disabled = true;
    $("block-build-status").classList.remove("error");
    $("block-build-status").textContent = "Matching departures to AIS contracts and preparing files…";
    $("block-validation").replaceChildren();
    if (!state.blockSource || !state.aisContracts.length || !state.blockTemplate) throw new Error("Upload the procurement source, AIS contract result, and block upload template first.");
    if (!state.selectedBlockProfile) throw new Error("Select a saved Block Config profile before downloading.");
    if (state.blockSource.tables.some((table) => table.truncated)) throw new Error("A source sheet exceeded the row limit. Split the source and inspect it again before generating blocks.");
    if (state.blockTemplate.headers.some((header) => norm(header) === "blockid")) throw new Error("Choose the pre-submit block upload template, not an AIS export.");
    buildBlockRows();
    const missing = blockGenerationIssues();
    if (missing.length) { showIssues("block-validation", missing); throw new Error("Could not create a complete contract-by-contract set of block files. Fix the listed source or contract coverage issues."); }
    const rows = gatherBlockData();
    const format = $("block-output-format").value;
    const data = await request("/api/blocks/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ headers: state.blockTemplate.headers, rows, format, profileCode: state.selectedBlockProfile.code, profileVersion: state.selectedBlockProfile.version, contractReferences: contractReferences() }) });
    state.lastBlocks = data; showIssues("block-validation", data.issues);
    if (!data.canDownload) throw new Error("Block export was blocked by schema or data checks. Review the issues above.");
    downloadArchive(data);
    $("block-build-status").textContent = `Downloaded ${data.contractCount} contract file(s) with ${data.rowCount} block row(s) in ${data.archiveFileName}.`;
    notice(`Downloaded ${data.contractCount} block file(s), one per AIS contract ID.`);
  } catch (error) { $("block-build-status").textContent = error.message; $("block-build-status").classList.add("error"); notice(error.message, true); }
  finally { updateBlockGenerateButton(); }
});

document.querySelectorAll("[data-stage-link]").forEach((button) => button.addEventListener("click", () => {
  const stage = button.dataset.stageLink;
  if (stage === "profiles") state.configView = button.dataset.configView || "tnc";
  renderStage(stage);
}));
document.querySelectorAll('[role="tab"][data-config-view]').forEach((button) => button.addEventListener("click", () => setConfigurationView(button.dataset.configView)));
$("block-profile-select").addEventListener("change", async () => { try { await loadBlockProfile($("block-profile-select").value); } catch (error) { $("block-profile-status").textContent = error.message; } });
$("block-profile-active").addEventListener("change", async () => { try { await loadBlockProfile($("block-profile-active").value); updateBlockGenerateButton(); } catch (error) { notice(error.message, true); } });
$("new-block-profile").addEventListener("click", beginNewBlockProfile);
$("block-profile-code").addEventListener("input", updateBlockTemplateSaveButton);
$("block-profile-select").addEventListener("change", updateBlockTemplateSaveButton);
$("block-profile-import-file").addEventListener("change", () => {
  const file = $("block-profile-import-file").files[0];
  $("block-profile-import-name").textContent = file?.name || "Only consistent values are suggested; review before saving.";
  $("import-block-profile").disabled = !state.selectedBlockProfile || !file;
  if (file && !state.selectedBlockProfile) {
    $("block-profile-import-status").textContent = "Select a saved profile to suggest its values. For a new BC profile, use Template for this Block Config below.";
    $("block-profile-import-status").classList.remove("error");
  }
});
$("import-block-profile").addEventListener("click", async () => {
  try { await importBlockProfileSuggestions(); }
  catch (error) { $("block-profile-import-status").textContent = error.message; $("block-profile-import-status").classList.add("error"); }
});
$("save-block-profile").addEventListener("click", async () => {
  const code = $("block-profile-code").value.trim().toUpperCase();
  const fields = Object.fromEntries([...document.querySelectorAll("[data-block-profile-field]")].map(input => [input.dataset.blockProfileField, input.value.trim()]));
  const empty = [...document.querySelectorAll("[data-block-profile-field]")].filter(input => !input.value.trim() && state.blockFieldMetadata.find((field) => field.key === input.dataset.blockProfileField)?.required !== false);
  document.querySelectorAll("[data-block-profile-field]").forEach(input => input.classList.remove("field-invalid"));
  document.querySelectorAll("[data-block-profile-error]").forEach(error => { error.hidden = true; error.textContent = ""; });
  empty.forEach(input => {
    input.classList.add("field-invalid");
    const reason = input.closest("label").querySelector("[data-block-profile-error]");
    reason.textContent = "Required: enter or import an approved reusable value."; reason.hidden = false;
  });
  if (empty.length) {
    empty[0].focus();
    $("block-profile-status").textContent = `${empty.length} required value(s) are missing. Fill the red fields before saving.`;
    $("block-profile-status").classList.add("error");
    return;
  }
  try {
    const saved = await request(`/api/blocks/profiles/${encodeURIComponent(code)}`, {method:"PUT",headers:jsonHeaders(),body:JSON.stringify({fields})});
    await refreshBlockProfiles(saved.code); $("block-profile-status").textContent = `${blockConfigName(saved.code)} saved as version ${saved.version}.`;
    $("block-profile-status").classList.remove("error");
    $("block-profile-version").textContent = `Version ${saved.version}`;
  } catch(error) { $("block-profile-status").textContent = error.message; $("block-profile-status").classList.add("error"); }
});
refreshProfiles().catch((error) => { $("profile-store-status").textContent = error.message; });
refreshBlockProfiles().catch((error) => { $("block-profile-store-status").textContent = error.message; });
document.querySelectorAll("[data-clear-file]").forEach((button) => button.addEventListener("click", () => {
  const inputId = button.dataset.clearFile;
  resetUpload(inputId);
  notice(inputId.includes("template") ? "Restored the built-in demo template." : "Selected file removed. Choose another file to continue.");
}));
window.addEventListener("beforeunload", () => { state.contractSource = null; state.blockSource = null; state.aisContracts = []; });

loadDemoTemplate("contract").catch((error) => notice(error.message, true));
loadDemoTemplate("block").catch((error) => notice(error.message, true));
renderStage("contract");
