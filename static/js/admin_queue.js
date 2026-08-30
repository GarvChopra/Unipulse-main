(() => {
  const ids = ["f-status", "f-category", "f-unit", "f-loc", "f-search", "f-sort"];
  const v = (id) => document.getElementById(id).value;
  const q = () => {
    const p = new URLSearchParams();
    if (v("f-status")) p.set("status", v("f-status"));
    if (v("f-category")) p.set("category", v("f-category"));
    if (v("f-unit")) p.set("unit", v("f-unit"));
    if (v("f-loc")) p.set("location_type", v("f-loc"));
    if (v("f-search")) p.set("search", v("f-search"));
    p.set("sort", v("f-sort"));
    return p.toString();
  };
  const sevOf = (r) => (r.priority_score >= 60 ? "high" : r.priority_score >= 35 ? "medium" : "low");
  const load = async () => {
    const box = document.getElementById("rows");
    box.innerHTML = `<p class="a-sub">Loading…</p>`;
    const { rows } = await (await fetch("/admin/grievances/data?" + q())).json();
    if (!rows.length) { box.innerHTML = `<p class="a-sub">No grievances match.</p>`; return; }
    box.innerHTML = rows.map((r) => {
      const href = r.is_group ? `/admin/recurring` : `/admin/grievances/${r.code}`;
      const sev = sevOf(r);
      return `<a class="g-card" href="${href}">
        <div class="accent ${sev}"></div>
        <div class="body">
          <div class="code">${r.is_group ? "RECURRING · " + r.report_count + " reports" : r.code}</div>
          <div class="cat">${r.category || "Unclassified"}</div>
          <div class="meta">${r.location_label}</div>
          <div class="desc">${r.title || ""}</div>
        </div>
        <div class="side">
          <span class="chip ${r.status}">${r.status.replace("_", " ")}</span>
          <span class="badge-pri ${sev}">${sev}</span>
          ${r.overdue ? `<span class="tiny" style="color:var(--alert);font-weight:800">Overdue</span>` : ""}
        </div>
      </a>`;
    }).join("");
  };
  ids.forEach((id) => document.getElementById(id).addEventListener("input", load));
  load();
})();
