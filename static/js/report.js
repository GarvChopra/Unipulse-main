(() => {
  const wiz = document.getElementById("wiz");
  const picker = JSON.parse(wiz.dataset.picker);   // {campus, nodes:[{id,name,type,bucket,room_type,children}]}
  const S = { photo_b64: null, photo_mime: "image/jpeg",
             location_id: null, room: null, sub_zone: null, path: [],
             category: "", description: "",
             noticed_at: null, affects_academics: false, ai: null };
  let stream = null;
  const $ = (id) => document.getElementById(id);
  const STEP_OF = { photo: 1, loc: 2, review: 3, done: 3 };
  const TITLE = { photo: "Report an Issue", loc: "Report an Issue",
                  review: "Review & Submit", done: "Submitted" };

  function show(name, fromPop) {
    // Push a history entry per wizard step so the Android hardware back button
    // (and the browser back button) walks Photo → Details → Review instead of
    // leaving the report screen.
    if (!fromPop) {
      try { history.pushState({ wizStep: name }, ""); } catch (e) { /* noop */ }
    }
    document.querySelectorAll(".wstep").forEach((el) =>
      el.classList.toggle("active", el.dataset.step === name));
    $("wtitle").textContent = TITLE[name];
    const s = STEP_OF[name];
    document.querySelectorAll("#stepper .st").forEach((st) => {
      const n = +st.dataset.s;
      st.classList.toggle("active", n === s);
      st.classList.toggle("done", n < s);
    });
    document.querySelectorAll("#stepper .line").forEach((ln, i) =>
      ln.classList.toggle("done", i < s - 1));
    window.scrollTo(0, 0);
  }

  // ---- 1. camera / photo ----
  function stopCam() {
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  }
  const MAX_EDGE = 1600;
  // Shrink a captured/picked photo in the browser before upload: keeps the
  // request well under the server's 16 MB cap and the stored row small. The
  // server downscales again authoritatively.
  function downscale(dataUrl, mime, done) {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height));
      if (scale === 1 && dataUrl.length < 1_400_000) { done(dataUrl, mime); return; }
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * scale);
      c.height = Math.round(img.height * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      done(c.toDataURL("image/jpeg", 0.82), "image/jpeg");
    };
    img.onerror = () => done(dataUrl, mime);
    img.src = dataUrl;
  }

  function useImage(dataUrl, mime) {
    downscale(dataUrl, mime, (url, m) => {
      S.photo_b64 = url.split(",")[1];
      S.photo_mime = m || "image/jpeg";
      $("preview").src = url; $("preview2").src = url;
      stopCam();
      $("camlaunch").hidden = true; $("camwrap").hidden = true;
      $("captured").hidden = false;
    });
  }
  $("startcam").addEventListener("click", async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      $("camlaunch").hidden = true; $("camwrap").hidden = false;
      const v = $("cam"); v.srcObject = stream; await v.play();
    } catch (e) { $("photo").click(); }   // fallback: OS camera / file picker
  });
  $("snap").addEventListener("click", () => {
    const v = $("cam"), c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    useImage(c.toDataURL("image/jpeg", 0.85), "image/jpeg");
  });
  $("pick").addEventListener("click", () => $("photo").click());
  $("photo").addEventListener("change", (e) => {
    const f = e.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = () => useImage(r.result, f.type || "image/jpeg");
    r.readAsDataURL(f);
  });
  $("retake").addEventListener("click", () => {
    S.photo_b64 = null;
    $("captured").hidden = true; $("camwrap").hidden = true; $("camlaunch").hidden = false;
  });
  $("to-details").addEventListener("click", () => {
    if (!S.photo_b64) return alert("Please add a photo first.");
    show("loc");
  });
  // photo is optional — let the reporter skip straight to the form
  $("skip-photo").addEventListener("click", () => {
    S.photo_b64 = null; S.photo_mime = "image/jpeg";
    stopCam();
    show("loc");
  });

  // ---- 2. location — cascading picker driven by the campus tree ----
  const drill = $("drill");
  const FREE = "__free__";

  function selectEl(label, opts, onChange, { free = false, freeLabel = "" } = {}) {
    const wrap = document.createElement("div");
    wrap.className = "loc-level";
    wrap.innerHTML = `<label>${label}</label>`;
    const sel = document.createElement("select");
    sel.innerHTML = `<option value="">Select…</option>` +
      opts.map((o) => `<option value="${o.id}">${o.name}${o.room_type ? " · " + o.room_type : ""}</option>`).join("") +
      (free ? `<option value="${FREE}">${freeLabel}</option>` : "");
    sel.addEventListener("change", () => onChange(sel.value));
    wrap.appendChild(sel);
    drill.appendChild(wrap);
    return wrap;
  }

  function freeText(label, placeholder, onInput) {
    const wrap = document.createElement("div");
    wrap.className = "loc-level";
    wrap.innerHTML = `<label>${label}</label>`;
    const inp = document.createElement("input");
    inp.placeholder = placeholder;
    inp.addEventListener("input", () => onInput(inp.value.trim() || null));
    wrap.appendChild(inp);
    drill.appendChild(wrap);
  }

  // clear every level after `keepCount`
  function trimLevels(keepCount) {
    [...drill.children].slice(keepCount).forEach((el) => el.remove());
  }

  function commit(node, freeRoom = null, freeArea = null) {
    S.location_id = node ? node.id : null;
    S.room = freeRoom;
    S.sub_zone = freeArea;
    S.path = [];
    // rebuild the readable path from the selects currently shown
  }

  function renderLevel(level, nodes, ctxLabel) {
    // level = index in drill; nodes = options to choose among
    const labels = { building: "Floor", floor: "Room", facility: "Specific area",
                     zone: "Sub-zone" };
    const parentType = ctxLabel;
    const label = labels[parentType] || "Area";
    const isRoomLevel = parentType === "building" ? false : parentType === "floor";
    const allowFree = parentType === "floor" || parentType === "facility";
    const freeLabel = parentType === "floor" ? "— Room not in the list —"
                                             : "— Other area (type it) —";

    selectEl(label, nodes, (val) => {
      trimLevels(level + 1);
      S.room = S.sub_zone = null;
      if (!val) { commit(currentDeepest(level)); return; }
      if (val === FREE) {
        commit(currentDeepest(level));
        if (parentType === "floor")
          freeText("Room number / name", "e.g. 204 or Lab-3", (v) => { S.room = v; });
        else
          freeText("Specific area", "e.g. kitchen, counter, washroom", (v) => { S.sub_zone = v; });
        return;
      }
      const node = nodes.find((n) => String(n.id) === val);
      commit(node);
      if (node.children && node.children.length) {
        renderLevel(level + 1, node.children, node.type);
      } else if (node.type === "floor") {
        // catalogued floor with no rooms yet
        freeText("Room number / name", "e.g. 204 or Lab-3", (v) => { S.room = v; });
      } else if (node.type === "facility" || node.type === "zone") {
        freeText("Specific area (optional)", "e.g. kitchen, counter", (v) => { S.sub_zone = v; });
      }
    }, { free: allowFree, freeLabel });
  }

  // the deepest fully-selected node above `level` (its <select>'s value)
  function currentDeepest(level) {
    for (let i = Math.min(level, drill.children.length) - 1; i >= 0; i--) {
      const sel = drill.children[i].querySelector("select");
      if (sel && sel.value && sel.value !== FREE) {
        return findNodeById(+sel.value);
      }
    }
    return null;
  }
  function findNodeById(id, list = picker.nodes) {
    for (const n of list) {
      if (n.id === id) return n;
      const hit = n.children && findNodeById(id, n.children);
      if (hit) return hit;
    }
    return null;
  }

  // top level
  selectEl("Building / Facility", picker.nodes, (val) => {
    trimLevels(1);
    S.location_id = S.room = S.sub_zone = null;
    if (!val || val === FREE) return;
    const node = picker.nodes.find((n) => String(n.id) === val);
    commit(node);
    if (node.children && node.children.length) {
      renderLevel(1, node.children, node.type);
    } else if (node.type === "facility" || node.type === "zone") {
      freeText("Specific area (optional)", "e.g. kitchen, counter, washroom", (v) => { S.sub_zone = v; });
    }
  });

  function readablePath() {
    const parts = [];
    [...drill.children].forEach((lvl) => {
      const sel = lvl.querySelector("select");
      const inp = lvl.querySelector("input");
      if (sel && sel.selectedIndex > 0 && sel.value !== FREE)
        parts.push(sel.options[sel.selectedIndex].textContent.split(" · ")[0]);
      if (inp && inp.value.trim()) parts.push(inp.value.trim());
    });
    return parts.join(" → ");
  }

  $("cat").addEventListener("change", (e) => (S.category = e.target.value));
  $("desc").addEventListener("input", (e) => {
    S.description = e.target.value;
    $("cc").textContent = e.target.value.length;
  });
  $("back-edit").addEventListener("click", () => show("loc"));
  $("to-review").addEventListener("click", async () => {
    S.description = $("desc").value.trim();
    if (!S.location_id) return alert("Pick where the issue is.");
    const topSel = drill.children[0] && drill.children[0].querySelector("select");
    const topNode = topSel && picker.nodes.find((n) => String(n.id) === topSel.value);
    if (topNode && topNode.type === "building" && !S.room &&
        !(findNodeById(S.location_id) || {}).room_type)
      return alert("Pick the floor and room (or type the room number).");
    if (S.description.length < 10) return alert("Describe what happened (min 10 characters).");

    const nv = $("noticed").value;
    S.noticed_at = nv ? new Date(nv).getTime() / 1000 : null;
    S.affects_academics = $("affects").checked;

    $("r-loc").textContent = readablePath() || "—";
    $("r-cat").textContent = S.category || "Auto-detect";
    $("r-pri").textContent = "Detecting…";
    $("r-desc").textContent = S.description;
    if (nv) $("r-when").textContent = new Date(nv).toLocaleString();
    $("preview2").hidden = !S.photo_b64;
    show("review");

    try {
      const a = await (await fetch("/report/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: S.description, photo_b64: S.photo_b64,
                               photo_mime: S.photo_mime }),
      })).json();
      S.ai = a;
      if (!S.category && a.category) $("r-cat").textContent = a.category + " (auto)";
      if (a.severity)
        $("r-pri").innerHTML = `<span class="badge-pri ${a.severity}">${a.severity}</span> (AI-detected)`;
      else
        $("r-pri").textContent = "Decided by AI on submit";
    } catch (e) {
      S.ai = null;
      $("r-pri").textContent = "Decided by AI on submit";
    }
  });

  // ---- submit ----
  $("submit").addEventListener("click", async () => {
    const btn = $("submit"); btn.disabled = true; btn.textContent = "Submitting…";
    try {
      const res = await fetch("/report", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description: S.description, location_id: S.location_id,
          room: S.room, sub_zone: S.sub_zone,
          photo_b64: S.photo_b64, photo_mime: S.photo_mime,
          category: S.category || null,
          noticed_at: S.noticed_at, affects_academics: S.affects_academics, ai: S.ai,
        }),
      });
      const out = await res.json();
      if (!res.ok) { alert((out.errors || ["Something went wrong"]).join("\n"));
        btn.disabled = false; btn.textContent = "Submit Report"; return; }
      $("done-code").textContent = out.code;
      $("done-recurring").textContent = out.recurring
        ? `Related to ${out.recurring.report_count - 1} other report(s) — the admin sees them as one recurring issue.`
        : "";
      show("done");
    } catch (e) {
      alert("Network error — please try again.");
      btn.disabled = false; btn.textContent = "Submit Report";
    }
  });

  $("wback").addEventListener("click", () => history.back());
  window.addEventListener("popstate", (e) => {
    const step = (e.state && e.state.wizStep) || "photo";
    show(step, true);
  });
  try { history.replaceState({ wizStep: "photo" }, ""); } catch (e) { /* noop */ }
})();
