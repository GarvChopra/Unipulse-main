(() => {
  const wiz = document.getElementById("wiz");
  const picker = JSON.parse(wiz.dataset.picker);
  const S = { photo_b64: null, photo_mime: "image/jpeg", type: null, block_no: null,
             floor: null, room: null, sub_zone: null, category: "", description: "",
             severity: null, noticed_at: null, affects_academics: false, ai: null };
  let stream = null;
  const $ = (id) => document.getElementById(id);
  const STEP_OF = { photo: 1, loc: 2, review: 3, done: 3 };
  const TITLE = { photo: "Report an Issue", loc: "Report an Issue",
                  review: "Review & Submit", done: "Submitted" };

  function show(name) {
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
  function useImage(dataUrl, mime) {
    S.photo_b64 = dataUrl.split(",")[1];
    S.photo_mime = mime || "image/jpeg";
    $("preview").src = dataUrl; $("preview2").src = dataUrl;
    stopCam();
    $("camlaunch").hidden = true; $("camwrap").hidden = true;
    $("captured").hidden = false;
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

  // ---- 2. details ----
  const tp = $("type-pills");
  picker.types.forEach((t) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "pill"; b.textContent = t.name; b.dataset.key = t.key;
    b.onclick = () => {
      tp.querySelectorAll(".pill").forEach((p) => p.classList.remove("sel"));
      b.classList.add("sel");
      S.type = t.key; S.block_no = S.floor = S.room = S.sub_zone = null;
      drill(t);
    };
    tp.appendChild(b);
  });
  function sel(label, opts, on) {
    const w = document.createElement("div");
    w.innerHTML = `<label>${label}</label>`;
    const s = document.createElement("select");
    s.innerHTML = `<option value="">Select…</option>` + opts.map((o) => `<option>${o}</option>`).join("");
    s.onchange = () => on(s.value || null);
    w.appendChild(s); return w;
  }
  function drill(t) {
    const d = $("drill"); d.innerHTML = "";
    if (t.key === "academics_block") {
      d.appendChild(sel("Block / Building", picker.academics_blocks, (v) => (S.block_no = v)));
      d.appendChild(sel("Floor", picker.academics_floors, (v) => (S.floor = v)));
      const rm = document.createElement("div");
      rm.innerHTML = `<label>Room Number / Area</label><input id="rm" placeholder="e.g. 204">`;
      rm.querySelector("input").oninput = (e) => (S.room = e.target.value.trim() || null);
      d.appendChild(rm);
    } else if (t.key === "outer_area") {
      d.appendChild(sel("Sub-zone", picker.outer_area_subzones, (v) => (S.sub_zone = v)));
    }
  }
  $("cat").addEventListener("change", (e) => (S.category = e.target.value));
  $("pri").querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      $("pri").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      S.severity = b.dataset.v;
    };
  });
  $("desc").addEventListener("input", (e) => {
    S.description = e.target.value;
    $("cc").textContent = e.target.value.length;
  });
  $("back-edit").addEventListener("click", () => show("loc"));
  $("to-review").addEventListener("click", async () => {
    S.description = $("desc").value.trim();
    if (!S.type) return alert("Pick a location type.");
    if (S.type === "academics_block" && !S.block_no) return alert("Pick a block / building.");
    if (S.type === "academics_block" && !S.room) return alert("Enter the room number / area.");
    if (S.type === "outer_area" && !S.sub_zone) return alert("Pick a sub-zone.");
    if (!S.severity) return alert("Pick a priority.");
    if (S.description.length < 10) return alert("Describe what happened (min 10 characters).");

    const nv = $("noticed").value;
    S.noticed_at = nv ? new Date(nv).getTime() / 1000 : null;
    S.affects_academics = $("affects").checked;

    $("r-block").textContent = S.block_no || (S.sub_zone ? "Outer Area" : "—");
    $("r-floor").textContent = S.floor || "—";
    $("r-room").textContent = S.room || S.sub_zone ||
      picker.types.find((t) => t.key === S.type).name;
    $("r-cat").textContent = S.category || "Auto-detect";
    $("r-pri").innerHTML = `<span class="badge-pri ${S.severity}">${S.severity}</span>`;
    $("r-desc").textContent = S.description;
    if (nv) $("r-when").textContent = new Date(nv).toLocaleString();
    show("review");

    try {
      const a = await (await fetch("/report/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: S.description, photo_b64: S.photo_b64,
                               photo_mime: S.photo_mime }),
      })).json();
      S.ai = a;
      if (!S.category && a.category) $("r-cat").textContent = a.category + " (auto)";
    } catch (e) { S.ai = null; }
  });

  // ---- submit ----
  $("submit").addEventListener("click", async () => {
    const btn = $("submit"); btn.disabled = true; btn.textContent = "Submitting…";
    try {
      const res = await fetch("/report", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description: S.description, location_type: S.type, block_no: S.block_no,
          floor: S.floor, room: S.room, sub_zone: S.sub_zone, photo_b64: S.photo_b64,
          photo_mime: S.photo_mime, category: S.category || null, severity: S.severity,
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

  $("wback").addEventListener("click", () => {
    const cur = document.querySelector(".wstep.active").dataset.step;
    const prev = { loc: "photo", review: "loc" }[cur];
    if (prev) show(prev); else location.href = "/";
  });
})();
