import os
import json


DATA_DIR = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(DATA_DIR, exist_ok=True)  # create the folder if not exists


LISTINGS_FILE = os.path.join(DATA_DIR, "cleaned_listings.csv")
FAV_FILE = os.path.join(DATA_DIR, "favorites.json")


def load_favorites():
    if not os.path.exists(FAV_FILE):
        return {}
    try:
        with open(FAV_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_favorites(favs: dict):
    with open(FAV_FILE, "w") as f:
        json.dump(favs, f, indent=4)


def get_user_favorites(user_id: str):
    favs = load_favorites()
    return favs.get(user_id, [])


def add_favorite(user_id: str, listing_id: int):
    favs = load_favorites()
    user_list = favs.get(user_id, [])
    if listing_id not in user_list:
        user_list.append(listing_id)
    favs[user_id] = user_list
    save_favorites(favs)
    return True


def remove_favorite(user_id: str, listing_id: int):
    favs = load_favorites()
    user_list = favs.get(user_id, [])
    if listing_id in user_list:
        user_list.remove(listing_id)
        favs[user_id] = user_list
        save_favorites(favs)
        return True
    return False
