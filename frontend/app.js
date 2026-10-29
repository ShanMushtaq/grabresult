/* GrabResult frontend — vanilla JS, no build step. All rendering uses
   textContent/DOM APIs so untrusted data can never become executable HTML. */
const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}
function fmtTime(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString();
}
function toast(msg, isErr) {
  const t = el("div", "toast" + (isErr ? " err" : ""), msg);
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4200);
}
async function api(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({"Content-Type": "application/json"}, opts.headers || {});
  const r = await fetch(path, opts);
  let data = {};
  try { data = await r.json(); } catch (e) { /* non-json */ }
  if (!r.ok) throw new Error((data && data.error) || ("Request failed: " + r.status));
  return data;
}
function badge(status) {
  return el("span", "badge " + status, status.replace(/_/g, " "));
}
function scoreCell(score) {
  const wrap = el("div", "score-cell");
  const bar = el("div", "score-bar");
  const fill = el("div"); fill.style.width = Math.min(100, score) + "%";
  bar.appendChild(fill);
  wrap.appendChild(bar);
  wrap.appendChild(el("b", null, String(score)));
  return wrap;
}

/* ---------------- navigation ---------------- */
const VIEWS = {
  dashboard: {title: "Dashboard", render: renderDashboard},
  new: {title: "New Research", render: renderNewResearch},
  history: {title: "Research History", render: renderHistory},
  leads: {title: "Leads Database", render: renderLeads},
  imports: {title: "Imports", render: renderImports},
  exports: {title: "Exports", render: renderExports},
  settings: {title: "Settings", render: renderSettings},
  help: {title: "Help", render: renderHelp},
};
let currentView = "dashboard";
function navigate(view) {
  currentView = view;
  $$("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $("#viewTitle").textContent = VIEWS[view].title;
  $("#sidebar").classList.remove("open");
  const c = $("#content"); c.innerHTML = "";
  c.appendChild(el("p", "muted", "Loading…"));
  VIEWS[view].render(c).catch(e => {
    c.innerHTML = "";
    c.appendChild(el("div", "card", ""));
    const card = c.firstChild;
    card.appendChild(el("h2", null, "Something went wrong"));
    card.appendChild(el("p", "muted", e.message));
  });
  window.scrollTo(0, 0);
}
$("#nav").addEventListener("click", e => {
  const b = e.target.closest("button[data-view]");
  if (b) navigate(b.dataset.view);
});
$("#menuBtn").addEventListener("click", () => $("#sidebar").classList.toggle("open"));

/* ---------------- dashboard ---------------- */
async function renderDashboard(c) {
  c.innerHTML = "";
  const d = await api("/api/dashboard");
  const stats = el("div", "grid cols-4");
  const cards = [
    [d.total_leads, "Leads in database"],
    [d.total_jobs, "Research jobs"],
    [d.by_status.qualified || 0, "Qualified leads"],
    [d.by_status.needs_review || 0, "Need review"],
  ];
  cards.forEach(([n, lbl]) => {
    const s = el("div", "stat");
    s.appendChild(el("div", "num", String(n)));
    s.appendChild(el("div", "lbl", lbl));
    stats.appendChild(s);
  });
  c.appendChild(stats);

  const row = el("div", "grid cols-2");
  const jCard = el("div", "card");
  jCard.appendChild(el("h2", null, "Recent research"));
  if (!d.recent_jobs.length) {
    jCard.appendChild(el("div", "empty", ""));
    jCard.lastChild.appendChild(el("div", "big", "🔍"));
    jCard.lastChild.appendChild(el("p", null, "No research yet. Start your first one!"));
    const b = el("button", "btn", "New research");
    b.onclick = () => navigate("new");
    jCard.lastChild.appendChild(b);
  } else {
    const t = el("table"); const tb = el("tbody");
    d.recent_jobs.forEach(j => {
      const tr = el("tr");
      tr.appendChild(el("td", null, j.request_text || "(no description)"));
      const td = el("td"); td.appendChild(badge(j.status)); tr.appendChild(td);
      tr.appendChild(el("td", "muted", fmtTime(j.created_at)));
      const go = el("td");
      const b = el("button", "btn small secondary", "Open");
      b.onclick = () => openJob(j.id);
      go.appendChild(b); tr.appendChild(go);
      tb.appendChild(tr);
    });
    t.appendChild(tb); jCard.appendChild(t);
  }
  const lCard = el("div", "card");
  lCard.appendChild(el("h2", null, "Newest leads"));
  if (!d.recent_leads.length) {
    lCard.appendChild(el("p", "muted", "Leads you discover or import will appear here."));
  } else {
    const t = el("table"); const tb = el("tbody");
    d.recent_leads.forEach(l => {
      const tr = el("tr");
      tr.appendChild(el("td", null, l.business_name));
      tr.appendChild(el("td", "muted", l.city || "—"));
      const td = el("td"); td.appendChild(scoreCell(l.lead_score)); tr.appendChild(td);
      tb.appendChild(tr);
    });
    t.appendChild(tb); lCard.appendChild(t);
  }
  row.appendChild(jCard); row.appendChild(lCard);
  c.appendChild(row);
}

/* ---------------- new research ---------------- */
const EXAMPLES = [
  "Find independent restaurants in London. Collect names, websites, public emails, phone numbers, addresses and social links. Remove duplicates and export to Excel.",
  "Find boutique hotels in Dubai with websites and phone numbers.",
  "Find dental clinics in Lahore. I need names, addresses and phone numbers.",
  "Find coworking spaces in Berlin with websites.",
];
async function renderNewResearch(c) {
  c.innerHTML = "";
  const card = el("div", "card");
  card.appendChild(el("h2", null, "Describe what you want to research"));
  card.appendChild(el("p", "muted",
    "Write in plain language. GrabResult turns it into a research plan, searches free public sources, and organizes the results."));
  const ta = el("textarea"); ta.id = "reqText";
  ta.placeholder = "e.g. Find independent coffee shops in Manchester with websites and phone numbers…";
  card.appendChild(ta);
  card.appendChild(el("div", null, "Try an example:"));
  const chips = el("div", "example-chips");
  EXAMPLES.forEach(x => {
    const ch = el("button", "chip", x.length > 70 ? x.slice(0, 70) + "…" : x);
    ch.title = x; ch.onclick = () => { ta.value = x; };
    chips.appendChild(ch);
  });
  card.appendChild(chips);

  card.appendChild(el("h3", null, "Optional filters"));
  const grid = el("div", "grid cols-3");
  const fields = [
    ["country", "Country", "text", "e.g. United Kingdom"],
    ["city", "City", "text", "e.g. London"],
    ["industry", "Industry", "text", "e.g. Hospitality"],
    ["category", "Business category", "text", "e.g. restaurant"],
    ["keywords", "Keywords", "text", "e.g. independent, boutique"],
    ["max_records", "Max records", "number", "100"],
  ];
  const inputs = {};
  fields.forEach(([name, lbl, type, ph]) => {
    const w = el("div");
    w.appendChild(el("label", null, lbl));
    const inp = el("input"); inp.type = type; inp.placeholder = ph; inp.id = "f_" + name;
    if (name === "max_records") inp.value = "100";
    w.appendChild(inp); grid.appendChild(w); inputs[name] = inp;
  });
  card.appendChild(grid);
  const checks = [["require_website", "Only keep businesses with a website"],
                  ["require_contact", "Only keep businesses with a public email or phone"],
                  ["inspect_websites", "Inspect business websites for contact info (recommended)"]];
  checks.forEach(([name, lbl]) => {
    const row = el("label", "checkbox-row");
    const cb = el("input"); cb.type = "checkbox"; cb.id = "f_" + name;
    if (name === "inspect_websites") cb.checked = true;
    row.appendChild(cb); row.appendChild(el("span", null, lbl));
    card.appendChild(row); inputs[name] = cb;
  });

  const btnRow = el("div"); btnRow.style.marginTop = "14px";
  const previewBtn = el("button", "btn secondary", "Preview plan");
  const startBtn = el("button", "btn", "Start research");
  startBtn.style.marginLeft = "8px";
  btnRow.appendChild(previewBtn); btnRow.appendChild(startBtn);
  card.appendChild(btnRow);
  const planBox = el("div"); card.appendChild(planBox);
  c.appendChild(card);

  function collectFilters() {
    return {
      country: inputs.country.value.trim(), city: inputs.city.value.trim(),
      industry: inputs.industry.value.trim(), category: inputs.category.value.trim(),
      keywords: inputs.keywords.value.trim(),
      max_records: parseInt(inputs.max_records.value, 10) || 100,
      require_website: inputs.require_website.checked,
      require_contact: inputs.require_contact.checked,
      inspect_websites: inputs.inspect_websites.checked,
    };
  }
  previewBtn.onclick = async () => {
    planBox.innerHTML = "";
    try {
      const r = await api("/api/research/plan", {method: "POST",
        body: JSON.stringify({request_text: ta.value, filters: collectFilters()})});
      planBox.appendChild(renderPlan(r.plan));
    } catch (e) { toast(e.message, true); }
  };
  startBtn.onclick = async () => {
    try {
      startBtn.disabled = true;
      const r = await api("/api/research/start", {method: "POST",
        body: JSON.stringify({request_text: ta.value, filters: collectFilters()})});
      toast("Research started — watch it in Research History.");
      openJob(r.job_id);
    } catch (e) { toast(e.message, true); startBtn.disabled = false; }
  };
}
function renderPlan(plan) {
  const box = el("div", "plan-box");
  box.appendChild(el("h3", null, "Research plan"));
  const dl = el("dl", "kv");
  const rows = [
    ["Objective", plan.objective],
    ["Category", plan.criteria.category || "—"],
    ["Location", [plan.criteria.city, plan.criteria.country].filter(Boolean).join(", ") || "—"],
    ["Sources", plan.sources.join(", ")],
    ["Max records", String(plan.max_records)],
    ["Output fields", plan.output_fields.join(", ")],
  ];
  rows.forEach(([k, v]) => {
    dl.appendChild(el("dt", null, k)); dl.appendChild(el("dd", null, v));
  });
  box.appendChild(dl);
  box.appendChild(el("b", null, "Known limitations:"));
  const ul = el("ul");
  plan.limitations.forEach(l => ul.appendChild(el("li", null, l)));
  box.appendChild(ul);
  return box;
}

/* ---------------- history / job detail ---------------- */
let jobPoll = null;
async function renderHistory(c) {
  c.innerHTML = "";
  if (jobPoll) { clearInterval(jobPoll); jobPoll = null; }
  const card = el("div", "card");
  card.appendChild(el("h2", null, "Research history"));
  const wrap = el("div", "table-wrap");
  const t = el("table");
  const thead = el("thead");
  const hr = el("tr");
  ["Request", "Status", "Progress", "Created", ""].forEach(h => hr.appendChild(el("th", null, h)));
  thead.appendChild(hr); t.appendChild(thead);
  const tb = el("tbody"); t.appendChild(tb); wrap.appendChild(t);
  card.appendChild(wrap); c.appendChild(card);
  async function load() {
    const d = await api("/api/research/jobs?limit=50");
    tb.innerHTML = "";
    if (!d.jobs.length) {
      const tr = el("tr"); const td = el("td", "muted", "No research jobs yet.");
      td.colSpan = 5; tr.appendChild(td); tb.appendChild(tr); return;
    }
    d.jobs.forEach(j => {
      const tr = el("tr");
      tr.appendChild(el("td", null, (j.request_text || "").slice(0, 90)));
      const s = el("td"); s.appendChild(badge(j.status)); tr.appendChild(s);
      const p = el("td");
      const bar = el("div", "progress"); const f = el("div");
      f.style.width = (j.progress || 0) + "%"; bar.appendChild(f); p.appendChild(bar);
      tr.appendChild(p);
      tr.appendChild(el("td", "muted", fmtTime(j.created_at)));
      const go = el("td");
      const b = el("button", "btn small secondary", "Open");
      b.onclick = () => openJob(j.id);
      go.appendChild(b); tr.appendChild(go);
      tb.appendChild(tr);
    });
  }
  await load();
  jobPoll = setInterval(() => { if (currentView === "history") load().catch(() => {}); }, 4000);
}
async function openJob(jobId) {
  if (jobPoll) { clearInterval(jobPoll); jobPoll = null; }
  const c = $("#content"); c.innerHTML = "";
  $("#viewTitle").textContent = "Research job";
  $$("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === "history"));
  currentView = "job";

  const back = el("button", "btn small secondary", "← Back to history");
  back.onclick = () => navigate("history");
  c.appendChild(back);

  const card = el("div", "card"); c.appendChild(card);
  async function load() {
    const d = await api("/api/research/jobs/" + jobId);
    const j = d.job;
    card.innerHTML = "";
    const head = el("div");
    head.appendChild(el("h2", null, "Research job"));
    head.appendChild(el("p", "muted", j.request_text));
    const sRow = el("div");
    sRow.appendChild(badge(j.status));
    sRow.appendChild(el("span", "muted", "  " + (j.progress_message || "")));
    head.appendChild(sRow);
    const bar = el("div", "progress"); const f = el("div");
    f.style.width = (j.progress || 0) + "%"; bar.appendChild(f);
    head.appendChild(bar);
    if (["queued", "running"].includes(j.status)) {
      const cb = el("button", "btn small danger", "Cancel research");
      cb.onclick = async () => {
        try { await api("/api/research/jobs/" + jobId + "/cancel", {method: "POST"}); toast("Cancellation requested."); }
        catch (e) { toast(e.message, true); }
      };
      head.appendChild(cb);
    }
    card.appendChild(head);

    const sum = j.summary || {};
    if (Object.keys(sum).length > 1) {
      card.appendChild(el("h3", null, "Summary (from actual collected data)"));
      const dl = el("dl", "kv");
      [["Records discovered", sum.records_discovered],
       ["With websites", sum.with_websites],
       ["With public emails", sum.with_emails],
       ["With public phones", sum.with_phones],
       ["Duplicates merged", (j.source_log || []).length ? undefined : undefined],
       ["Duration", sum.duration_seconds ? sum.duration_seconds + "s" : "—"],
      ].forEach(([k, v]) => {
        if (v === undefined) return;
        dl.appendChild(el("dt", null, k)); dl.appendChild(el("dd", null, String(v)));
      });
      if (sum.by_status) {
        dl.appendChild(el("dt", null, "By status"));
        dl.appendChild(el("dd", null, Object.entries(sum.by_status).map(([k, v]) => `${k}: ${v}`).join(" · ")));
      }
      if (sum.note) { dl.appendChild(el("dt", null, "Note")); dl.appendChild(el("dd", "muted", sum.note)); }
      card.appendChild(dl);
    }
    if ((j.source_log || []).length) {
      card.appendChild(el("h3", null, "Sources consulted"));
      const t = el("table"); const tb = el("tbody");
      j.source_log.forEach(s => {
        const tr = el("tr");
        tr.appendChild(el("td", null, s.source));
        const td = el("td"); td.appendChild(badge(s.status)); tr.appendChild(td);
        tr.appendChild(el("td", "muted", s.message || ""));
        tb.appendChild(tr);
      });
      t.appendChild(tb);
      const w = el("div", "table-wrap"); w.appendChild(t); card.appendChild(w);
    }
    card.appendChild(el("h3", null, `Leads (${(j.leads || []).length})`));
    if ((j.leads || []).length) {
      card.appendChild(leadTable(j.leads, true));
      const eb = el("button", "btn", "Export these leads to Excel");
      eb.style.marginTop = "10px";
      eb.onclick = async () => {
        try {
          const r = await api("/api/exports", {method: "POST",
            body: JSON.stringify({kind: "xlsx", job_id: jobId})});
          toast(`Excel file ready (${r.rows} rows).`);
          navigate("exports");
        } catch (e) { toast(e.message, true); }
      };
      card.appendChild(eb);
    } else if (j.status === "completed" || j.status === "partial" || j.status === "failed") {
      card.appendChild(el("p", "muted",
        j.status === "failed"
          ? "This research failed: " + (j.error || j.progress_message || "unknown error")
          : "No leads were found. Try a broader category, a larger city, or check the source messages above."));
    }
    return ["completed", "partial", "failed", "cancelled"].includes(j.status);
  }
  await load();
  jobPoll = setInterval(async () => {
    try { if (await load()) { clearInterval(jobPoll); jobPoll = null; } }
    catch (e) { /* keep polling */ }
  }, 3000);
}

/* ---------------- leads ---------------- */
function leadTable(leads, compact) {
  const wrap = el("div", "table-wrap");
  const t = el("table");
  const thead = el("thead"); const hr = el("tr");
  ["Business", "City", "Contact", "Status", "Score", ""].forEach(h => hr.appendChild(el("th", null, h)));
  thead.appendChild(hr); t.appendChild(thead);
  const tb = el("tbody");
  leads.forEach(l => {
    const tr = el("tr");
    const name = el("td");
    name.appendChild(el("b", null, l.business_name || "—"));
    if (l.website && !compact) {
      name.appendChild(el("br"));
      const a = el("a", "muted", l.website); a.href = l.website; a.target = "_blank"; a.rel = "noopener";
      name.appendChild(a);
    }
    tr.appendChild(name);
    tr.appendChild(el("td", "muted", [l.city, l.country].filter(Boolean).join(", ") || "—"));
    const contactBits = [l.email, l.phone].filter(Boolean);
    tr.appendChild(el("td", "muted", contactBits.join(" · ") || "—"));
    const s = el("td"); s.appendChild(badge(l.verification_status)); tr.appendChild(s);
    const sc = el("td"); sc.appendChild(scoreCell(l.lead_score || 0)); tr.appendChild(sc);
    const go = el("td");
    const b = el("button", "btn small secondary", "View");
    b.onclick = () => openLead(l.id);
    go.appendChild(b); tr.appendChild(go);
    tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t);
  return wrap;
}
let leadPage = 0;
async function renderLeads(c) {
  c.innerHTML = "";
  if (jobPoll) { clearInterval(jobPoll); jobPoll = null; }
  const card = el("div", "card");
  card.appendChild(el("h2", null, "Leads database"));
  const bar = el("div", "toolbar");
  const mkField = (lbl, iden, type) => {
    const w = el("div", "field");
    w.appendChild(el("label", null, lbl));
    const i = type === "select" ? el("select") : el("input");
    if (type !== "select") i.type = type || "text";
    i.id = iden; w.appendChild(i); bar.appendChild(w); return i;
  };
  const fSearch = mkField("Search", "lf_search");
  const fStatus = mkField("Status", "lf_status", "select");
  ["", "discovered", "qualified", "verified", "needs_review", "excluded"].forEach(s => {
    const o = el("option", null, s ? s.replace(/_/g, " ") : "All statuses"); o.value = s;
    fStatus.appendChild(o);
  });
  const fCity = mkField("City", "lf_city");
  const fScore = mkField("Min score", "lf_score", "number");
  const goBtn = el("button", "btn", "Filter");
  const goW = el("div", "field"); goW.appendChild(el("label", null, " ")); goW.appendChild(goBtn);
  bar.appendChild(goW);
  card.appendChild(bar);
  const res = el("div"); card.appendChild(res);
  const pager = el("div", "pagination"); card.appendChild(pager);
  c.appendChild(card);

  async function load() {
    const q = new URLSearchParams({limit: 25, offset: leadPage * 25});
    if (fSearch.value) q.set("search", fSearch.value);
    if (fStatus.value) q.set("status", fStatus.value);
    if (fCity.value) q.set("city", fCity.value);
    if (fScore.value) q.set("min_score", fScore.value);
    const d = await api("/api/leads?" + q.toString());
    res.innerHTML = "";
    if (!d.leads.length) {
      res.appendChild(el("div", "empty", ""));
      res.lastChild.appendChild(el("p", null, "No leads match. Run a research job or import a file."));
    } else {
      res.appendChild(el("p", "muted", `${d.total} lead(s) found.`));
      res.appendChild(leadTable(d.leads));
    }
    pager.innerHTML = "";
    const prev = el("button", "btn small secondary", "← Prev");
    prev.disabled = leadPage === 0;
    prev.onclick = () => { leadPage--; load(); };
    const next = el("button", "btn small secondary", "Next →");
    next.disabled = (leadPage + 1) * 25 >= d.total;
    next.onclick = () => { leadPage++; load(); };
    pager.appendChild(prev);
    pager.appendChild(el("span", "muted", `Page ${leadPage + 1}`));
    pager.appendChild(next);
  }
  goBtn.onclick = () => { leadPage = 0; load().catch(e => toast(e.message, true)); };
  await load();
}
async function openLead(leadId) {
  const d = await api("/api/leads/" + leadId);
  const l = d.lead;
  const c = $("#content"); c.innerHTML = "";
  $("#viewTitle").textContent = "Lead detail";
  currentView = "lead";
  const back = el("button", "btn small secondary", "← Back to leads");
  back.onclick = () => navigate("leads");
  c.appendChild(back);
  const card = el("div", "card"); c.appendChild(card);
  const head = el("div");
  head.appendChild(el("h2", null, l.business_name));
  head.appendChild(badge(l.verification_status));
  card.appendChild(head);
  const dl = el("dl", "kv");
  let socials = {}, reasons = [];
  try { socials = JSON.parse(l.socials_json || "{}"); } catch (e) {}
  try { reasons = JSON.parse(l.score_reasons_json || "[]"); } catch (e) {}
  [["Description", l.description], ["Industry", l.industry], ["Category", l.category],
   ["Website", l.website], ["Email", l.email], ["Phone", l.phone],
   ["Address", l.address], ["City", l.city], ["Country", l.country],
   ["Source", l.source_name], ["Source URL", l.source_url],
   ["Discovered", fmtTime(l.discovered_at)],
   ["Confidence", String(l.confidence)],
   ["Lead score", String(l.lead_score)],
   ["Why this score", reasons.join("; ")],
   ["Socials", Object.entries(socials).map(([k, v]) => `${k}: ${v}`).join("; ")],
   ["Notes", l.notes],
  ].forEach(([k, v]) => {
    if (!v) return;
    dl.appendChild(el("dt", null, k)); dl.appendChild(el("dd", null, v));
  });
  card.appendChild(dl);
  card.appendChild(el("h3", null, "Update this lead"));
  const sRow = el("div", "toolbar");
  const sel = el("select");
  ["discovered", "qualified", "verified", "needs_review", "excluded"].forEach(s => {
    const o = el("option", null, s.replace(/_/g, " ")); o.value = s;
    if (s === l.verification_status) o.selected = true;
    sel.appendChild(o);
  });
  const noteInp = el("input"); noteInp.type = "text"; noteInp.placeholder = "Add a note…";
  noteInp.value = l.notes || "";
  const save = el("button", "btn small", "Save");
  const del = el("button", "btn small danger", "Delete");
  sRow.appendChild(sel); sRow.appendChild(noteInp); sRow.appendChild(save); sRow.appendChild(del);
  card.appendChild(sRow);
  save.onclick = async () => {
    try {
      await api("/api/leads/" + leadId, {method: "PATCH",
        body: JSON.stringify({verification_status: sel.value, notes: noteInp.value})});
      toast("Lead updated."); openLead(leadId);
    } catch (e) { toast(e.message, true); }
  };
  del.onclick = async () => {
    if (!confirm("Delete this lead?")) return;
    try { await api("/api/leads/" + leadId, {method: "DELETE"}); toast("Lead deleted."); navigate("leads"); }
    catch (e) { toast(e.message, true); }
  };
}

/* ---------------- imports ---------------- */
async function renderImports(c) {
  c.innerHTML = "";
  const up = el("div", "card");
  up.appendChild(el("h2", null, "Import a file"));
  up.appendChild(el("p", "muted",
    "Upload a CSV or Excel file (.csv, .xlsx, max 10 MB). Map your columns, preview what will be added, then confirm. Existing leads are never deleted or overwritten."));
  const fileInp = el("input"); fileInp.type = "file"; fileInp.accept = ".csv,.xlsx,.xlsm";
  up.appendChild(fileInp);
  const upBtn = el("button", "btn", "Upload & analyze");
  upBtn.style.marginTop = "10px";
  up.appendChild(upBtn);
  const stage = el("div"); up.appendChild(stage);
  c.appendChild(up);

  const hist = el("div", "card");
  hist.appendChild(el("h2", null, "Import history"));
  const d = await api("/api/imports");
  if (!d.imports.length) hist.appendChild(el("p", "muted", "No imports yet."));
  else {
    const t = el("table"); const tb = el("tbody");
    d.imports.forEach(i => {
      const tr = el("tr");
      tr.appendChild(el("td", null, i.filename));
      tr.appendChild(el("td", "muted", `${i.rows_imported} added · ${i.rows_skipped} skipped`));
      tr.appendChild(el("td", "muted", fmtTime(i.created_at)));
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    const w = el("div", "table-wrap"); w.appendChild(t); hist.appendChild(w);
  }
  c.appendChild(hist);

  let uploadPath = null, headers = [], suggested = {}, availableFields = [];
  upBtn.onclick = async () => {
    if (!fileInp.files.length) { toast("Choose a file first.", true); return; }
    stage.innerHTML = ""; stage.appendChild(el("p", "muted", "Uploading and analyzing…"));
    const fd = new FormData(); fd.append("file", fileInp.files[0]);
    try {
      const r = await fetch("/api/imports/upload", {method: "POST", body: fd});
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || "Upload failed");
      uploadPath = data.upload_path; headers = data.headers;
      suggested = data.suggested_mapping; availableFields = data.available_fields;
      renderMapping(stage, data);
    } catch (e) { stage.innerHTML = ""; toast(e.message, true); }
  };

  function renderMapping(stage, data) {
    stage.innerHTML = "";
    stage.appendChild(el("h3", null, `Map columns (${data.row_count} rows found)`));
    const t = el("table"); const tb = el("tbody");
    const selects = {};
    headers.forEach(h => {
      const tr = el("tr");
      tr.appendChild(el("td", null, h || "(empty header)"));
      const td = el("td");
      const sel = el("select");
      const none = el("option", null, "— ignore —"); none.value = "";
      sel.appendChild(none);
      availableFields.forEach(f => {
        const o = el("option", null, f); o.value = f;
        if (suggested[h] === f) o.selected = true;
        sel.appendChild(o);
      });
      td.appendChild(sel); tr.appendChild(td); tb.appendChild(tr);
      selects[h] = sel;
    });
    t.appendChild(tb);
    const w = el("div", "table-wrap"); w.appendChild(t); stage.appendChild(w);
    const pvBtn = el("button", "btn secondary", "Preview cleaning & merge");
    pvBtn.style.marginTop = "10px";
    stage.appendChild(pvBtn);
    const pv = el("div"); stage.appendChild(pv);
    pvBtn.onclick = async () => {
      const mapping = {};
      Object.entries(selects).forEach(([h, sel]) => { if (sel.value) mapping[h] = sel.value; });
      if (!mapping || !Object.values(mapping).includes("business_name")) {
        toast("Map at least the business name column.", true); return;
      }
      pv.innerHTML = ""; pv.appendChild(el("p", "muted", "Analyzing…"));
      try {
        const r = await api("/api/imports/preview", {method: "POST",
          body: JSON.stringify({upload_path: uploadPath, mapping})});
        pv.innerHTML = "";
        pv.appendChild(el("h3", null, "Preview"));
        const dl = el("dl", "kv");
        dl.appendChild(el("dt", null, "Clean rows ready")); dl.appendChild(el("dd", null, String(r.clean_count)));
        dl.appendChild(el("dt", null, "New leads")); dl.appendChild(el("dd", null, String(r.merge_preview.new_count)));
        dl.appendChild(el("dt", null, "Already in database")); dl.appendChild(el("dd", null, String(r.merge_preview.existing_count)));
        dl.appendChild(el("dt", null, "Skipped rows")); dl.appendChild(el("dd", null, String(r.skipped)));
        pv.appendChild(dl);
        if (r.issues.length) {
          pv.appendChild(el("b", null, "Issues:"));
          const ul = el("ul", "muted");
          r.issues.forEach(i => ul.appendChild(el("li", null, i)));
          pv.appendChild(ul);
        }
        if (r.sample.length) {
          pv.appendChild(el("b", null, "Sample cleaned rows:"));
          const st = el("table"); const stb = el("tbody");
          r.sample.forEach(sr => {
            const tr = el("tr");
            tr.appendChild(el("td", null, sr.business_name || ""));
            tr.appendChild(el("td", "muted", sr.city || ""));
            tr.appendChild(el("td", "muted", sr.email || sr.phone || ""));
            stb.appendChild(tr);
          });
          st.appendChild(stb);
          const sw = el("div", "table-wrap"); sw.appendChild(st); pv.appendChild(sw);
        }
        const cfBtn = el("button", "btn", `Confirm import (${r.merge_preview.new_count} new)`);
        cfBtn.style.marginTop = "10px";
        cfBtn.onclick = async () => {
          try {
            const rr = await api("/api/imports/confirm", {method: "POST",
              body: JSON.stringify({upload_path: uploadPath, mapping})});
            toast(`Imported ${rr.imported} leads (${rr.skipped} skipped).`);
            navigate("imports");
          } catch (e) { toast(e.message, true); }
        };
        pv.appendChild(cfBtn);
      } catch (e) { pv.innerHTML = ""; toast(e.message, true); }
    };
  }
}

/* ---------------- exports ---------------- */
async function renderExports(c) {
  c.innerHTML = "";
  const card = el("div", "card");
  card.appendChild(el("h2", null, "Create an export"));
  card.appendChild(el("p", "muted",
    "Exports include: All Results, Qualified Leads, Needs Review, per-country/city sheets, Sources & Evidence, and a Research Summary sheet."));
  const row = el("div", "toolbar");
  const kindSel = el("select");
  [["xlsx", "Excel (.xlsx)"], ["csv", "CSV (.csv)"]].forEach(([v, lbl]) => {
    const o = el("option", null, lbl); o.value = v; kindSel.appendChild(o);
  });
  const scopeSel = el("select");
  const so = el("option", null, "Whole leads database"); so.value = "";
  scopeSel.appendChild(so);
  const jobs = await api("/api/research/jobs?limit=50");
  jobs.jobs.forEach(j => {
    const o = el("option", null, `Job: ${(j.request_text || "").slice(0, 50)} (${j.status})`);
    o.value = j.id; scopeSel.appendChild(o);
  });
  const go = el("button", "btn", "Generate file");
  row.appendChild(kindSel); row.appendChild(scopeSel); row.appendChild(go);
  card.appendChild(row);
  c.appendChild(card);

  const list = el("div", "card");
  list.appendChild(el("h2", null, "Export files"));
  const wrap = el("div"); list.appendChild(wrap); c.appendChild(list);
  async function load() {
    const d = await api("/api/exports");
    wrap.innerHTML = "";
    if (!d.exports.length) { wrap.appendChild(el("p", "muted", "No exports yet.")); return; }
    const t = el("table"); const tb = el("tbody");
    d.exports.forEach(x => {
      const tr = el("tr");
      tr.appendChild(el("td", null, x.filename));
      tr.appendChild(el("td", "muted", `${x.rows} rows · ${(x.size_bytes / 1024).toFixed(1)} KB`));
      tr.appendChild(el("td", "muted", fmtTime(x.created_at)));
      const td = el("td");
      const a = el("a", "btn small", "Download");
      a.href = "/api/exports/" + x.id + "/download";
      td.appendChild(a); tr.appendChild(td);
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    const w = el("div", "table-wrap"); w.appendChild(t); wrap.appendChild(w);
  }
  go.onclick = async () => {
    try {
      const r = await api("/api/exports", {method: "POST",
        body: JSON.stringify({kind: kindSel.value, job_id: scopeSel.value || null})});
      toast(`Export ready: ${r.filename} (${r.rows} rows).`);
      await load();
    } catch (e) { toast(e.message, true); }
  };
  await load();
}

/* ---------------- settings ---------------- */
async function renderSettings(c) {
  c.innerHTML = "";
  const s = await api("/api/settings");
  const card = el("div", "card");
  card.appendChild(el("h2", null, "Research settings"));
  const grid = el("div", "grid cols-3");
  const mk = (lbl, iden, val) => {
    const w = el("div");
    w.appendChild(el("label", null, lbl));
    const i = el("input"); i.type = "number"; i.id = iden; i.value = val;
    w.appendChild(i); grid.appendChild(w); return i;
  };
  const fMax = mk("Default max records per job", "s_max", s.settings.max_records_default);
  const fWeb = mk("Max websites inspected per job", "s_web", s.settings.max_website_inspect);
  card.appendChild(grid);
  const sv = el("button", "btn", "Save settings");
  sv.style.marginTop = "12px";
  sv.onclick = async () => {
    try {
      await api("/api/settings", {method: "POST", body: JSON.stringify({
        max_records_default: fMax.value, max_website_inspect: fWeb.value,
      })});
      toast("Settings saved.");
    } catch (e) { toast(e.message, true); }
  };
  card.appendChild(sv);
  c.appendChild(card);

  const src = el("div", "card");
  src.appendChild(el("h2", null, "Source registry"));
  src.appendChild(el("p", "muted",
    "Every source GrabResult can use, what it needs, and whether it is currently reachable. Sources that need paid keys are never required."));
  const d = await api("/api/sources");
  const t = el("table"); const tb = el("tbody");
  const thead = el("thead"); const hr = el("tr");
  ["Source", "Type", "Needs", "Status", "Provides", "Limits"].forEach(h => hr.appendChild(el("th", null, h)));
  thead.appendChild(hr); t.appendChild(thead);
  if (!d.sources.length) {
    const tr = el("tr"); const td = el("td", "muted", "No sources checked yet — run a research job first.");
    td.colSpan = 6; tr.appendChild(td); tb.appendChild(tr);
  }
  d.sources.forEach(x => {
    const tr = el("tr");
    tr.appendChild(el("td", null, x.name));
    tr.appendChild(el("td", "muted", x.kind || "—"));
    tr.appendChild(el("td", "muted", (x.auth_required || "none").replace(/_/g, " ")));
    const st = el("td"); st.appendChild(badge(x.status === "available" ? "completed" : x.status === "error" ? "failed" : "discovered")); st.firstChild.textContent = x.status;
    tr.appendChild(st);
    let fields = [];
    try { fields = JSON.parse(x.fields_json || "[]"); } catch (e) {}
    tr.appendChild(el("td", "muted", fields.slice(0, 5).join(", ") + (fields.length > 5 ? "…" : "")));
    tr.appendChild(el("td", "muted", (x.limitations || "").slice(0, 120)));
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  const w = el("div", "table-wrap"); w.appendChild(t); src.appendChild(w);
  c.appendChild(src);

  const dz = el("div", "card");
  dz.appendChild(el("h2", null, "Danger zone"));
  dz.appendChild(el("p", "muted", "Delete all leads, jobs, imports and exports. This cannot be undone."));
  const del = el("button", "btn danger", "Delete all data");
  del.onclick = async () => {
    if (!confirm("Delete ALL data? This cannot be undone.")) return;
    try { await api("/api/data/clear", {method: "POST"}); toast("All data deleted."); navigate("dashboard"); }
    catch (e) { toast(e.message, true); }
  };
  dz.appendChild(del);
  c.appendChild(dz);
}

/* ---------------- help ---------------- */
async function renderHelp(c) {
  c.innerHTML = "";
  const card = el("div", "card");
  card.appendChild(el("h2", null, "How GrabResult works"));
  const items = [
    ["1. Describe your research", "On New Research, write what you need in plain language and set optional filters (country, city, category, max records)."],
    ["2. Review the plan", "GrabResult converts your request into a research plan: objective, criteria, sources, output fields and known limitations."],
    ["3. Sources are searched", "Free public sources are queried — OpenStreetMap business data, geocoding, and the businesses' own public websites. Each source reports success or failure honestly."],
    ["4. Data is cleaned", "Names, URLs, emails and phones are normalized; duplicates are merged (same website, or same name + city/phone — never on similar names alone)."],
    ["5. Leads are scored & assessed", "A transparent 0–100 score explains itself rule by rule. Quality statuses: Discovered, Qualified, Verified, Needs Review, Duplicate, Excluded. A high score never means 'verified'."],
    ["6. Export", "Download real Excel (.xlsx, multi-sheet) or CSV files from the Exports page or any finished job."],
    ["Imports", "Upload your own CSV/Excel files. Columns are mapped, rows validated and de-duplicated against your database, and you preview everything before confirming. Nothing existing is ever deleted."],
    ["Honesty rules", "GrabResult never invents data. Missing values stay empty, failed sources say so, and summaries count only real collected records."],
  ];
  items.forEach(([t, dsc]) => {
    card.appendChild(el("h3", null, t));
    card.appendChild(el("p", "muted", dsc));
  });
  card.appendChild(el("h3", null, "Status meanings"));
  const dl = el("dl", "kv");
  const desc = {
    discovered: "Found by a source. Not yet assessed.",
    qualified: "Matches your criteria and has usable public contact info.",
    verified: "Key fields confirmed by you or a trusted import.",
    needs_review: "Thin or conflicting data — check before outreach.",
    duplicate: "Merged into another record (audit only).",
    excluded: "Did not pass your filters.",
  };
  Object.entries(desc).forEach(([k, v]) => {
    dl.appendChild(el("dt", null, k.replace(/_/g, " "))); dl.appendChild(el("dd", null, v));
  });
  card.appendChild(dl);
  c.appendChild(card);
}

/* ---------------- boot ---------------- */
(async function boot() {
  try {
    await api("/api/health");
  } catch (e) {
    $("#apiStatus").textContent = "Offline";
    $(".dot").classList.remove("ok"); $(".dot").classList.add("bad");
    toast("Cannot reach the GrabResult server.", true);
  }
  navigate("dashboard");
})();
