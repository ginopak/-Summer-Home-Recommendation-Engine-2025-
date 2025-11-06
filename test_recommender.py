# test_recommender.py
import traceback
from user_crud import load_users, User
from listings import load_listings, Listing
from recommender import get_recommendations

def run_test():
    print("--- Starting standalone recommender system test ---")

    # 1. Load all data
    print("\nStep 1/3] Loading users and listings...")
    try:
        all_users = load_users()
        all_listings = load_listings()
        if not all_users:
            print("Error: failed to load users or file is empty. Please check users.json.")
            return
        if not all_listings:
            print("Error: failed to load listings or file is empty. Please check cleaned_listings.csv.")
            return
        print(f"Successfully loaded {len(all_users)} users and {len(all_listings)} listings.")
    except Exception as e:
        print(f"Fatal error occurred while loading data: {e}")
        traceback.print_exc()
        return

    # 2. Select a test user
    # We will use the first user from users.json for testing
    test_user = all_users[0]
    print(f"\n[Step 2/3] Selected test user: '{test_user.name}' (ID: {test_user.user_id})")
    print(f"  -> User preferences: Environment='{test_user.preferred_environment}', Budget=${test_user.budget_min}-${test_user.budget_max}, Group Size={test_user.group_size}")

    # 3. Execute recommendation function and capture any errors
    print("\n[Step 3/3] Calling get_recommendations function...")
    try:
        recommendations = get_recommendations(test_user, all_listings, top_n=5)

        print("\n--- ✅ Test Passed ---")
        if recommendations:
            print(f"Successfully retrieved {len(recommendations)} recommendations:")
            for i, rec in enumerate(recommendations):
                # recommendations may be a list of objects or dicts; handle both
                if isinstance(rec, Listing):
                    print(f"  {i+1}. [ID: {rec.listing_id}] {rec.name} - ${rec.price} - Rating: {rec.review_rating}")
                elif isinstance(rec, dict):
                     print(f"  {i+1}. [ID: {rec.get('listing_id')}] {rec.get('name')} - ${rec.get('price')} - Rating: {rec.get('review_rating')}")
        else:
            print("Function ran successfully but returned no recommendations (user preferences may be too strict).")

    except Exception as e:
        print("\n--- ❌ Test Failed ---")
        print("An error occurred while calling get_recommendations. Here is the full traceback report:")
        print("-" * 20)
        traceback.print_exc()
        print("-" * 20)

if __name__ == "__main__":
    run_test()