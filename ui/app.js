// ui/app.js

// ---------- Helpers UI ----------
const input = document.getElementById("search");
const results = document.getElementById("results");

const selectedBox = document.getElementById("selected");
const selectedName = document.getElementById("selected-name");
const selectedAddress = document.getElementById("selected-address");
const selectedMeta = document.getElementById("selected-meta");

const btnDetails = document.getElementById("btn-details");
const btnAdd = document.getElementById("btn-add");

const statusEl = document.getElementById("status");

let selected = null; // { place_id, description, details? }
let debounceTimer = null;

function setStatus(msg = "", type = "info") {
  statusEl.textContent = msg;
  statusEl.dataset.type = type;
}

function clearResults() {
  results.innerHTML = "";
  results.style.display = "none";
}

function showResults(items) {
  results.innerHTML = "";

  if (!items || items.length === 0) {
    clearResults();
    return;
  }

  results.style.display = "block";

  items.forEach((it) => {
    const div = document.createElement("div");
    div.className = "result-item";
    div.textContent = it.description || "";

    div.addEventListener("click", () => {
      // Save selection
      selected = {
        place_id: it.place_id,
        description: it.description,
        details: null,
      };

      // Fill input + close list
      input.value = it.description;
      clearResults();

      // Show selected card (basic)
      selectedBox.style.display = "block";
      selectedName.textContent = it.description;
      selectedAddress.textContent = "";
      selectedMeta.textContent = "";

      // Buttons state
      btnDetails.disabled = false;
      btnAdd.disabled = true;

      setStatus("Sélection OK. Clique sur “Voir détails”.", "ok");
    });

    results.appendChild(div);
  });
}

// ---------- API calls ----------
async function apiGet(url) {
  const r = await fetch(url);
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(txt || `HTTP ${r.status}`);
  }
  return r.json();
}

async function autocomplete(q) {
  // Endpoint returns either [] or {data:[]}. We support both.
  const data = await apiGet(`/api/google/autocomplete?q=${encodeURIComponent(q)}`);
  return Array.isArray(data) ? data : (data.data || []);
}

async function placeDetails(placeId) {
  const data = await apiGet(`/api/google/place?place_id=${encodeURIComponent(placeId)}`);
  // Endpoint returns either direct object or {data:{...}}. We support both.
  return data.data || data;
}

// ---------- Events ----------
input.addEventListener("input", () => {
  const q = input.value.trim();

  // Reset current selection when typing
  selected = null;
  btnDetails.disabled = true;
  btnAdd.disabled = true;

  if (q.length < 3) {
    clearResults();
    setStatus("", "info");
    return;
  }

  setStatus("Recherche…", "info");

  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(async () => {
    try {
      const items = await autocomplete(q);
      showResults(items);
      setStatus("Clique sur un résultat.", "info");
    } catch (e) {
      console.error(e);
      clearResults();
      setStatus("Erreur autocomplete.", "err");
    }
  }, 250);
});

btnDetails.addEventListener("click", async () => {
  if (!selected?.place_id) return;

  btnDetails.disabled = true;
  setStatus("Chargement des détails…", "info");

  try {
    const d = await placeDetails(selected.place_id);

    // Normalize details keys for our UI + DB
    const normalized = {
      google_place_id: d.google_place_id || d.place_id || selected.place_id,
      name: d.name || selected.description,
      address: d.address || d.formatted_address || "",
      rating: (typeof d.rating === "number" ? d.rating : null),
      types: Array.isArray(d.types) ? d.types : [],
    };

    selected.details = normalized;

    // Render in UI
    selectedName.textContent = normalized.name;
    selectedAddress.textContent = normalized.address;

    const ratingText = normalized.rating != null ? `⭐ ${normalized.rating}` : "";
    const typesText = normalized.types.length ? normalized.types.slice(0, 4).join(", ") : "";
    selectedMeta.textContent = [ratingText, typesText].filter(Boolean).join(" • ");

    // Enable Add button
    btnAdd.disabled = false;
    setStatus("Détails OK. Tu peux “Ajouter à THENA”.", "ok");
  } catch (e) {
    console.error(e);
    setStatus("Erreur détails (place).", "err");
  } finally {
    btnDetails.disabled = false;
  }
});

btnAdd.addEventListener("click", async () => {
  if (!selected?.details) return;

  btnAdd.disabled = true;
  setStatus("Ajout à THENA…", "info");

  try {
    const d = selected.details;

    // ✅ Payload EXACT attendu par POST /establishments (sinon 422)
    const payload = {
      google_place_id: d.google_place_id,
      name: d.name,
      address: d.address,
      rating: d.rating,       // null accepté
      types: d.types,         // [] accepté
    };

    const r = await fetch("/establishments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!r.ok) {
      const txt = await r.text();
      throw new Error(txt || `HTTP ${r.status}`);
    }

    setStatus("✅ Ajouté à ta base THENA.", "ok");
  } catch (e) {
    console.error(e);
    setStatus("Erreur ajout DB (/establishments).", "err");
  } finally {
    btnAdd.disabled = false;
  }
});

// Close dropdown when clicking outside
document.addEventListener("click", (e) => {
  const isInside = results.contains(e.target) || input.contains(e.target);
  if (!isInside) clearResults();
});

// Initial UI state
clearResults();
btnDetails.disabled = true;
btnAdd.disabled = true;
setStatus("", "info");
