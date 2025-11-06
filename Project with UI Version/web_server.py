# web_server.py
from __future__ import annotations
from flask import Flask, request, jsonify, render_template, send_file
from pathlib import Path
from configs import CLEANED_LISTING_CSV_PATH, LLM_API_KEY
import io, csv, datetime, random, math
import json, uuid # Ensure json and uuid are imported for the new endpoint
from flask import request, jsonify
from pathlib import Path
import datetime
import traceback
import re

# real modules or fallbacks 
try:
    from configs import LLM_API_KEY
    from synthetic_data import generate_synthetic_listings, extract_json
    LLM_AVAILABLE = True
except ImportError:
    print("Warning: LLM configs or synthetic_data module not found. LLM features will be disabled.")
    LLM_API_KEY = None
    generate_synthetic_listings = None
    extract_json = None
    LLM_AVAILABLE = False

try:
    from user_crud import load_users, create_user, find_user_by_id, save_users
except Exception:
    # Fallback to project-relative data/users.json if the absolute path does not exist
    try:
        BASE_DIR = Path(__file__).resolve().parent
        DATA_DIR = BASE_DIR / "data"
        DATA_DIR.mkdir(exist_ok=True)
    except Exception:
        DATA_DIR = Path(".")
    
    USERS_FILE = DATA_DIR / "users.json"
    
    def _read_users():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8")) if USERS_FILE.exists() else []
        except Exception:
            return []
    def _write_users(data):
        try:
            USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            USERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass # Or log the error
    def save_users(users): # Add fallback save_users
        _write_users([as_dict(u) for u in users])

    def load_users():
        users = _read_users(); print(f"Loaded {len(users)} user profiles from {USERS_FILE}."); return users
    def create_user(users, name, group_size, preferred_env, budget_min, budget_max):
        u = {"user_id": str(uuid.uuid4()), "name": name, "group_size": int(group_size),
             "preferred_environment": preferred_env, "budget_min": float(budget_min), "budget_max": float(budget_max)}
        users.append(u); _write_users(users); return u
    def find_user_by_id(users, user_id): return next((u for u in users if u.get("user_id")==user_id), None)
# optional recommender
try:
    from recommender import get_recommendations as _recommend_fn  # expects (listings, user, k) -> list
except Exception:
    _recommend_fn = None

try:
    from listings import load_listings, filter_combined, sort_listings, find_listing_by_id
except Exception:
    import pandas as pd
    def _first_existing(paths):
        for p in paths:
            pth = Path(p)
            if pth.exists(): return pth
        return None
    CSV_PATH = _first_existing([
       Path(__file__).resolve().parent / "cleaned_listings.csv",
       CLEANED_LISTING_CSV_PATH
    ])
    def load_listings():
        if CSV_PATH and CSV_PATH.exists():
            df = pd.read_csv(CSV_PATH)
            recs = df.to_dict(orient="records")
            # Ensure listing_id is a string for consistency
            for i, r in enumerate(recs): r.setdefault("listing_id", str(i+1))
            print(f"Loaded {len(recs)} listings from {CSV_PATH}.")
            return recs
        print("No listings CSV found; returning empty list."); return []
    def filter_combined(listings, environment, budget_min, budget_max, accommodates):
        env = (environment or "").strip().lower()
        out = []
        for r in listings:
            tags = f"{str(r.get('tags',''))} {str(r.get('preferred_environment',''))}".lower()
            if env and env not in tags: continue
            price = float(r.get("price", 1e18))
            if budget_min is not None and price < float(budget_min): continue
            if budget_max is not None and price > float(budget_max): continue
            if accommodates is not None and int(r.get("accommodates",0)) < int(accommodates): continue
            out.append(r)
        return out
    def sort_listings(listings, sort_by="price", ascending=True):
        return sorted(listings, key=lambda x: x.get(sort_by, 0), reverse=not ascending)
    def find_listing_by_id(listings, listing_id):
        # Compare as strings
        for r in listings:
            try:
                if str(r.get("listing_id")) == str(listing_id): return r
            except: pass
        return None

try:
    from favourites import get_user_favorites, add_favorite, remove_favorite
