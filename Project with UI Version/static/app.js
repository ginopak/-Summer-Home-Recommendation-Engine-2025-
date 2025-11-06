// static/app.js
let currentPage = 1;
const limit = 12;
const USER_ID_KEY = 'summer-stays-user-id';

let __currentUser = null;

const $  = (id) => document.getElementById(id);
const val = (id) => ($(`${id}`)?.value ?? "").trim();

// UI State Management
function showMainApp() {
  $('login-page').style.display = 'none';
  $('main-app-content').style.display = 'block';
  $('userMenu').style.display = 'block';
  document.body.classList.add('home-mode');
  document.body.classList.remove('login-mode');
  refreshDatasetStatus();
  fetchListings(1);
}

function showLoginPage() {
  __currentUser = null;
  localStorage.removeItem(USER_ID_KEY);

  if ($('env')) $('env').value = '';
  if ($('min_price')) $('min_price').value = '';
  if ($('max_price')) $('max_price').value = '';
  if ($('accommodates')) $('accommodates').value = '';
 
  $('login-page').style.display = 'flex';
  $('main-app-content').style.display = 'none';
  $('userMenu').style.display = 'none';
  document.body.classList.add('login-mode');
  document.body.classList.remove('home-mode');
  $('login-box').style.display = 'block';
  $('create-user-box').style.display = 'none';
}

// Dataset status
function updateDatasetBadge(source, count) {
  const el = $("datasetSource");
  if (el) el.textContent = `${source} (${count})`;
}
async function refreshDatasetStatus() {
  try {
    const r = await fetch("/api/dataset/status", { cache: "no-store" });
    if (!r.ok) return;
    const j = await r.json();
    updateDatasetBadge(j.source, j.count);
  } catch {}
}

// Card rendering
function card(node, it) {
  node.dataset.lid = it.listing_id;
  node.querySelector(".card-title").textContent = it.name || `Listing #${it.listing_id ?? ""}`;
  node.querySelector(".card-tag").textContent = it.tags || it.location || it.property_type || "";
  const set = (field, v) => {
    const el = node.querySelector(`[data-field="${field}"]`);
    if (el) el.textContent = v ?? "";
  };
  set("location", it.location);
  set("property_type", it.property_type ?? it.type ?? "");
  set("accommodates", it.accommodates);
  set("price", it.price);
  set("review_rating", it.review_rating);
  set("tags", Array.isArray(it.tags) ? it.tags.join(", ") : it.tags);
  try {
    const mount = node.querySelector('[data-field="amenities"]');
    if (mount) {
      const row = mount.parentElement;
      let ams = [];
      if (Array.isArray(it.amenities)) ams = it.amenities;
      else if (typeof it.amenities === "string")
        ams = it.amenities.split(/[,;|]/).map(s => s.trim()).filter(Boolean);

      if (!ams.length) { row.style.display = "none"; }
      else {
        ams.sort((a,b)=>a.localeCompare(b, undefined, {sensitivity:"base"}));
        const mkList = arr => {
          const ul = document.createElement("ul");
          ul.className = "amenities-grid";
          arr.forEach(t => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
          return ul;
        };
        const preview = mkList(ams.slice(0,3));
        const full    = mkList(ams);
        full.style.display = "none";
        mount.style.display = "none";
        row.insertAdjacentElement("afterend", preview);
        const trigger = document.createElement("span");
        trigger.className = "more-link";
        trigger.setAttribute("role", "button");
        trigger.setAttribute("tabindex", "0");
        trigger.innerHTML = "<strong>See more info</strong>";
        preview.insertAdjacentElement("afterend", trigger);
        trigger.insertAdjacentElement("afterend", full);
        if (ams.length <= 3) trigger.style.display = "none";
        const toggle = () => {
          const showAll = full.style.display === "none";
          full.style.display = showAll ? "" : "none";
          preview.style.display = showAll ? "none" : "";
          trigger.innerHTML = showAll ? "<strong>Hide all info</strong>" : "<strong>See more info</strong>";
        };
        trigger.addEventListener("click", toggle);
        trigger.addEventListener("keydown", e => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
        });
      }
    }
  } catch (_) { }
  const favBtn = node.querySelector(".fav-btn");
  const lidStr = String(it.listing_id);
  function paintFav(){
    const isFav = window.__favSet?.has(lidStr);
    favBtn.textContent = isFav ? "Remove Favorite" : "★ Add to Favorites";
    favBtn.classList.toggle("danger", isFav);
  }
  favBtn?.addEventListener("click", async () => {
    const userId = __currentUser?.user_id;
    if (!userId) return alert("Select or create a user first.");
    const isFav = window.__favSet?.has(lidStr);
    const r = await fetch("/api/favorites", {
      method: isFav ? "DELETE" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, listing_id: it.listing_id }),
    });
    if (!r.ok) {
        alert(`${isFav ? "Remove" : "Add"} failed (${r.status}). The server encountered an error.`);
        return;
    }
    await r.json();
    await hydrateFavSet();
    paintFav();
  });
  paintFav();
  node.querySelector(".book-btn")?.addEventListener("click", () => openBooking(it));
  return node;
}

