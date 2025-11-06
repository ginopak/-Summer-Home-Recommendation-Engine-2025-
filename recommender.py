import pandas as pd
import numpy as np


def get_recommendations(user, listings, top_n=5, weights=None):
    """
    Recommend top-N listings based on user's preferences and budget.
    Vectorized with Pandas/NumPy for speed and clarity.
    """
    if weights is None:
        weights = dict(price=40.0, env=30.0, rating=30.0)

    if not listings:
        print("No listings available.")
        return []

    # 1) Convert to DataFrame for vectorized math
    df = pd.DataFrame([l.to_dict() for l in listings])

    for col in ["price", "review_rating", "accommodates"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["tags", "location", "property_type"]:
        df[col] = df[col].astype(str)

    # 3) Filter: budget + accommodates
    df = df[
        (df["price"] >= float(user.budget_min))
        & (df["price"] <= float(user.budget_max))
        & (df["accommodates"] >= int(user.group_size))
    ]

    if df.empty:
        print("No listings match your budget and group size.")
        return []

    # 4) Scoring (vectorized)
    df["score"] = 0.0

    # We want listings that match the user’s preferred environment to get a bonus score.
    # Check tags, location, property_type columns to see if the environment word appears.

    preferred_env = getattr(user, "preferred_environment", "").strip().lower()
    if preferred_env:
        # Check if the preferred environment appears in tags, location, or property_type
        matches_tags = df["tags"].str.lower().str.contains(preferred_env, na=False)
        matches_location = (
            df["location"].str.lower().str.contains(preferred_env, na=False)
        )
        matches_type = (
            df["property_type"].str.lower().str.contains(preferred_env, na=False)
        )

        env_mask = matches_tags | matches_location | matches_type
        df.loc[env_mask, "score"] += float(weights["env"])

    # We are Computing a normalized score based on distance from user's ideal budget (midpoint).
    # Listings closest to midpoint get max points; score decreases linearly to 0 at budget min/max.
    bmin = float(user.budget_min)
    bmax = float(user.budget_max)
    mid = (bmin + bmax) / 2
    rng = bmax - bmin

    if rng > 0:
        denminator = rng / 2
        proximity = 1 - (np.abs(df["price"] - mid) / denminator)

    else:
        denminator = max(mid, 1.0)
        proximity = 1 - (np.abs(df["price"] - mid) / denminator)

    proximity = proximity.clip(lower=0, upper=1)
    df["score"] += proximity * float(weights["price"])

    rating_normalised = (df["review_rating"] / 5.0).clip(lower=0, upper=1)
    df["score"] += rating_normalised * float(weights["rating"])

    df = df.sort_values(by=["score", "review_rating"], ascending=[False, False]).head(
        int(top_n)
    )

    id_to_listing = {l.listing_id: l for l in listings}
    out = []
    for _, row in df.iterrows():
        lst = id_to_listing.get(int(row["listing_id"]))
        if lst is not None:
            out.append(lst)

    return out
