# recommender.py
import pandas as pd
import numpy as np

def get_recommendations(user, listings, top_n=5, weights=None):
    """
    Recommend top-N listings based on user's preferences and budget.
    
    This robust version accepts user as a dictionary and listings as a list of dictionaries.
    It internally handles data cleaning and validation, making it resilient to messy data.
    """
    if weights is None:
        weights = dict(price=40.0, env=30.0, rating=30.0)

    if not listings:
        print("No listings available.")
        return []

    # Convert list of dictionaries to a DataFrame for robust processing
    df = pd.DataFrame(listings)

    # If the dataframe is empty after creation, exit early.
    if df.empty:
        return []

    # Data Cleaning and Type Coercion Layer
    # Clean and validate numeric columns
    for col in ["price", "review_rating", "accommodates"]:
        df[col] = pd.to_numeric(df[col], errors="coerce") # Invalid values become NaN
    
    # Fill NaN values with safe defaults
    df["price"].fillna(0.0, inplace=True)
    df["review_rating"].fillna(3.0, inplace=True) # Use a neutral rating for missing ones
    df["accommodates"].fillna(1, inplace=True)

    # Clean and validate text columns
    for col in ["tags", "location", "property_type"]:
        df[col] = df[col].fillna("").astype(str) # Missing text becomes an empty string

    # Ensure listing_id is present and usable for the final step. Drop rows with invalid IDs.
    if 'listing_id' not in df.columns:
        return [] # Cannot proceed without IDs
    df.dropna(subset=['listing_id'], inplace=True)

    # Filtering Layer 
    user_budget_min = float(user.get("budget_min", 0))
    user_budget_max = float(user.get("budget_max", float('inf')))
    user_group_size = int(user.get("group_size", 1))

    df_filtered = df[
        (df["price"] >= user_budget_min)
        & (df["price"] <= user_budget_max)
        & (df["accommodates"] >= user_group_size)
    ].copy() # Use .copy() to avoid SettingWithCopyWarning

    if df_filtered.empty:
        print("No listings match your budget and group size after filtering.")
        return []

    # Scoring Layer
    df_filtered["score"] = 0.0

    # Environment Score
    preferred_env = user.get("preferred_environment", "").strip().lower()
    if preferred_env:
        # Combine relevant text fields into one for searching
        search_space = (df_filtered["tags"].str.lower() + " " +
                        df_filtered["location"].str.lower() + " " +
                        df_filtered["property_type"].str.lower())
        
        env_mask = search_space.str.contains(preferred_env, na=False)
        df_filtered.loc[env_mask, "score"] += float(weights["env"])

    # Price Proximity Score
    bmin = user_budget_min
    bmax = user_budget_max
    mid = (bmin + bmax) / 2
    rng = bmax - bmin

    if rng > 0:
        half_range = rng / 2
        proximity = 1 - (np.abs(df_filtered["price"] - mid) / half_range)
    else:
        denominator = max(mid, 1.0)
        proximity = 1 - (np.abs(df_filtered["price"] - mid) / denominator)

    df_filtered["score"] += proximity.clip(lower=0, upper=1) * float(weights["price"])

    # Rating Score
    rating_normalized = (df_filtered["review_rating"] / 5.0).clip(lower=0, upper=1)
    df_filtered["score"] += rating_normalized * float(weights["rating"])

    # Final Sorting and Selection
    df_sorted = df_filtered.sort_values(by=["score", "review_rating"], ascending=[False, False]).head(int(top_n))

    # Return the final list of recommended listing dictionaries
    return df_sorted.to_dict(orient='records')