<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>THENA — Mini UI</title>
  <style>
    :root { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; }
    body { margin: 0; background: #0f1115; color: #e8e8e8; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 6px; font-size: 28px; }
    .sub { opacity: .75; margin-bottom: 18px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { background: #161a22; border: 1px solid #23283a; border-radius: 14px; padding: 14px; }
    .row { display:flex; gap:10px; }
    input, textarea, button, select {
      width: 100%; box-sizing: border-box;
      padding: 10px 12px; border-radius: 10px;
      border: 1px solid #2a3150; background: #0f1115; color: #e8e8e8;
      outline: none;
    }
    textarea { min-height: 90px; resize: vertical; }
    button { cursor: pointer; border: 1px solid #3a4370; background: #1b2140; }
    button:hover { filter: brightness(1.1); }
    .btn-red { background:#3a1116; border-color:#6b1b27; }
    .btn-red:hover { filter: brightness(1.08); }
    .muted { opacity:.7; font-size: 13px; }
    .pill { display:inline-block; padding: 3px 9px; border-radius:999px; border:1px solid #2a3150; font-size:12px; opacity:.9; }
    .cards { display:grid; grid-template-columns: 1fr; gap: 12px; }
    .est-head { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
    .est-title { font-weight:700; font-size:16px; }
    .est-meta { opacity:.8; font-size:13px; margin-top:3px; }
    .stars { font-weight:700; }
    .reviews { margin-top:10px; border-top:1px solid #23283a; padding-top:10px; display:grid; gap:8px; }
    .rev { background:#0f1115; border:1px solid #23283a; border-radius: 12px; padding: 10px; }
    .rev-top { display:flex; justify-content:space-between; gap:10px; }
    .tagline { margin-top:6px; display:flex; flex-wrap:wrap; gap:6px; }
    details { margin-top:12px; }
    pre { background:#0b0d12; border:1px solid #23283a; border-radius: 12px; padding: 10px; overflow:auto; }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>THENA — Mini UI</h1>
    <div class="sub">Si ça affiche et que les actions marchent, ça veut dire : <b>UI → API → DB</b> OK.</div>

    <div class="grid">
      <div class="card">
        <h3 style="margin-top:0">Créer un établissement</h3>
        <div class="row">
          <input id="c_name" placeholder="Nom" />
          <input id="c_city" placeholder="Ville (ex: Chamonix)" />
        </div>
        <div style="margin-top:10px">
          <input id="c_cat" placeholder="Catégorie (ex: restaurant)" />
        </div>
        <div class="row" style="margin-top:10px">
          <button id="btn_create">Créer</button>
          <button id="btn_refresh">Rafraîchir</button>
        </div>
        <details>
          <summary class="muted">Debug (dernier JSON)</summary>
          <pre id="debug_create">{}</pre>
        </details>
      </div>

      <div class="card">
        <h3 style="margin-top:0">Filtrer / Lister</h3>
        <div class="row">
          <input id="f_city" placeholder="Ville (optionnel)" />
          <input id="f_cat" placeholder="Catégorie (optionnel)" />
        </div>
        <div class="row" style="margin-top:10px">
          <button id="btn_load">Charger</button>
          <button id="btn_clear">Reset filtres</button>
        </div>
        <div class="muted" style="margin-top:10px">
          Affichage en “cartes” avec moyenne ⭐ et reviews.
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3 style="margin-top:0">Ajouter une review</h3>
      <div class="row">
        <input id="r_est_id" placeholder="Establishment ID (ex: 1)" />
        <input id="r_rating" placeholder="Rating (0-5)" />
      </div>
      <div style="margin-top:10px">
        <textarea id="r_comment" placeholder="Commentaire"></textarea>
      </div>
      <div style="margin-top:10px">
        <input id="r_tags" placeholder="Tags (séparés par des virgules) ex: toxic_management, unpaid_hours" />
      </div>
      <div class="row" style="margin-top:10px">
        <button id="btn_review">Créer la review</button>
        <button id="btn_review_refresh">Rafraîchir la liste</button>
      </div>
      <details>
        <summary class="muted">Debug (dernier JSON)</summary>
        <pre id="debug_review">{}</pre>
      </details>
    </div>

    <div style="margin-top:16px" class="cards" id="est_cards"></div>
  </div>

<script>
  const API = "http://127.0.0.1:8000";

  const $ = (id) => document.getElementById(id);

  function stars(avg) {
    const rounded = Math.round(avg);
    return "★".repeat(rounded) + "☆".repeat(5-rounded);
  }

  async function apiCall(method, path, body) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(API + path, opts);
    const text = await res.text();
    let json;
    try { json = text ? JSON.parse(text) : null; } catch { json = { raw: text }; }
    return { ok: res.ok, status: res.status, data: json };
  }

  function renderCards(items) {
    const root = $("est_cards");
    root.innerHTML = "";

    if (!items || items.length === 0) {
      root.innerHTML = `<div class="card"><div class="muted">Aucun établissement.</div></div>`;
      return;
    }

    for (const e of items) {
      const card = document.createElement("div");
      card.className = "card";

      const avg = e.avg_rating ?? 0;
      const count = e.reviews_count ?? (e.reviews ? e.reviews.length : 0);

      card.innerHTML = `
        <div class="est-head">
          <div>
            <div class="est-title">#${e.id} — ${escapeHtml(e.name)}</div>
            <div class="est-meta">${escapeHtml(e.city)} · <span class="pill">${escapeHtml(e.category)}</span></div>
            <div style="margin-top:6px" class="stars">${stars(avg)} <span class="muted">(${avg} / 5 · ${count} review(s))</span></div>
          </div>
          <div style="display:flex; gap:10px">
            <button class="btn-red" data-del="${e.id}">Delete</button>
          </div>
        </div>

        <div class="reviews" id="rev_${e.id}">
          ${renderReviews(e.reviews || [])}
        </div>
      `;

      root.appendChild(card);
    }

    // bind delete
    root.querySelectorAll("[data-del]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-del");
        const r = await apiCall("DELETE", `/establishments/${id}`);
        if (!r.ok) alert("Delete failed: " + r.status);
        await loadFull();
      });
    });
  }

  function renderReviews(revs) {
    if (!revs || revs.length === 0) return `<div class="muted">Aucune review pour l’instant.</div>`;

    // latest first
    const sorted = [...revs].sort((a,b) => (b.id||0)-(a.id||0));

    return sorted.map(r => `
      <div class="rev">
        <div class="rev-top">
          <div><b>Rating:</b> ${r.rating} / 5</div>
          <div class="muted">#${r.id}</div>
        </div>
        <div style="margin-top:6px">${escapeHtml(r.comment)}</div>
        <div class="tagline">
          ${(r.tags || []).map(t => `<span class="pill">${escapeHtml(t)}</span>`).join("")}
        </div>
      </div>
    `).join("");
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (m) => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[m]));
  }

  async function loadFull() {
    const city = $("f_city").value.trim();
    const cat = $("f_cat").value.trim();
    const qs = new URLSearchParams();
    if (city) qs.set("city", city);
    if (cat) qs.set("category", cat);

    const r = await apiCall("GET", `/establishments_full?${qs.toString()}`);
    if (!r.ok) {
      alert("Load failed: " + r.status);
      return;
    }
    renderCards(r.data);
  }

  // ---- actions ----
  $("btn_create").addEventListener("click", async () => {
    const payload = {
      name: $("c_name").value.trim(),
      city: $("c_city").value.trim(),
      category: $("c_cat").value.trim(),
    };
    const r = await apiCall("POST", "/establishments", payload);
    $("debug_create").textContent = JSON.stringify(r, null, 2);
    if (!r.ok) alert("Create failed: " + r.status);
    await loadFull();
  });

  $("btn_refresh").addEventListener("click", loadFull);
  $("btn_load").addEventListener("click", loadFull);
  $("btn_clear").addEventListener("click", async () => {
    $("f_city").value = "";
    $("f_cat").value = "";
    await loadFull();
  });

  $("btn_review").addEventListener("click", async () => {
    const estId = $("r_est_id").value.trim();
    const rating = Number($("r_rating").value.trim());
    const tags = $("r_tags").value.split(",").map(s => s.trim()).filter(Boolean);
    const payload = {
      rating,
      comment: $("r_comment").value.trim(),
      tags: tags.length ? tags : null
    };

    const r = await apiCall("POST", `/establishments/${estId}/reviews`, payload);
    $("debug_review").textContent = JSON.stringify(r, null, 2);
    if (!r.ok) alert("Review failed: " + r.status);
    await loadFull();
  });

  $("btn_review_refresh").addEventListener("click", loadFull);

  // first load
  loadFull();
</script>
</body>
</html>