function renderCards(items) {
  const wrap = $("results");
  wrap.innerHTML = "";
  if (!items || items.length === 0) {
    wrap.innerHTML = `<div class="muted">No results</div>`;
    return;
  }
  const tpl = $("cardTmpl");
  items.forEach((it) => {
    const node = tpl.content.firstElementChild.cloneNode(true);
    wrap.appendChild(card(node, it));
  });
}

// Fetch and display listings
async function fetchListings(page = 1) {
    currentPage = page;
    const params = new URLSearchParams({
        sort_by: val("sort_by") || "price",
        ascending: String((val("ascending") || "true") !== "false"),
        limit: String(limit),
        page: String(page),
    });

    if (val("env")) params.set("environment", val("env"));
    if (val("min_price")) params.set("min_price", val("min_price"));
    if (val("max_price")) params.set("max_price", val("max_price"));
    if (val("accommodates")) params.set("accommodates", val("accommodates"));

    try {
        const res = await fetch(`/api/listings?${params.toString()}`);
        if (!res.ok) {
            $("results").innerHTML = `<div class="muted">Search failed (${res.status})</div>`;
            return;
        }
        const data = await res.json();
        const items = data.items || [];
        renderCards(items);

        const total = data.total || 0;
        const maxPage = Math.max(1, Math.ceil(total / limit));
        if ($("pageInfo")) {
            $("pageInfo").textContent = `Page ${page} of ${maxPage} — ${total} results`;
        }
    } catch (err) {
        console.error("Error in fetchListings:", err);
        $("results").innerHTML = `<div class="muted">An error occurred while fetching listings.</div>`;
    }
}

// RESTORED: Function to switch to the original dataset
async function useOriginal() {
  const r = await fetch("/api/dataset/use_original", { method: "POST" });
  if (!r.ok) return alert(`Failed (${r.status})`);
  const j = await r.json();
  updateDatasetBadge(j.source, j.count);
  fetchListings(1);
}

// RESTORED: Function to download the synthetic data as a CSV
async function downloadSyntheticCSV() {
  const include_real = $("include_real")?.checked ?? true;
  // This value is just a placeholder for the backend, 
  // which might use it if no prompt is provided in a different context.
  const fake_rows = 50; 
  const r = await fetch("/api/synthetic_csv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_real, fake_rows }),
  });
  if (!r.ok) return alert(`CSV failed (${r.status})`);
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "synthetic_listings.csv"; a.click();
  URL.revokeObjectURL(url);
}


