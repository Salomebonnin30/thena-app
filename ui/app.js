/* ui/app.js
   THENA — Front ultra clean (no framework)
   - Autocomplete Google -> click -> fiche THENA
   - Si pas en DB -> propose "Ajouter à THENA + 1ère review"
   - Si déjà en DB -> affiche reviews + formulaire "Ajouter une review"
   - Draft persisté en localStorage
   Compatible avec ton backend main.py :
   - GET  /api/google/autocomplete?q=
   - GET  /api/google/place?place_id=
   - POST /establishments   (retourne EstablishmentOut)
   - GET  /establishments/by_google/{google_place_id} (retourne bundle EstablishmentWithStats)
   - POST /reviews
   - DELETE /reviews/{id}
*/

"use strict";

/* =========================
   DOM
========================= */
const $ = (sel) => document.querySelector(sel);

const search = $("#search");
const hint = $("#hint");
const suggestions = $("#suggestions");
const panel = $("#panel");

/* =========================
   Config & State
========================= */
const API = ""; // same origin
const LS = {
  lastQuery: "thena:lastQuery",
  currentPlaceId: "thena:currentPlaceId",
  currentGooglePlaceId: "thena:currentGooglePlaceId",
  draft: (key) => `thena:draft:${key}`,
};

let debounceTimer = null;
let current = {
  place: null,          // normalized google place
  bundle: null,         // EstablishmentWithStats {establishment, reviews, thena_avg, ...}
};

/* =========================
   Helpers
========================= */
function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeJson(str, fallback) {
  try {
    return JSON.parse(str);
  } catch {
    return fallback;
  }
}

function setHint(text) {
  hint.textContent = text || "";
}

function clearSuggestions() {
  suggestions.innerHTML = "";
}

function showPanel() {
  panel.classList.remove("hidden");
}

function hidePanel() {
  panel.classList.add("hidden");
  panel.innerHTML = "";
}

function formatDate(isoOrDate) {
  try {
    const d = new Date(isoOrDate);
    if (Number.isNaN(d.getTime())) return String(isoOrDate ?? "");
    return d.toLocaleString();
  } catch {
    return String(isoOrDate ?? "");
  }
}

function safeNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function computeAverageScore(reviews) {
  const vals = (reviews || [])
    .map((r) => safeNumber(r.score))
    .filter((n) => n != null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function scoreMeta(avg) {
  if (avg == null) return { label: "N/A", cls: "kpi" };
  if (avg >= 7) return { label: avg.toFixed(1), cls: "kpi kpi_good" };
  if (avg >= 4) return { label: avg.toFixed(1), cls: "kpi kpi_warn" };
  return { label: avg.toFixed(1), cls: "kpi kpi_bad" };
}

function scorePillClass(score) {
  if (score == null) return "scorePill na";
  if (score >= 7) return "scorePill good";
  if (score >= 4) return "scorePill warn";
  return "scorePill bad";
}

function normalizePlace(p) {
  // backend /api/google/place returns:
  // { google_place_id, name, address, google_rating, types }
  const rating =
    p?.rating ?? p?.google_rating ?? p?.googleRating ?? p?.google?.rating ?? null;

  const types = p?.types ?? (typeof p?.types_json === "string" ? safeJson(p.types_json, []) : []) ?? [];

  return {
    google_place_id: p?.google_place_id ?? p?.place_id ?? p?.googlePlaceId ?? null,
    name: p?.name ?? "",
    address: p?.address ?? p?.formatted_address ?? "",
    rating: rating == null ? null : Number(rating),
    types: Array.isArray(types) ? types : [],
  };
}

/* =========================
   API
========================= */
async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text || null;
  }

  if (!res.ok) {
    const msg =
      (data && data.detail && typeof data.detail === "string" && data.detail) ||
      (typeof data === "string" ? data : null) ||
      `${res.status} ${res.statusText}`;
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

const apiGET = (p) => apiFetch(p);
const apiPOST = (p, body) => apiFetch(p, { method: "POST", body: JSON.stringify(body) });
const apiDELETE = (p) => apiFetch(p, { method: "DELETE" });

/* =========================
   Draft
========================= */
function draftKey() {
  const gid = current?.place?.google_place_id;
  return gid ? LS.draft(`google:${gid}`) : null;
}

function saveDraft(partial) {
  const key = draftKey();
  if (!key) return;
  const existing = safeJson(localStorage.getItem(key), {}) || {};
  localStorage.setItem(key, JSON.stringify({ ...existing, ...partial, _ts: Date.now() }));
}

function loadDraft() {
  const key = draftKey();
  if (!key) return {};
  return safeJson(localStorage.getItem(key), {}) || {};
}

function clearDraft() {
  const key = draftKey();
  if (!key) return;
  localStorage.removeItem(key);
}

/* =========================
   Flags + Housing
========================= */
const HOUSING_OPTIONS = [
  { v: "", label: "—" },
  { v: "NON_LOGE", label: "Non logé" },
  { v: "LOGE", label: "Logé (fourni par l’employeur)" },
];

const HOUSING_QUALITY_OPTIONS = [
  { v: "", label: "—" },
  { v: "TOP", label: "Top" },
  { v: "OK", label: "OK" },
  { v: "MOYEN", label: "Moyen" },
  { v: "MAUVAIS", label: "Mauvais" },
  { v: "INSALUBRE", label: "Insalubre" },
];

function renderFlag(label, key, checked) {
  return `
    <label class="badge" style="cursor:pointer; user-select:none;">
      <input type="checkbox" data-flag="${escapeHtml(key)}" ${checked ? "checked" : ""} />
      ${escapeHtml(label)}
    </label>
  `;
}

function collectFlags() {
  const flags = {};
  panel.querySelectorAll("input[data-flag]").forEach((cb) => {
    flags[cb.dataset.flag] = cb.checked;
  });
  return flags;
}

function flagsToBackend(flags) {
  // mapping UI -> backend ReviewCreate fields
  return {
    coupure: !!flags.coupure,
    unpaid_overtime: !!flags.heures_sup_non_payees,
    toxic_manager: !!flags.manager_toxique,
    harassment: !!flags.harcelement,
    recommend: !!flags.je_recommande,
  };
}

function setFormMsg(text, kind = "ok") {
  const el = $("#formMsg");
  if (!el) return;
  el.className = kind === "err" ? "err" : "ok";
  el.textContent = text;
}

/* =========================
   Backend lookup (THE fix)
========================= */
async function lookupBundleByGoogleId(googlePlaceId) {
  if (!googlePlaceId) return null;
  try {
    // ✅ ton backend : PATH param
    return await apiGET(`/establishments/by_google/${encodeURIComponent(googlePlaceId)}`);
  } catch (e) {
    if (e.status === 404) return null;
    throw e;
  }
}

/* =========================
   Render Panel
========================= */
function renderSuggestions(items) {
  clearSuggestions();
  if (!items || !items.length) return;

  const frag = document.createDocumentFragment();
  for (const it of items) {
    const placeId = it.place_id || it.placeId || it.google_place_id;
    const desc = it.description || it.name || "";
    const div = document.createElement("div");
    div.className = "sug";
    div.textContent = desc;
    div.onclick = () => onSelectSuggestion(placeId);
    frag.appendChild(div);
  }
  suggestions.appendChild(frag);
}

function renderPanel(bundleOrNull, isNewFlow) {
  showPanel();

  const place = current.place;
  const bundle = bundleOrNull;
  const reviews = bundle?.reviews ?? [];
  const avg = computeAverageScore(reviews);
  const avgMeta = scoreMeta(avg);

  const googleText = place.rating != null ? place.rating.toFixed(1) : "N/A";
  const typesHtml = (place.types || [])
    .slice(0, 8)
    .map((t) => `<span class="badge badge-na">${escapeHtml(t)}</span>`)
    .join("");

  const reviewsCount = reviews.length;

  const topHtml = `
    <div class="panelTop">
      <div>
        <div class="title">${escapeHtml(place.name || "Établissement")}</div>
        <div class="addr">${escapeHtml(place.address || "")}</div>
        <div class="row" style="margin-top:10px">
          <span class="badge blue">Google: ${escapeHtml(googleText)}</span>
          <span class="badge muted">Avis THENA: ${reviewsCount}</span>
          ${typesHtml}
        </div>
      </div>

      <div class="${avgMeta.cls}">
        <div class="k">MOYENNE THENA</div>
        <div class="v">${escapeHtml(avgMeta.label)}${avg != null ? " / 10" : ""}</div>
      </div>
    </div>
    <div class="sep"></div>
  `;

  const listHtml =
    reviewsCount === 0
      ? `<div class="small">Aucun avis THENA pour le moment.</div>`
      : reviews
          .map((r) => {
            const score = safeNumber(r.score);
            const pillText = score == null ? "Sans note" : `${score}/10`;
            const pillCls = scorePillClass(score);

            const metaBits = [
              r.role ? `Rôle: ${escapeHtml(r.role)}` : null,
              r.contract ? `Contrat: ${escapeHtml(r.contract)}` : null,
              r.housing ? `Logement: ${escapeHtml(r.housing)}` : null,
              r.housing_quality ? `Qualité: ${escapeHtml(r.housing_quality)}` : null,
            ].filter(Boolean);

            return `
              <div class="review">
                <div class="reviewHead">
                  <div>
                    <span class="${pillCls}">${escapeHtml(pillText)}</span>
                    ${metaBits.length ? `<span class="small"> • ${metaBits.join(" • ")}</span>` : ""}
                  </div>
                  <div class="small">${escapeHtml(formatDate(r.created_at))}</div>
                </div>

                <div style="margin-top:8px">${escapeHtml(r.comment || "")}</div>

                ${
                  r.id
                    ? `<div class="btnRow">
                        <button class="btnDanger" onclick="deleteReview('${r.id}')">Supprimer</button>
                        <span class="small">Visible uniquement sur l'appareil qui a posté l’avis.</span>
                      </div>`
                    : ""
                }
              </div>
            `;
          })
          .join("");

  const draft = loadDraft();
  const defaultScore = draft.score ?? "";
  const defaultRole = draft.role ?? "";
  const defaultContract = draft.contract ?? "";
  const defaultComment = draft.comment ?? "";
  const defaultHousing = draft.housing ?? "";
  const defaultHousingQuality = draft.housing_quality ?? "";
  const defaultFlags = draft.flags ?? {};

  const housingOptionsHtml = HOUSING_OPTIONS.map(
    (o) =>
      `<option value="${escapeHtml(o.v)}" ${o.v === defaultHousing ? "selected" : ""}>${escapeHtml(o.label)}</option>`
  ).join("");

  const housingQualityOptionsHtml = HOUSING_QUALITY_OPTIONS.map(
    (o) =>
      `<option value="${escapeHtml(o.v)}" ${o.v === defaultHousingQuality ? "selected" : ""}>${escapeHtml(o.label)}</option>`
  ).join("");

  const formTitle = isNewFlow ? "Ajouter à THENA + 1ère review" : "Ajouter une review";
  const btnText = isNewFlow ? "Ajouter + 1ère review" : "Ajouter la review";

  panel.innerHTML = `
    <section class="card">
      ${topHtml}

      <div>
        <h3 style="margin:0 0 10px 0">Reviews THENA</h3>
        ${listHtml}
      </div>

      <div class="sep"></div>

      <div>
        <h3 style="margin:0 0 10px 0">${escapeHtml(formTitle)}</h3>

        <div class="grid2">
          <div>
            <label>Note (0-10) (optionnelle)</label>
            <input id="score" class="input" inputmode="numeric" placeholder="ex: 7" value="${escapeHtml(defaultScore)}" />
            <div class="small">Si vide, l'avis est publié “Sans note”.</div>
          </div>

          <div>
            <label>Rôle (optionnel)</label>
            <input id="role" class="input" placeholder="ex: serveuse" value="${escapeHtml(defaultRole)}" />
          </div>

          <div>
            <label>Contrat (optionnel)</label>
            <select id="contract" class="input">
              <option value="" ${defaultContract === "" ? "selected" : ""}>—</option>
              <option value="CDI" ${defaultContract === "CDI" ? "selected" : ""}>CDI</option>
              <option value="CDD" ${defaultContract === "CDD" ? "selected" : ""}>CDD</option>
              <option value="Saisonnier" ${defaultContract === "Saisonnier" ? "selected" : ""}>Saisonnier</option>
              <option value="Intérim" ${defaultContract === "Intérim" ? "selected" : ""}>Intérim</option>
              <option value="Stage" ${defaultContract === "Stage" ? "selected" : ""}>Stage</option>
              <option value="Alternance" ${defaultContract === "Alternance" ? "selected" : ""}>Alternance</option>
              <option value="Freelance" ${defaultContract === "Freelance" ? "selected" : ""}>Freelance</option>
            </select>
          </div>

          <div>
            <label>Logement (optionnel)</label>
            <select id="housing" class="input">${housingOptionsHtml}</select>
          </div>

          <div>
            <label>Qualité du logement (optionnel)</label>
            <select id="housing_quality" class="input">${housingQualityOptionsHtml}</select>
            <div class="small">Remplis surtout si tu es logé(e) par l’employeur.</div>
          </div>
        </div>

        <div style="margin-top:10px">
          <label>Commentaire (obligatoire)</label>
          <textarea id="comment" placeholder="Décris ce qui est VRAI sur le terrain..." required>${escapeHtml(defaultComment)}</textarea>
        </div>

        <div class="row" style="margin-top:10px">
          ${renderFlag("Coupure", "coupure", defaultFlags.coupure)}
          ${renderFlag("Heures sup non payées", "heures_sup_non_payees", defaultFlags.heures_sup_non_payees)}
          ${renderFlag("Manager toxique", "manager_toxique", defaultFlags.manager_toxique)}
          ${renderFlag("Harcèlement", "harcelement", defaultFlags.harcelement)}
          ${renderFlag("Je recommande", "je_recommande", defaultFlags.je_recommande)}
        </div>

        <div class="btnRow">
          <button class="btnPrimary" id="submitReview">${escapeHtml(btnText)}</button>
          <button class="btnGhost" id="refreshBtn">Rafraîchir</button>
          <span class="small">Brouillon auto-sauvegardé sur cet appareil.</span>
        </div>

        <div id="formMsg"></div>
      </div>
    </section>
  `;

  // wire events
  const scoreEl = $("#score");
  const roleEl = $("#role");
  const contractEl = $("#contract");
  const housingEl = $("#housing");
  const housingQualityEl = $("#housing_quality");
  const commentEl = $("#comment");

  const saveAll = () => {
    saveDraft({
      score: scoreEl.value,
      role: roleEl.value,
      contract: contractEl.value,
      housing: housingEl.value,
      housing_quality: housingQualityEl.value,
      comment: commentEl.value,
      flags: collectFlags(),
    });
  };

  ["input", "change"].forEach((ev) => {
    scoreEl.addEventListener(ev, saveAll);
    roleEl.addEventListener(ev, saveAll);
    contractEl.addEventListener(ev, saveAll);
    housingEl.addEventListener(ev, saveAll);
    housingQualityEl.addEventListener(ev, saveAll);
    commentEl.addEventListener(ev, saveAll);
  });

  panel.querySelectorAll("input[data-flag]").forEach((cb) => cb.addEventListener("change", saveAll));

  $("#submitReview").onclick = async () => submitReviewFlow({ isNewFlow });
  $("#refreshBtn").onclick = async () => refreshCurrent();
}

/* =========================
   Core flows
========================= */
async function onSelectSuggestion(placeId) {
  try {
    setHint("Chargement...");
    clearSuggestions();
    localStorage.setItem(LS.currentPlaceId, placeId);

    // 1) Google details
    const placeRaw = await apiGET(`/api/google/place?place_id=${encodeURIComponent(placeId)}`);
    current.place = normalizePlace(placeRaw);

    const gid = current.place.google_place_id;
    localStorage.setItem(LS.currentGooglePlaceId, gid);

    // 2) DB bundle
    const bundle = await lookupBundleByGoogleId(gid);
    current.bundle = bundle;

    if (!bundle) {
      setHint("Pas encore dans THENA. Ajoute + 1ère review 👇");
      renderPanel(null, true);
    } else {
      setHint("Fiche THENA chargée.");
      renderPanel(bundle, false);
    }
  } catch (e) {
    console.error(e);
    setHint("Erreur chargement (API).");
    hidePanel();
    alert(`Erreur: ${e.message}`);
  }
}

async function refreshCurrent() {
  const gid = current?.place?.google_place_id || localStorage.getItem(LS.currentGooglePlaceId);
  if (!gid) return;
  const bundle = await lookupBundleByGoogleId(gid);
  current.bundle = bundle;
  renderPanel(bundle, !bundle);
}

async function ensureEstablishmentExists() {
  // Si bundle existe -> ok
  if (current.bundle?.establishment?.id) return current.bundle;

  // Sinon on crée l’establishment (backend renvoie EstablishmentOut)
  const place = current.place;
  if (!place?.google_place_id) throw new Error("Google place id manquant");

  await apiPOST("/establishments", {
    google_place_id: place.google_place_id,
    name: place.name,
    address: place.address,
    google_rating: place.rating,
    types: place.types || [],
  });

  // Puis on récupère le bundle complet (reviews + stats)
  const bundle = await lookupBundleByGoogleId(place.google_place_id);
  current.bundle = bundle;
  return bundle;
}

async function submitReviewFlow({ isNewFlow }) {
  const scoreEl = $("#score");
  const roleEl = $("#role");
  const contractEl = $("#contract");
  const housingEl = $("#housing");
  const housingQualityEl = $("#housing_quality");
  const commentEl = $("#comment");

  const scoreVal = scoreEl?.value?.trim();
  const score = scoreVal === "" ? null : Number(scoreVal);
  if (scoreVal !== "" && (!Number.isFinite(score) || score < 0 || score > 10)) {
    setFormMsg("La note doit être entre 0 et 10 (ou vide).", "err");
    return;
  }

  const comment = commentEl?.value?.trim();
  if (!comment) {
    setFormMsg("Le commentaire est obligatoire.", "err");
    return;
  }

  try {
    setFormMsg("Enregistrement...", "ok");

    const bundle = await ensureEstablishmentExists();
    const estId = bundle.establishment.id;

    const flags = collectFlags();

    const payload = {
      establishment_id: estId,
      score: score,
      comment: comment,
      role: roleEl?.value?.trim() || null,
      contract: contractEl?.value || null,
      housing: housingEl?.value || null,
      housing_quality: housingQualityEl?.value || null,
      ...flagsToBackend(flags),
    };

    await apiPOST("/reviews", payload);

    // refresh bundle
    const fresh = await lookupBundleByGoogleId(current.place.google_place_id);
    current.bundle = fresh;

    // reset form
    scoreEl.value = "";
    roleEl.value = "";
    contractEl.value = "";
    housingEl.value = "";
    housingQualityEl.value = "";
    commentEl.value = "";
    panel.querySelectorAll("input[data-flag]").forEach((cb) => (cb.checked = false));

    clearDraft();
    setHint("Ajout terminé ✅");
    setFormMsg("Review ajoutée ✅", "ok");
    renderPanel(fresh, false);
  } catch (e) {
    console.error(e);
    setFormMsg(`Erreur API: ${e.message}`, "err");
  }
}

/* =========================
   Delete review (global)
========================= */
window.deleteReview = async (id) => {
  if (!id) return;
  if (!confirm("Supprimer cet avis ?")) return;

  try {
    await apiDELETE(`/reviews/${encodeURIComponent(id)}`);
    await refreshCurrent();
  } catch (e) {
    alert(`Erreur suppression: ${e.message}`);
  }
};

/* =========================
   Search input -> autocomplete
========================= */
search.addEventListener("input", () => {
  const q = search.value.trim();
  localStorage.setItem(LS.lastQuery, q);

  setHint("");
  clearSuggestions();
  hidePanel();

  if (debounceTimer) clearTimeout(debounceTimer);
  if (!q) return;

  debounceTimer = setTimeout(async () => {
    try {
      setHint("Chargement...");
      const items = await apiGET(`/api/google/autocomplete?q=${encodeURIComponent(q)}`);
      if (!items || items.length === 0) {
        setHint("Aucun résultat.");
        return;
      }
      setHint("Clique un résultat.");
      renderSuggestions(items);
    } catch (e) {
      console.error(e);
      setHint("Erreur autocomplete (clé Google ?).");
    }
  }, 250);
});

/* =========================
   Boot
========================= */
(function boot() {
  const q = localStorage.getItem(LS.lastQuery);
  if (q) search.value = q;
})();