except Exception:
    try:
        BASE_DIR = Path(__file__).resolve().parent
        DATA_DIR = BASE_DIR / "data"
        DATA_DIR.mkdir(exist_ok=True)
    except Exception:
        DATA_DIR = Path(".")
    FAV_FILE = DATA_DIR / "favorites.json"


    def _read_favs():
        try:
            if not FAV_FILE.exists():
                return {}
            return json.loads(FAV_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}


    def _write_favs(d):
        try:
            FAV_FILE.parent.mkdir(parents=True, exist_ok=True)
            FAV_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # or log


    def _normalize_favs(raw):
        """
        Accepts:
          - dict: {"user_id": ["lid1","lid2",...]}
          - list: [{"user_id": "...", "listing_id": "..."}, ...]  (legacy)
        Returns dict in the new canonical form with all ids as strings.
        """
        if isinstance(raw, dict):
            return {str(uid): [str(lid) for lid in (lst or [])] for uid, lst in raw.items()}
        if isinstance(raw, list):
            out = {}
            for row in raw:
                uid = str(row.get("user_id"))
                lid = str(row.get("listing_id"))
                if uid and lid:
                    out.setdefault(uid, []).append(lid)
            return out
        return {}


    def get_user_favorites(user_id):
        data = _normalize_favs(_read_favs())
        return data.get(str(user_id), [])


    def add_favorite(user_id, listing_id):
        data = _normalize_favs(_read_favs())
        uid = str(user_id);
        lid = str(listing_id)
        data.setdefault(uid, [])
        if lid not in data[uid]:
            data[uid].append(lid)
            _write_favs(data)  # auto-upgrades file to dict format
            return True
        return False


    def remove_favorite(user_id, listing_id):
        data = _normalize_favs(_read_favs())
        uid = str(user_id);
        lid = str(listing_id)
        if uid in data and lid in data[uid]:
            data[uid].remove(lid)
            if not data[uid]:
                del data[uid]
            _write_favs(data)  # stays in dict format
            return True
        return False
# Bookings (fallback JSON store)
try:
    from bookings import list_user_bookings, add_booking, get_listing_bookings, remove_booking