// Sends the user's prompt to the backend to generate data.
async function generateDataFromPrompt() {
  const prompt = val("syn_prompt");
  if (!prompt) {
    return alert("Prompt cannot be empty.");
  }
  closePromptModal();
  
  updateDatasetBadge("Generating...", "---");

  const payload = {
    include_real: $("include_real")?.checked ?? true,
    prompt: prompt
  };

  try {
    const r = await fetch("/api/dataset/use_synthetic", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!r.ok) {
      const err = await r.json();
      throw new Error(err.error || `Request failed with status ${r.status}`);
    }

    const j = await r.json();
    updateDatasetBadge(j.source, j.count);
    fetchListings(1); // Refresh the view with the new merged dataset
  } catch (err) {
    alert(`Error generating synthetic data: ${err.message}`);
    refreshDatasetStatus(); // Revert to the original status if generation fails
  }
}

// User-related functions
function showUser(u) {
  if (!u || !u.user_id) { showLoginPage(); return; }
  __currentUser = u;
  const el = $("userNameDisplay");
  if (el) el.textContent = u.name ?? `User (${u.user_id.substring(0,6)}...)`;
  localStorage.setItem(USER_ID_KEY, u.user_id);
  hydrateFavSet().then(() => {
    showMainApp();
  });
}


async function createUser() {
  const payload = {
    name: val("name"),
    group_size: Number(val("group_size") || 1),
    preferred_environment: val("preferred_environment"),
    budget_min: Number(val("budget_min") || 0),
    budget_max: Number(val("budget_max") || 1e12),
  };
  if (!payload.name) return alert("Name is required.");

  const res = await fetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

  alert(`Account created! Your User ID is: ${data.user_id}\nIt has been saved to your browser for auto-login.`);
  showUser(data); // <-- existing line

  //  NEW: save the user_id locally for the user 

// After showUser(data);
try {
  const r = await fetch("/api/save_userid_to_desktop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: data.user_id, name: data.name || "" }),
  });
  const j = await r.json();
  if (!r.ok || !j.ok) {
    console.warn("Desktop save failed:", j.error || r.status);
    // optional: fall back to the browser download you already implemented
  } else {
    // optional: toast/alert for confirmation
    console.log("Saved user id file to:", j.path);
  }
} catch (err) {
  console.warn("Desktop save request failed:", err);
}
}

async function loginWithId(id) {
    if (!id) return;
    const res = await fetch(`/api/users/${encodeURIComponent(id)}`);
    const data = await res.json();
    if (!res.ok || data.error) {
        localStorage.removeItem(USER_ID_KEY);
        throw new Error(data.error || `HTTP ${res.status}`);
    }
    showUser(data); // This will now store the full profile and update the UI
}

/* NEW: Profile Edit and Logout Logic  */
function openEditProfileModal() {
    if (!__currentUser) return;
    // Populate modal with current user data
    $('edit_name').value = __currentUser.name || '';
    $('edit_group_size').value = __currentUser.group_size || 1;
    $('edit_preferred_environment').value = __currentUser.preferred_environment || '';
    $('edit_budget_min').value = __currentUser.budget_min || 0;
    $('edit_budget_max').value = __currentUser.budget_max || 500;

    $('editProfileModal').style.display = 'flex';
}

function closeEditProfileModal() {
    $('editProfileModal').style.display = 'none';
}

