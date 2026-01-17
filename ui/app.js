/* ui/app.js
   THENA — Front ultra clean (no framework)
   + Auth (magic link) + UI pro (works with main.py routes)
*/

"use strict";

/* =========================
   DOM helpers
========================= */
const $ = (sel) => document.querySelector(sel);

const search = $("#search");
const hint = $("#hint");
const suggestions = $("#suggestions");
const panel = $("#panel");

// auth header
const authStatus = $("#authStatus");
const btnLogin = $("#btnLogin");
const btnLogout = $("#btnLogout");

// modal
const loginModal = $("#loginModal");
const btnCloseModal = $("#btnCloseModal");
const btnSendLink = $("#btnSendLink");
const loginEmail = $("#loginEmail");
const loginPseudo = $("#loginPseudo");
const loginMsg = $("#loginMsg");
const devLinkBox = $("#devLinkBox"); // optional div in html
const devLinkA = $("#devLinkA");     // optional a in html

/* =========================
   Config & State
========================= */
const API = ""; // same origin

const LS = {
  lastQuery: "thena:lastQuery",
  currentPlaceId: "thena:currentPlaceId",
  currentEstId: "thena:currentEstId",
  draft: (placeIdOrEstId) => `thena:draft:${placeIdOrEstId}`,
};

let debounceTimer = null;

let current = {
  place: null,          // Google place details normalized
  establishment: null,  // bundle {establishment, reviews}
};

let auth = {
  user: null, // {id, pseudo}
};

/* =========================
   Utils
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
  try { return JSON.parse(str); } catch { return fallback; }
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
  const vals = (reviews || []).map((r) => safeNumber(r.score)).filter((n) => n != null);
  if (!vals.length) return null;
  const sum = vals.reduce((a, b) => a + b, 0);
  return sum / vals.length;
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
  const rating =
    p?.rating ?? p?.google_rating ?? p?.googleRating ?? p?.google?.rating ?? p?.google_rating ?? null;

  const types =
    p?.types ??
    p?.place_types ??
    p?.place?.types ??
    (typeof p?.types_json === "string" ? safeJson(p.types_json, []) : []) ??
    [];

  return {
    google_place_id: p?.place_id ?? p?.google_place_id ?? p?.googlePlaceId ?? null,
    name: p?.name ?? "",
    address: p?.formatted_address ?? p?.address ?? "",
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
    credentials: "include", // IMPORTANT: cookies session
    ...opts,
  });

  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; }
  catch { data = text || null; }

  if (!res.ok) {
    const msg =
      (data && data.detail) ||
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

async function tryManyGet(paths) {
  let lastErr = null;
  for (const p of paths) {
    try { return await apiGET(p); }
    catch (e) {
      lastErr = e;
      if (![404, 422].includes(e.status)) break;
    }
  }
  throw lastErr ?? new Error("GET failed");
}

/* =========================
   Draft persistence
========================= */
function draftKey() {
  const k = current?.establishment?.establishment?.id
    ? `est:${current.establishment.establishment.id}`
    : current?.place?.google_place_id
      ? `place:${current.place.google_place_id}`
      : null;
  return k ? LS.draft(k) : null;
}