except Exception:
    try:
        BASE_DIR = Path(__file__).resolve().parent
        DATA_DIR = BASE_DIR / "data"
        DATA_DIR.mkdir(exist_ok=True)
    except Exception:
        DATA_DIR = Path(".")
    BOOK_FILE = DATA_DIR / "bookings.json"

    def _read_bookings():
        if BOOK_FILE.exists():
            try:
                return json.loads(BOOK_FILE.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _write_bookings(data):
        try:
            BOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
            BOOK_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def list_user_bookings(user_id):
        return [b for b in _read_bookings() if str(b.get("user_id")) == str(user_id)]

    def get_listing_bookings(listing_id):
        lid = str(listing_id)
        return [b for b in _read_bookings() if str(b.get("listing_id")) == lid]

    def _overlap(a_start, a_end, b_start, b_end):
        # All dates as ISO YYYY-MM-DD; treat [start, end) (checkout not included)
        return (a_start < b_end) and (a_end > b_start)

    def add_booking(user_id, listing_id, start, end):
        if start >= end:
            return None, "Invalid date range"
        data = _read_bookings()
        # conflicts on the same listing
        for b in data:
            if str(b.get("listing_id")) == str(listing_id):
                if _overlap(start, end, b["start"], b["end"]):
                    return None, "Requested dates are not available"
        newb = {
            "id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "listing_id": str(listing_id),
            "start": start,
            "end": end,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        data.append(newb); _write_bookings(data)
        return newb, None

    def remove_booking(booking_id, user_id=None):
        data = _read_bookings()
        out = []; removed = False
        for b in data:
            # Match booking ID and optionally user ID
            if str(b.get("id")) == str(booking_id):
                if user_id is None or str(b.get("user_id")) == str(user_id):
                    removed = True
                    continue
            out.append(b)
        if removed: _write_bookings(out)
        return removed

# helpers 
def as_dict(x): return x.to_dict() if hasattr(x, "to_dict") else x
def _get(obj, key, default=None): return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
def _to_float(v, default=None):
    try:
        if v is None: return default
        if isinstance(v, (int, float)): f = float(v); return f if math.isfinite(f) else default
        s = str(v).strip().lower()
        if s in {"", "nan", "inf", "-inf"}: return default
        f = float(s); return f if math.isfinite(f) else default
    except: return default
def _to_int(v, d=None):
    try:
        if v is None: return d
        if isinstance(v, bool): return int(v)
        return int(float(v))
    except: return d
def rows_as_dicts(rows):
    for r in rows: yield as_dict(r) if not isinstance(r, dict) else r
def json_sanitize(obj):
    if isinstance(obj, dict): return {k: json_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)): return [json_sanitize(v) for v in obj]
    try:
        if obj != obj: return None
    except: pass
    if isinstance(obj, float) and math.isinf(obj): return None
    t = type(obj).__name__
    if t in {"int8","int16","int32","int64","uint8","uint16","uint32","uint64"}:
        try: return int(obj)
        except: pass
    if t in {"float16","float32","float64"}:
        try:
            v = float(obj);
            if v != v or math.isinf(v): return None
            return v
        except: return None
    if isinstance(obj, (str, int, bool)) or obj is None: return obj
    if hasattr(obj, "to_dict"): return json_sanitize(obj.to_dict())
    return str(obj)
def sort_safe(listings, sort_by, ascending):
    try: return sort_listings(listings, sort_by=sort_by, ascending=ascending)
    except TypeError:
        try: return sort_listings(listings, by_what=sort_by, ascending=ascending)
        except: pass
    except: pass
    def keyer(x):
        v = _get(x, sort_by, 0)
        return _to_float(v, _to_int(v, 0))
    return sorted(listings, key=keyer, reverse=not ascending)
def filter_safe(listings, environment, min_price, max_price, accommodates):
    try:
        return filter_combined(listings, environment=environment, min_price=min_price, max_price=max_price, min_accommodates=accommodates)
    except TypeError:
        try: return filter_combined(listings, environment=environment, budget_min=min_price, budget_max=max_price, accommodates=accommodates)
        except TypeError:
            try: return filter_combined(listings, environment, min_price, max_price, accommodates)
            except: pass
    except: pass
    env = (environment or "").strip().lower()
    def ok(r):
        if env:
            hay = " ".join(str(x) for x in [_get(r,"tags",""), _get(r,"preferred_environment",""), _get(r,"name",""), _get(r,"property_type","")]).lower()
            if env not in hay: return False
        p = _to_float(_get(r,"price"))
        if min_price is not None and (p is None or p < float(min_price)): return False
        if max_price is not None and (p is None or p > float(max_price)): return False
        acc = _to_int(_get(r,"accommodates"))
        if accommodates is not None and (acc is None or acc < int(accommodates)): return False
        return True
    return [r for r in listings if ok(r)]

def _fallback_recommend(user, listings, k=12):
    """Cheap, robust recommender using user prefs & simple scoring."""
    env = (user.get("preferred_environment") or "").lower()
    gsize = int(user.get("group_size") or 1)
    bmin  = float(user.get("budget_min") or 0)
    bmax  = float(user.get("budget_max") or 1e12)
    recs = []
    for r in rows_as_dicts(listings):
        price = _to_float(r.get("price"), 0)
        rating = _to_float(r.get("review_rating"), 0)
        acc = _to_int(r.get("accommodates"), 0)
        if price and (price < bmin or price > bmax): continue
        if acc and acc < gsize: continue
        tags = " ".join(str(x) for x in [r.get("tags",""), r.get("preferred_environment",""), r.get("location",""), r.get("property_type","")]).lower()
        score = 0.0
        if env and env in tags: score += 3.0
        if rating: score += (rating - 3.5) * 2.0
        if price:  score += max(0, (bmax - price) / max(1.0, bmax-bmin or 1.0))
        score += 0.2 * min(acc or 0, gsize)
        recs.append((score, r))
    recs.sort(key=lambda t: t[0], reverse=True)
    return [json_sanitize(as_dict(x)) for _, x in recs[:k]]

# app + dataset state 
app = Flask(__name__, static_folder="static", template_folder="templates")
USERS = load_users() or []
ORIGINAL_LISTINGS = load_listings() or []
LISTINGS = ORIGINAL_LISTINGS
ACTIVE_SOURCE = "original"
SYNTHETIC_LIST = []

def get_active_listings(): return LISTINGS
def set_original_active():
    global LISTINGS, ACTIVE_SOURCE
    LISTINGS = ORIGINAL_LISTINGS; ACTIVE_SOURCE = "original"
def set_synthetic_active(rows):
    global LISTINGS, ACTIVE_SOURCE, SYNTHETIC_LIST
    SYNTHETIC_LIST = list(rows); LISTINGS = SYNTHETIC_LIST; ACTIVE_SOURCE = "synthetic"

# pages 
@app.route("/")
def index():
    title = request.args.get("title") or "Summer Stays Recommender"
    try:
        html = (Path(app.template_folder)/"index.html").read_text(encoding="utf-8")
        html = html.replace("<h1>Summer Stays Recommender</h1>", f"<h1>{title}</h1>")
        return html
    except Exception:
        return render_template("index.html")

# users 
@app.route("/api/users", methods=["GET"])
def api_users(): return jsonify([json_sanitize(as_dict(u)) for u in USERS])

@app.route("/api/users", methods=["POST"])
def api_users_create():
    d = request.get_json(force=True)
    u = create_user(
        USERS,
        d.get("name","").strip(),
        int(d.get("group_size", 1)),
        d.get("preferred_environment","").strip(),
        float(d.get("budget_min", 0)),
        float(d.get("budget_max", 1e12)),
    )
    return jsonify(as_dict(u)), 201

@app.route("/api/users/<user_id>", methods=["GET"])
def api_users_get(user_id):
    u = find_user_by_id(USERS, user_id)
    if not u:
        u = {"user_id": str(user_id), "name": f"User {user_id}", "group_size": None,
             "preferred_environment": None, "budget_min": None, "budget_max": None}
    return jsonify(json_sanitize(as_dict(u)))

@app.route("/api/users/<user_id>", methods=["PUT"])
def api_user_update(user_id):
    # find_user_by_id now returns a User OBJECT
    user_to_update = find_user_by_id(USERS, user_id)
    if not user_to_update:
        return jsonify({"error": "User not found"}), 404
    
    data = request.get_json(force=True)
    
    user_to_update.name = data.get("name", user_to_update.name)
    user_to_update.group_size = int(data.get("group_size", user_to_update.group_size))
    user_to_update.preferred_environment = data.get("preferred_environment", user_to_update.preferred_environment)
    user_to_update.budget_min = float(data.get("budget_min", user_to_update.budget_min))
    user_to_update.budget_max = float(data.get("budget_max", user_to_update.budget_max))
    
    # This function correctly handles saving a list of User objects
    save_users(USERS)
    
    # as_dict will correctly convert the updated object to a dictionary for the JSON response
    return jsonify(json_sanitize(as_dict(user_to_update)))


# listings
@app.route("/api/listings", methods=["GET"])
def api_listings():
    # Get filter parameters from the request
    env_keyword = request.args.get("environment", "").lower().strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    accommodates = request.args.get("accommodates", type=int)
    
    # Get sorting and pagination parameters
    sort_by = request.args.get("sort_by", default="price")
    ascending = request.args.get("ascending", default="true").lower() != "false"
    limit = request.args.get("limit", type=int, default=12)
    page = request.args.get("page", type=int, default=1)
    
    # get_active_listings() now returns a list of Listing OBJECTS
    base_listings = get_active_listings() or []
    
    filtered_listings = list(base_listings)

    # Apply filters using object attribute access
    if env_keyword:
        filtered_listings = [
            l for l in filtered_listings 
            if env_keyword in str(getattr(l, 'tags', '')).lower() or 
               env_keyword in str(getattr(l, 'name', '')).lower() or
               env_keyword in str(getattr(l, 'location', '')).lower()
        ]

    if min_price is not None:
        filtered_listings = [l for l in filtered_listings if float(getattr(l, 'price', 0)) >= min_price]

    if max_price is not None:
        filtered_listings = [l for l in filtered_listings if float(getattr(l, 'price', 0)) <= max_price]

    if accommodates is not None:
        filtered_listings = [l for l in filtered_listings if int(getattr(l, 'accommodates', 0)) >= accommodates]
        
    # Apply sorting using object attribute access 
    if sort_by:
        try:
            filtered_listings.sort(key=lambda l: getattr(l, sort_by, 0) or 0, reverse=not ascending)
        except TypeError:
            filtered_listings.sort(key=lambda l: str(getattr(l, sort_by, '')), reverse=not ascending)

    # Apply pagination
    total = len(filtered_listings)
    start = max(0, (page - 1) * limit)
    end = start + limit
    paginated_items_objects = filtered_listings[start:end]
    
    # Convert the final list of objects back to dictionaries for the JSON response
    items_as_dicts = [item.to_dict() for item in paginated_items_objects]
    
    return jsonify({
        "total": total, 
        "page": page, 
        "limit": limit, 
        "items": json_sanitize(items_as_dicts)
    })

@app.route("/api/listings/<listing_id>", methods=["GET"])
def api_listing_get(listing_id):
    listing = find_listing_by_id(get_active_listings(), listing_id)
    if listing: return jsonify(json_sanitize(as_dict(listing)))
    return jsonify({"error":"Listing not found"}), 404


@app.route("/api/recommend", methods=["GET"])
def api_recommend():
    user_id = (request.args.get("user_id") or "").strip()
    k = int(request.args.get("limit", 12))

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    user = find_user_by_id(USERS, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not _recommend_fn:
        return jsonify({"error": "Recommender module is not available"}), 500

    # Convert user object and listing objects to simple dictionaries
    user_dict = as_dict(user)
    listings_list_of_dicts = [as_dict(l) for l in get_active_listings() or []]

    try:
        # Call the recommender with dictionaries
        recommendations = _recommend_fn(user_dict, listings_list_of_dicts, top_n=k)
        return jsonify({"total": len(listings_list_of_dicts), "items": json_sanitize(recommendations)})
    except Exception as e:
        print(f"--- RECOMMENDATION API ERROR ---")
        print(f"Error: {e}")
        traceback.print_exc()
        print(f"-----------------------------")
        return jsonify({"error": "An internal error occurred while generating recommendations."}), 500

@app.route("/api/favorites/<user_id>", methods=["GET"])
def api_favorites_list(user_id):
    fav_ids = {str(fid) for fid in get_user_favorites(user_id)}
    if not fav_ids: return jsonify({"user_id": user_id, "favorite_ids": [], "favorites": []})
    expanded = [json_sanitize(as_dict(r)) for r in get_active_listings() if str(as_dict(r).get("listing_id")) in fav_ids]
    return jsonify(json_sanitize({"user_id": user_id, "favorite_ids": list(fav_ids), "favorites": expanded}))

@app.route("/api/favorites", methods=["POST"])
def api_favorites_add():
    d = request.get_json(force=True)
    user_id, listing_id = d.get("user_id"), str(d.get("listing_id"))
    if not (user_id and listing_id): return jsonify({"error": "user_id and listing_id required"}), 400
    ok = add_favorite(user_id, listing_id)
    return jsonify({"added": bool(ok)})

@app.route("/api/favorites", methods=["DELETE"])
def api_favorites_remove():
    d = request.get_json(force=True)
    user_id, listing_id = d.get("user_id"), str(d.get("listing_id"))
    if not (user_id and listing_id): return jsonify({"error": "user_id and listing_id required"}), 400
    ok = remove_favorite(user_id, listing_id)
    return jsonify({"removed": bool(ok)})
    

def _listing_exists_anywhere(listing_id):
    lid = str(listing_id)
    # check both original and synthetic (active) sets
    for r in list(rows_as_dicts(ORIGINAL_LISTINGS)) + list(rows_as_dicts(LISTINGS)):
        try:
            if str(as_dict(r).get("listing_id")) == lid:
                return True
        except Exception:
            pass
    return False

@app.route("/api/availability", methods=["GET"])
def api_availability():
    listing_id = request.args.get("listing_id")
    start = request.args.get("start")  # YYYY-MM-DD
    end = request.args.get("end")
    if not (listing_id and start and end):
        return jsonify({"error": "listing_id, start, end required"}), 400
    if not _listing_exists_anywhere(listing_id):
        return jsonify({"error": "Listing not found"}), 404

    conflicts = []
    for b in get_listing_bookings(listing_id):
        # overlap?
        if (start < b["end"]) and (end > b["start"]):
            conflicts.append(b)
    return jsonify({"available": len(conflicts) == 0, "conflicts": conflicts})


@app.route("/api/book", methods=["POST"])
def api_book():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    listing_id = data.get("listing_id")
    # Accept multiple keys and provide defaults if missing
    start = data.get("check_in") or data.get("start")
    end = data.get("check_out") or data.get("end")
    if not user_id or not listing_id:
        return jsonify({"error": "user_id and listing_id required"}), 400
    # Soft user validation: allow ephemeral users if users.json is missing/empty
    try:
        user_found = bool(find_user_by_id(USERS, user_id))
    except Exception:
        user_found = False
    if not _listing_exists_anywhere(listing_id):
        return jsonify({"error": "Listing not found"}), 404
    # Default dates if not provided
    if not (start and end):
        today = datetime.date.today()
        start = today.isoformat()
        end = (today + datetime.timedelta(days=2)).isoformat()
    if start >= end:
        return jsonify({"error": "Invalid date range"}), 400
    booking, err = add_booking(user_id, listing_id, start, end)
    if err:
        return jsonify({"error": err}), 409
    return jsonify({"ok": True, "booking": booking})

@app.route("/api/bookings", methods=["GET"])
def api_user_bookings():
    """
    API endpoint to return all bookings for a specific user, including listing details.
    URL Parameter:
        - user_id: ID of the user whose bookings are being retrieved
    Returns:
        - JSON response with a list of bookings, each optionally including listing metadata
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    # Retrieve all bookings for the user
    bookings = list_user_bookings(user_id)
    listings = get_active_listings()  # Get available listings once

    enriched_bookings = []
    for booking in bookings:
        # Find the corresponding listing for this booking
        listing = find_listing_by_id(listings, booking.get("listing_id"))

        booking_info = booking.copy()
        if listing:
            booking_info["listing_details"] = as_dict(listing)
        else:
            # If listing not found (deleted or inactive), provide fallback data
            booking_info["listing_details"] = {
                "name": "Listing not found",
                "location": "N/A",
                "listing_id": booking.get("listing_id")
            }

        enriched_bookings.append(booking_info)

    return jsonify({"items": json_sanitize(enriched_bookings)})


@app.route("/api/bookings/<booking_id>", methods=["DELETE"])
def api_cancel_booking(booking_id):
    # user_id is required to ensure a user can only cancel their own bookings
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required for authorization"}), 401
        
    ok = remove_booking(booking_id, user_id=user_id)
    return jsonify({"removed": ok})

#  dataset switching
@app.route("/api/dataset/status", methods=["GET"])
def api_dataset_status(): return jsonify({"source": ACTIVE_SOURCE, "count": len(get_active_listings() or [])})

@app.route("/api/dataset/use_original", methods=["POST"])
def api_dataset_use_original():
    set_original_active()
    return jsonify({"ok": True, "source": ACTIVE_SOURCE, "count": len(LISTINGS)})

def _build_synthetic_rows(include_real: bool, n_fake: int):
    original_dicts = list(rows_as_dicts(ORIGINAL_LISTINGS))
    prices = [_to_float(r.get("price")) for r in original_dicts]; prices = [p for p in prices if p is not None] or [150.0]
    mean_price, min_p, max_p = sum(prices)/len(prices), min(prices), max(prices)
    ratings = [_to_float(r.get("review_rating")) for r in original_dicts]; ratings = [x for x in ratings if x is not None] or [4.6]
    mean_rating = sum(ratings)/len(ratings)

    property_types = [r.get("property_type") or r.get("type") for r in original_dicts if (r.get("property_type") or r.get("type"))] or ["apartment"]
    locations = [r.get("location") for r in original_dicts if r.get("location")] or ["Nowhere, XX"]

    ams = []
    for r in original_dicts:
        am = r.get("amenities")
        if isinstance(am, list): ams.extend(am)
        elif isinstance(am, str): ams.extend([p.strip() for p in am.split(",") if p.strip()])
    amenity_pool = sorted({a for a in ams if a}) or ["Wifi","Kitchen","Free parking","Air conditioning","Washer"]

    def synth_row(i):
        price = max(min_p, min(max_p, mean_price*(0.6 + random.random())))
        rating = max(3.5, min(5.0, mean_rating + (random.random()-0.5)*0.6))
        am = ", ".join(random.sample(amenity_pool, k=min(len(amenity_pool), random.randint(3,8))))
        return {
            "listing_id": f"SYN-{i}",
            "name": f"Synthetic Stay #{i}",
            "location": random.choice(locations),
            "property_type": random.choice(property_types),
            "accommodates": random.randint(1,10),
            "price": round(price,2),
            "review_rating": round(rating,2),
            "amenities": am,
        }

    syn = [synth_row(i+1) for i in range(n_fake)]
    return (original_dicts + syn) if include_real else syn

# API endpoint for LLM-based data generation.
@app.route("/api/dataset/use_synthetic", methods=["POST"])
def api_dataset_use_synthetic():
    if not LLM_AVAILABLE:
        return jsonify({"error": "LLM functionality is not configured on the server."}), 503

    payload = request.get_json(force=True)
    user_prompt = payload.get("prompt", "")
    include_real = payload.get("include_real", True)

    if not user_prompt:
        return jsonify({"error": "Prompt cannot be empty."}), 400

    num_to_generate = 5
    match = re.search(r'\d+', user_prompt)
    if match:
        num_to_generate = int(match.group(0))

    final_prompt = (
        f"{user_prompt}\n\n"
        f"Generate exactly {num_to_generate} listings based on the request above.\n"
        "Output ONLY a valid JSON array of objects. Each object must have these keys: "
        "'name', 'location', 'property_type', 'accommodates', 'amenities', "
        "'price', 'min_nights', 'max_nights', 'review_rating', 'tags'."
    )
    
    print(f"Sending prompt to LLM (requesting {num_to_generate} listings)...")

    try:
        #  Call the LLM to generate data.
        raw_output = generate_synthetic_listings(final_prompt, LLM_API_KEY)
        synthetic_dicts = extract_json(raw_output)
        
        if not isinstance(synthetic_dicts, list):
            raise ValueError("LLM did not return a valid JSON array.")

        print(f"Successfully received {len(synthetic_dicts)} listings from LLM.")

   # Merge datasets by ensuring all data are dictionaries first.
        # Convert ORIGINAL_LISTINGS (which are objects) to a list of dictionaries.
        original_dicts = [as_dict(l) for l in ORIGINAL_LISTINGS]
        
        if include_real:
            merged_list = original_dicts + synthetic_dicts
        else:
            merged_list = synthetic_dicts

        # Update the active dataset, re-indexing to ensure unique IDs.
        # This loop now safely operates on a list containing ONLY dictionaries.
        for i, row in enumerate(merged_list):
            row['listing_id'] = i
        
        set_synthetic_active(merged_list)

        return jsonify({"ok": True, "source": ACTIVE_SOURCE, "count": len(LISTINGS)})

    except Exception as e:
        print("ERROR during LLM generation or processing:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

#  synthetic CSV download 
@app.route("/api/synthetic_csv", methods=["POST"])
def api_synthetic_csv():
    d = request.get_json(silent=True) or {}
    include_real = bool(d.get("include_real", True))
    n_fake = max(0, min(int(d.get("fake_rows", 100)), 5000))

    original_dicts = list(rows_as_dicts(ORIGINAL_LISTINGS))
    generated = _build_synthetic_rows(include_real, n_fake)

    preferred = ["listing_id","name","location","property_type","accommodates","price","review_rating","amenities","tags"]
    keys, seen = list(preferred), set(preferred)
    for r in original_dicts:
        for k in r.keys():
            if k not in seen: keys.append(k); seen.add(k)

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in generated: w.writerow({k: r.get(k) for k in keys})

    out = io.BytesIO(buf.getvalue().encode("utf-8"))
    fname = f"synthetic_listings_{'withreal' if include_real else 'synthetic'}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(out, mimetype="text/csv", as_attachment=True, download_name=fname)

@app.post("/api/save_userid_to_desktop")
def api_save_userid_to_desktop():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id") or "").strip()
    name = str(data.get("name") or "").strip()
    if not user_id:
        return jsonify({"ok": False, "error": "user_id required"}), 400

    # Cross-platform Desktop path; fallback to Downloads if Desktop missing
    home = Path.home()
    desktop = home / "Desktop"
    target_dir = desktop if desktop.exists() else (home / "Downloads")
    target_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().isoformat(timespec="seconds")
    fname = f"summer_home_user_id_{user_id}.txt"
    content = (
        "Summer Stays User ID\n"
        "====================\n"
        f"User ID: {user_id}\n"
        f"Name: {name}\n"
        f"Created: {ts}\n\n"
        "Keep this file somewhere safe."
    )

    try:
        (target_dir / fname).write_text(content, encoding="utf-8")
        return jsonify({"ok": True, "path": str((target_dir / fname))})
    except Exception as e:
        return jsonify({"ok": False, "error": repr(e)}), 500

# health 
@app.route("/health")
def health(): return jsonify({"status":"ok","users_count":len(USERS),"listings_count":len(get_active_listings() or [])})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)