async function saveProfile() {
    if (!__currentUser) return;

    const payload = {
        name: val("edit_name"),
        group_size: Number(val("edit_group_size")),
        preferred_environment: val("edit_preferred_environment"),
        budget_min: Number(val("edit_budget_min")),
        budget_max: Number(val("edit_budget_max")),
    };

    try {
        const res = await fetch(`/api/users/${__currentUser.user_id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.error || `HTTP ${res.status}`);
        }

        const updatedUser = await res.json();
        alert('Profile updated successfully!');
        showUser(updatedUser); // Refresh the global user object and UI
        closeEditProfileModal();

    } catch (err) {
        alert(`Failed to update profile: ${err.message}`);
    }
}


/*  Favorites & Recommend */
async function loadFavorites() {
  const userId = __currentUser?.user_id;
  if (!userId) return alert("Create/select a user first.");
  const r = await fetch(`/api/favorites/${encodeURIComponent(userId)}`);
  if (!r.ok) return alert(`Favorites failed (${r.status})`);
  const j = await r.json();
  const items = j.favorites || [];
  renderCards(items);
  const n = items.length;
  if ($("pageInfo")) $("pageInfo").textContent = `My Favorites — ${n} saved`;
}
async function onRecommend() {
  const userId = __currentUser?.user_id;
  if (!userId) return alert("Create/select a user first.");
  const r = await fetch(`/api/recommend?user_id=${encodeURIComponent(userId)}&limit=${limit}`);
  if (!r.ok) return alert(`Recommend failed (${r.status})`);
  const j = await r.json();
  renderCards(j.items || []);
  const shown = (j.items || []).length;
  if ($("pageInfo")) $("pageInfo").textContent = `Recommended for you — showing ${shown} of ${j.total ?? shown}`;
}
function todayISO() { return new Date().toISOString().slice(0, 10); }

window.__favSet = new Set();
async function hydrateFavSet() {
  const userId = __currentUser?.user_id;
  if (!userId) { window.__favSet = new Set(); return; }
  try {
    const r = await fetch(`/api/favorites/${encodeURIComponent(userId)}`);
    if (!r.ok) throw new Error();
    const j = await r.json();
    window.__favSet = new Set((j.favorite_ids || []).map(String));
  } catch {
    window.__favSet = new Set();
  }
}

/*  Booking  */
function openBooking(it) {
  $("book_listing_id").value = it.listing_id;
  $("book_title").textContent = it.name || `Listing #${it.listing_id}`;
  $("book_checkin").value = todayISO();
  $("book_checkout").value = "";
  $("book_status").textContent = "";
  $("bookModal").style.display = "flex";
}
function closeBooking() { $("bookModal").style.display = "none"; }

async function checkAvailability() {
  const lid = $("book_listing_id").value;
  const start = $("book_checkin").value;
  const end = $("book_checkout").value;
  if (!lid || !start || !end) return;
  if (start >= end) {
      $("book_status").textContent = "Check-out must be after check-in.";
      $("confirmBookBtn").disabled = true;
      return;
  }
  const r = await fetch(`/api/availability?listing_id=${encodeURIComponent(lid)}&start=${start}&end=${end}`);
  if (!r.ok) return $("book_status").textContent = `Check failed (${r.status})`;
  const j = await r.json();
  $("book_status").textContent = j.available ? "Available ✅" : "Not available ❌";
  $("confirmBookBtn").disabled = !j.available;
}

async function confirmBooking() {
  const userId = __currentUser?.user_id;
  if (!userId) return alert("Select/create a user first.");
  const payload = {
    user_id: userId,
    listing_id: $("book_listing_id").value,
    check_in: $("book_checkin").value,
    check_out: $("book_checkout").value,
  };
  const r = await fetch("/api/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const j = await r.json();
  if (!r.ok) return alert(j.error || `Booking failed (${r.status})`);
  alert("Booked successfully! Booking ID: " + j.booking.id);
  closeBooking();
}

/*  'My Bookings' Modal  */
async function openMyBookings() {
    const userId = __currentUser?.user_id;
    if (!userId) return alert("Please log in to see your bookings.");

    const r = await fetch(`/api/bookings?user_id=${encodeURIComponent(userId)}`);
    if (!r.ok) return alert(`Failed to fetch bookings (${r.status})`);
    const j = await r.json();

    const listEl = $('bookingsList');
    listEl.innerHTML = ''; // Clear previous content

    if (!j.items || j.items.length === 0) {
        listEl.innerHTML = '<p class="muted">You have no bookings.</p>';
    } else {
        j.items.forEach(booking => {
            const details = booking.listing_details || { name: 'Unknown Listing' };
            const item = document.createElement('div');
            item.className = 'booking-item';
            item.innerHTML = `
                <h4>${details.name}</h4>
                <p><strong>Location:</strong> ${details.location || details.name}</p>
                <p><strong>Dates:</strong> ${booking.start} to ${booking.end}</p>
                <p><strong>Booking ID:</strong> ${booking.id}</p>
                <button class="cancel-booking-btn danger" data-booking-id="${booking.id}">Cancel Booking</button>
            `;
            listEl.appendChild(item);
        });
    }
    $('bookingsModal').style.display = 'flex';
}

async function cancelBooking(bookingId) {
    const userId = __currentUser?.user_id;
    if (!confirm(`Are you sure you want to cancel booking ${bookingId}?`)) return;

    const r = await fetch(`/api/bookings/${bookingId}?user_id=${userId}`, { method: 'DELETE' });
    if (!r.ok) {
        alert(`Failed to cancel booking (${r.status})`);
        return;
    }
    const j = await r.json();
    if (j.removed) {
        alert('Booking cancelled successfully.');
        openMyBookings(); // Refresh the bookings list
    } else {
        alert('Cancellation failed. The booking may not exist or does not belong to you.');
    }
}

/*  Prompt modal  */
function openPromptModal() { $("promptModal").style.display="flex"; $("syn_prompt")?.focus(); }
function closePromptModal() { $("promptModal").style.display="none"; }


/*  Wire up */
document.addEventListener("DOMContentLoaded", () => {
  
  // users
  $("loginBtn")?.addEventListener("click", (e) => {
    e.preventDefault();
    loginWithId(val('login-user-id')).catch((err) => alert(`Login failed: ${err.message}`));
  });
  $("createUserBtn")?.addEventListener("click", (e) => {
    e.preventDefault();
    createUser().catch((err) => alert(`Create failed: ${err.message}`));
  });
  $('showCreateUserLink')?.addEventListener('click', (e) => {
    e.preventDefault();
    $('login-box').style.display = 'none';
    $('create-user-box').style.display = 'block';
  });
  $('showLoginLink')?.addEventListener('click', (e) => {
    e.preventDefault();
    $('login-box').style.display = 'block';
    $('create-user-box').style.display = 'none';
  });

 // filters/listings
 $("searchBtn")?.addEventListener("click", () => fetchListings(1));
  $("prevBtn")?.addEventListener("click", () => fetchListings(Math.max(1, currentPage - 1)));
  $("nextBtn")?.addEventListener("click", () => fetchListings(currentPage + 1));
  $("loadFavBtn")?.addEventListener("click", loadFavorites);
  $("myBookingsBtn")?.addEventListener("click", openMyBookings);
  $("recBtn")?.addEventListener("click", onRecommend);

// dataset controls
  $("useOriginalBtn")?.addEventListener("click", useOriginal);
  $("useSyntheticBtn")?.addEventListener("click", generateDataFromPrompt);
  // The listener for addSyntheticBtn has been removed as the button is obsolete.

  // user menu and modal 
  $('logoutBtn')?.addEventListener('click', showLoginPage);
  $('editProfileBtn')?.addEventListener('click', openEditProfileModal);
  $('saveProfileBtn')?.addEventListener('click', saveProfile);
  $('cancelEditProfileBtn')?.addEventListener('click', closeEditProfileModal);

  // prompt modal
  $("openPromptBtn")?.addEventListener("click", openPromptModal);
  $("cancelPromptBtn")?.addEventListener("click", closePromptModal);
  // This now correctly calls the new LLM function.
  $("savePromptBtn")?.addEventListener("click", generateDataFromPrompt);

  // booking modal
  $("bookCancelBtn")?.addEventListener("click", closeBooking);
  $("checkAvailBtn")?.addEventListener("click", checkAvailability);
  $("confirmBookBtn")?.addEventListener("click", confirmBooking);

  // My Bookings modal
  $("bookingsCloseBtn")?.addEventListener('click', () => $('bookingsModal').style.display = 'none');
  $('bookingsList').addEventListener('click', (e) => {
      if (e.target.classList.contains('cancel-booking-btn')) {
          const bookingId = e.target.dataset.bookingId;
          cancelBooking(bookingId);
      }
  });


  // Initial UI state - try auto-login first
  const savedUserId = localStorage.getItem(USER_ID_KEY);
  if (savedUserId) {
    loginWithId(savedUserId).catch(() => {
        // If auto-login fails, show the login page
        showLoginPage();
    });
  } else {
      showLoginPage();
  }
});