function saveDraft(partial) {
  const key = draftKey();
  if (!key) return;
  const existing = safeJson(localStorage.getItem(key), {}) || {};
  const merged = { ...existing, ...partial, _ts: Date.now() };
  localStorage.setItem(key, JSON.stringify(merged));
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
   Auth UI
========================= */
function openModal() {
  loginModal.classList.remove("hidden");
  loginModal.setAttribute("aria-hidden", "false");
  loginMsg.textContent = "";
  if (devLinkBox) devLinkBox.classList.add("hidden");
  loginEmail.focus();
}

function closeModal() {
  loginModal.classList.add("hidden");
  loginModal.setAttribute("aria-hidden", "true");
}

function setAuthUI() {
  if (auth.user) {
    authStatus.textContent = `Connecté : ${auth.user.pseudo}`;
    btnLogin.classList.add("hidden");
    btnLogout.classList.remove("hidden");
  } else {
    authStatus.textContent = "Non connecté";
    btnLogin.classList.remove("hidden");
    btnLogout.classList.add("hidden");
  }

  // re-render panel to lock/unlock submit if already visible
  if (!panel.classList.contains("hidden") && current.place) {
    renderPanel(current.establishment, !current.establishment);
  }
}

async function refreshAuth() {
  try {
    const me = await apiGET("/me");
    // /me returns { user: { id, pseudo, created_at } }
    auth.user = me?.user ?? null;
  } catch {
    auth.user = null;
  }
  setAuthUI();
}

/* =========================
   Flags + Housing
========================= */
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

function setFormMsg(text, kind = "ok") {
  const el = $("#formMsg");
  if (!el) return;
  el.className = kind === "err" ? "err" : "ok";
  el.textContent = text;
}

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

function housingLabel(v) {
  const map = {
    NON_LOGE: "Non logé",
    LOGE: "Logé",
    TOP: "Top",
    OK: "OK",
    MOYEN: "Moyen",
    MAUVAIS: "Mauvais",
    INSALUBRE: "Insalubre",
  };
  return map[v] || v || null;
}

/* =========================
   Render Suggestions
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

/* =========================
   Render Panel
========================= */
function renderPanel(estBundle, isNewFlow) {
  showPanel();

  const place = current.place;
  const reviews = estBundle?.reviews ?? [];
  const reviewsCount = reviews.length;

  const avg = computeAverageScore(reviews);
  const avgMeta = scoreMeta(avg);
  const googleText = place.rating != null ? place.rating.toFixed(1) : "N/A";

  const typesHtml = (place.types || [])
    .slice(0, 8)
    .map((t) => `<span class="badge badge-na">${escapeHtml(t)}</span>`)
    .join("");

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
      : reviews.map((r) => {
          const score = safeNumber(r.score);
          const pillText = score == null ? "Sans note" : `${score}/10`;
          const pillCls = scorePillClass(score);

          const author = r.user_pseudo ? `@${escapeHtml(r.user_pseudo)}` : "Utilisateur";
          const metaBits = [
            r.role ? `Rôle: ${escapeHtml(r.role)}` : null,
            r.contract ? `Contrat: ${escapeHtml(r.contract)}` : null,
            r.housing ? `Logement: ${escapeHtml(housingLabel(r.housing))}` : null,
            r.housing_quality ? `Qualité: ${escapeHtml(housingLabel(r.housing_quality))}` : null,
          ].filter(Boolean);

          const canDelete = auth.user && r.user_id === auth.user.id;

          return `
            <div class="review">
              <div class="reviewHead">
                <div>
                  <span class="${pillCls}">${escapeHtml(pillText)}</span>
                  <span class="small muted" style="margin-left:10px">${author}</span>
                  ${metaBits.length ? `<span class="small"> • ${metaBits.join(" • ")}</span>` : ""}
                </div>
                <div class="small">${escapeHtml(formatDate(r.created_at || r.createdAt || r.date))}</div>
              </div>

              <div style="margin-top:8px">${escapeHtml(r.comment || "")}</div>

              ${
                canDelete
                  ? `<div class="btnRow">
                      <button class="btnDanger" onclick="deleteReview('${r.id}')">Supprimer</button>
                    </div>`
                  : ""
              }
            </div>
          `;
        }).join("");

  const draft = loadDraft();
  const defaultScore = draft.score ?? "";
  const defaultRole = draft.role ?? "";
  const defaultContract = draft.contract ?? "";
  const defaultComment = draft.comment ?? "";
  const defaultFlags = draft.flags ?? {};
  const defaultHousing = draft.housing ?? "";
  const defaultHousingQuality = draft.housing_quality ?? "";

  const housingOptionsHtml = HOUSING_OPTIONS.map(
    (o) => `<option value="${escapeHtml(o.v)}" ${o.v === defaultHousing ? "selected" : ""}>${escapeHtml(o.label)}</option>`
  ).join("");

  const housingQualityOptionsHtml = HOUSING_QUALITY_OPTIONS.map(
    (o) => `<option value="${escapeHtml(o.v)}" ${o.v === defaultHousingQuality ? "selected" : ""}>${escapeHtml(o.label)}</option>`
  ).join("");

  const logged = !!auth.user;

  const lockHtml = logged
    ? ""
    : `<div class="err" style="margin-bottom:12px">Tu dois être connecté pour publier un avis.</div>`;

  const btnText = isNewFlow ? "Ajouter + 1ère review" : "Publier mon avis";

  panel.innerHTML = `
    <section class="card">
      ${topHtml}

      <div>
        <h3 style="margin:0 0 10px 0">Reviews THENA</h3>
        ${listHtml}
      </div>

      <div class="sep"></div>

      <div>
        <h3 style="margin:0 0 10px 0">${logged ? "Ajouter / modifier mon avis" : "Connexion requise"}</h3>
        ${lockHtml}

        <div class="grid2">
          <div>
            <label>Note (0-10) (optionnelle)</label>
            <input id="score" class="input" inputmode="numeric" placeholder="ex: 7"
              value="${escapeHtml(defaultScore)}" ${logged ? "" : "disabled"} />
            <div class="small muted">Si vide, l'avis est publié “Sans note”.</div>
          </div>

          <div>
            <label>Rôle (optionnel)</label>
            <input id="role" class="input" placeholder="ex: serveuse"
              value="${escapeHtml(defaultRole)}" ${logged ? "" : "disabled"} />
          </div>

          <div>
            <label>Contrat (optionnel)</label>
            <select id="contract" class="input" ${logged ? "" : "disabled"}>
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
            <select id="housing" class="input" ${logged ? "" : "disabled"}>${housingOptionsHtml}</select>
          </div>

          <div>
            <label>Qualité du logement (optionnel)</label>
            <select id="housing_quality" class="input" ${logged ? "" : "disabled"}>${housingQualityOptionsHtml}</select>
            <div class="small muted">Remplis surtout si tu es logé(e) par l’employeur.</div>
          </div>
        </div>

        <div style="margin-top:10px">
          <label>Commentaire (obligatoire)</label>
          <textarea id="comment" placeholder="Décris ce qui est VRAI sur le terrain..."
            ${logged ? "" : "disabled"}>${escapeHtml(defaultComment)}</textarea>
        </div>

        <div class="row" style="margin-top:10px">
          ${renderFlag("Coupure", "coupure", defaultFlags.coupure)}
          ${renderFlag("Heures sup non payées", "unpaid_overtime", defaultFlags.unpaid_overtime)}
          ${renderFlag("Manager toxique", "toxic_manager", defaultFlags.toxic_manager)}
          ${renderFlag("Harcèlement", "harassment", defaultFlags.harassment)}
          ${renderFlag("Je recommande", "recommend", defaultFlags.recommend)}
        </div>

        <div class="btnRow">
          <button class="btnPrimary" id="submitReview" ${logged ? "" : "disabled"}>${escapeHtml(btnText)}</button>
          <button class="btnGhost" id="refreshBtn">Rafraîchir</button>
          <button class="btnGhost" id="openLoginFromPanel" ${logged ? "disabled" : ""}>Se connecter</button>
        </div>

        <div id="formMsg"></div>
      </div>
    </section>
  `;

  const scoreEl = $("#score");
  const roleEl = $("#role");
  const contractEl = $("#contract");
  const housingEl = $("#housing");
  const housingQualityEl = $("#housing_quality");
  const commentEl = $("#comment");
  const submitBtn = $("#submitReview");
  const refreshBtn = $("#refreshBtn");
  const openLoginFromPanel = $("#openLoginFromPanel");

  const saveAll = () => {
    if (!logged) return;
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

  panel.querySelectorAll("input[data-flag]").forEach((cb) => {
    cb.disabled = !logged;
    cb.addEventListener("change", saveAll);
  });

  if (logged) {
    ["input", "change"].forEach((ev) => {
      scoreEl.addEventListener(ev, saveAll);
      roleEl.addEventListener(ev, saveAll);
      contractEl.addEventListener(ev, saveAll);
      housingEl.addEventListener(ev, saveAll);
      housingQualityEl.addEventListener(ev, saveAll);
      commentEl.addEventListener(ev, saveAll);
    });
    submitBtn.onclick = async () => submitReviewFlow();
  } else {
    openLoginFromPanel.onclick = openModal;
  }

  refreshBtn.onclick = async () => refreshCurrent();
}

/* =========================
   Core flows
========================= */
async function onSelectSuggestion(placeId) {
  try {
    setHint("Chargement...");
    clearSuggestions();
    localStorage.setItem(LS.currentPlaceId, placeId);

    const placeRaw = await apiGET(`/api/google/place?place_id=${encodeURIComponent(placeId)}`);
    current.place = normalizePlace(placeRaw);

    const gid = current.place.google_place_id;
    const estBundle = await lookupEstablishmentByGoogleId(gid);

    current.establishment = estBundle;
    localStorage.setItem(LS.lastQuery, search.value);

    if (!estBundle) {
      setHint("Pas encore dans THENA. Connecte-toi pour ajouter un avis.");
      renderPanel(null, true);
    } else {
      setHint("Fiche THENA chargée.");
      localStorage.setItem(LS.currentEstId, estBundle.establishment.id);
      renderPanel(estBundle, false);
    }
  } catch (e) {
    console.error(e);
    setHint("Erreur chargement (API).");
    hidePanel();
    alert(`Erreur: ${e.message}`);
  }
}

async function lookupEstablishmentByGoogleId(googlePlaceId) {
  if (!googlePlaceId) return null;
  try {
    const data = await tryManyGet([
      `/establishments/by_google/${encodeURIComponent(googlePlaceId)}`,
      `/establishments/lookup?google_place_id=${encodeURIComponent(googlePlaceId)}`,
      `/establishments/find?google_place_id=${encodeURIComponent(googlePlaceId)}`,
    ]);
    if (data?.establishment && Array.isArray(data?.reviews)) return data;
    return null;
  } catch (e) {
    if ([404, 422].includes(e.status)) return null;
    throw e;
  }
}

async function refreshCurrent() {
  if (current?.establishment?.establishment?.id) {
    const id = current.establishment.establishment.id;
    const fresh = await apiGET(`/establishments/${id}`);
    current.establishment = fresh?.establishment ? fresh : current.establishment;
    renderPanel(current.establishment, false);
    return;
  }

  const gid = current?.place?.google_place_id;
  const estBundle = await lookupEstablishmentByGoogleId(gid);
  current.establishment = estBundle;
  renderPanel(estBundle, !estBundle);
}

async function ensureEstablishmentExists() {
  let estBundle = current.establishment;
  if (estBundle) return estBundle;

  const place = current.place;
  const payload = {
    google_place_id: place.google_place_id,
    name: place.name,
    address: place.address,
    google_rating: place.rating,
    types: place.types || [],
  };

  const created = await apiPOST("/establishments", payload);
  estBundle = { establishment: created, reviews: [] };
  current.establishment = estBundle;
  localStorage.setItem(LS.currentEstId, created.id);
  return estBundle;
}

async function submitReviewFlow() {
  if (!auth.user) {
    setFormMsg("Connecte-toi pour publier.", "err");
    openModal();
    return;
  }

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

  const flags = collectFlags();

  try {
    setFormMsg("Enregistrement...", "ok");

    const estBundle = await ensureEstablishmentExists();
    const estId = estBundle.establishment.id;

    const payload = {
      establishment_id: estId,
      score,
      comment,
      role: roleEl?.value?.trim() || null,
      contract: contractEl?.value || null,
      housing: housingEl?.value || null,
      housing_quality: housingQualityEl?.value || null,

      coupure: !!flags.coupure,
      unpaid_overtime: !!flags.unpaid_overtime,
      toxic_manager: !!flags.toxic_manager,
      harassment: !!flags.harassment,
      recommend: !!flags.recommend,
    };

    await apiPOST("/reviews", payload);

    const fresh = await apiGET(`/establishments/${estId}`);
    current.establishment = fresh;

    clearDraft();
    setHint("Ajout terminé ✅");
    setFormMsg("Avis publié ✅", "ok");
    renderPanel(current.establishment, false);
  } catch (e) {
    console.error(e);
    if (e.status === 401) {
      setFormMsg("Session expirée. Reconnecte-toi.", "err");
      auth.user = null;
      setAuthUI();
      openModal();
      return;
    }
    setFormMsg(`Erreur API: ${e.message}`, "err");
  }
}

/* =========================
   Delete review (author only)
========================= */
window.deleteReview = async (id) => {
  if (!id) return;
  if (!confirm("Supprimer cet avis ?")) return;

  try {
    await apiDELETE(`/reviews/${encodeURIComponent(id)}`);

    if (current?.establishment?.establishment?.id) {
      const estId = current.establishment.establishment.id;
      const fresh = await apiGET(`/establishments/${estId}`);
      current.establishment = fresh;
      renderPanel(current.establishment, false);
    }
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
   Auth events
========================= */
btnLogin.onclick = openModal;
btnCloseModal.onclick = closeModal;

const overlay = loginModal?.querySelector(".modalOverlay");
if (overlay) overlay.onclick = closeModal;

btnSendLink.onclick = async () => {
  const email = loginEmail.value.trim();
  const pseudo = loginPseudo.value.trim();
  loginMsg.textContent = "";

  if (!email || !email.includes("@")) {
    loginMsg.textContent = "Email invalide.";
    return;
  }
  if (!pseudo || pseudo.length < 2) {
    loginMsg.textContent = "Pseudo trop court (min 2 caractères).";
    return;
  }

  try {
    btnSendLink.disabled = true;
    loginMsg.textContent = "Génération du lien magique...";

    // ✅ correct route
    const out = await apiPOST("/auth/magic-link", { email, pseudo });

    // Dev: show clickable link
    if (out?.dev_link) {
      loginMsg.textContent = "✅ Lien généré (DEV). Clique ci-dessous :";
      if (devLinkBox && devLinkA) {
        devLinkA.href = out.dev_link;
        devLinkA.textContent = out.dev_link;
        devLinkBox.classList.remove("hidden");
      } else {
        // fallback if you didn't add html elements
        loginMsg.textContent = `✅ Ouvre ce lien (DEV) : ${out.dev_link}`;
      }
    } else {
      loginMsg.textContent = "✅ Lien envoyé (prod). Vérifie tes emails.";
    }
  } catch (e) {
    console.error(e);
    loginMsg.textContent = `Erreur: ${e.message}`;
  } finally {
    btnSendLink.disabled = false;
  }
};

btnLogout.onclick = async () => {
  try {
    await apiPOST("/auth/logout", {});
  } catch {}
  auth.user = null;
  setAuthUI();
};

/* =========================
   Boot
========================= */
(async function boot() {
  const q = localStorage.getItem(LS.lastQuery);
  if (q) search.value = q;

  await refreshAuth();
})();


