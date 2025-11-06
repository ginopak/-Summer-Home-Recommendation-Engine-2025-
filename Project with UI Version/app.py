from favourites import get_user_favorites, add_favorite, remove_favorite
from recommender import get_recommendations
import listings as listings_module
from configs import (
    LLM_API_KEY,
    SYNTHETIC_LISTING_CSV_PATH,
    CLEANED_LISTING_CSV_PATH,
    MERGED_LISTING_CSV_PATH,
)
import pandas as pd
import pathlib

from user_crud import (
    load_users,
    create_user,
    find_user_by_id,
    update_user,
    User,
)
from listings import (
    load_listings,
    view_listings,
    filter_combined,
    sort_listings,
    find_listing_by_id,
)

from synthetic_data import (
    generate_synthetic_listings,
    save_synthetic_listings,
    merge_with_real_listings,
)

from bookings import (
    create_booking,
    get_user_bookings,
    cancel_booking,
    is_listing_available,
)


def choose_user(users):

    def save_user_id_to_file(user_id: str):
        """
        Saving the generated user_id to a text file for the user to keep as a secret key.
        """
        file_path = pathlib.Path.home() / "Desktop" / "summer_home_user_id.txt"
        with open(file_path, "w") as f:
            f.write(f"Your secret User ID: {user_id}\n")
        print(
            f"\n IMPORTANT: Your User ID has been saved to to your Desktop as 'summer_home_user_id.txt' "
        )
        print(
            "Keep this file safe because you can only see this one time. You will need it to access your profile. \n"
        )

    if not users:
        print("\nNo users yet. Let's create one.")
        name = input("Name: ").strip()
        group_size = int(input("Group size: ").strip())
        preferred_env = input("Preferred environment: ").strip().lower()
        budget_min = float(input("Budget min: ").strip())
        budget_max = float(input("Budget max: ").strip())
        new_user = create_user(
            users, name, group_size, preferred_env, budget_min, budget_max
        )
        print(f"\nCreated user {new_user.name}.")
        save_user_id_to_file(new_user.user_id)  # <-- Save secret key
        return new_user

    print("\nOptions:")
    print("1) Select an existing user by providing your User ID")
    print("2) Create a new user")
    choice = input("Choose 1 or 2: ").strip()

    if choice == "1":
        user_id = input("Enter your secret User ID: ").strip()
        user = find_user_by_id(users, user_id)
        if user:
            print(f"Selected {user.name}.")
            return user
        print("User not found. Make sure you enter the correct User ID.")
        return None

    elif choice == "2":
        name = input("Name: ").strip()
        group_size = int(input("Group size: ").strip())
        preferred_env = input("Preferred environment: ").strip().lower()
        budget_min = float(input("Budget min: ").strip())
        budget_max = float(input("Budget max: ").strip())
        new_user = create_user(
            users, name, group_size, preferred_env, budget_min, budget_max
        )
        print(f"\nCreated user {new_user.name}.")
        save_user_id_to_file(new_user.user_id)  # <-- Save secret key
        return new_user

    else:
        print("Invalid choice.")
        return None


def edit_current_user(user: User, users: list):

    print("\n--- Edit My Profile ---")
    print("Leave blank to keep current value.")

    new_name = input(f"Name [{user.name}]: ").strip() or user.name

    group_size_input = input(f"Group Size [{user.group_size}]: ").strip()
    new_group_size = int(group_size_input) if group_size_input else user.group_size

    new_env = (
        input(f"Preferred Environment [{user.preferred_environment}]: ").strip().lower()
        or user.preferred_environment
    )

    budget_min_input = input(f"Budget Min [{user.budget_min}]: ").strip()
    new_budget_min = float(budget_min_input) if budget_min_input else user.budget_min

    budget_max_input = input(f"Budget Max [{user.budget_max}]: ").strip()
    new_budget_max = float(budget_max_input) if budget_max_input else user.budget_max

    update_user(
        users,
        user.user_id,
        name=new_name,
        group_size=new_group_size,
        preferred_environment=new_env,
        budget_min=new_budget_min,
        budget_max=new_budget_max,
    )

    print("\n Profile updated successfully!\n")


def listings_menu_for_user(user, listings, users):

    while True:
        print(f"\n=== Listings Menu (User: {user.name}) ===")
        print("1. View listings")
        print("2. Update/Edit user profile")
        print("3. Combined filter (environment + budget + accommodates)")
        print("4. Sort listings")
        print("5. Add a listing to favorites (by ID)")
        print("6. View my favorites")
        print("7. Remove a favorite (by ID)")
        print("8. Get recommendations")
        print("9. Generate synthetic listings via LLM")
        print("10. Book a listing")
        print("11. View my bookings")
        print("12. Cancel a booking")
        print("13. Back to main menu")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            limit = input("Show how many? (default 5): ").strip()
            limit = int(limit) if limit.isdigit() else 5
            view_listings(listings, limit=limit)

        elif choice == "2":
            edit_current_user(user, users)

        elif choice == "3":
            env = input("Environment (or blank): ").strip()
            min_price = input("Min price (or blank): ").strip()
            max_price = input("Max price (or blank): ").strip()
            min_acc = input("Min accommodates (or blank): ").strip()

            # parse to numbers or None
            min_price = (
                float(min_price) if min_price.replace(".", "", 1).isdigit() else None
            )
            max_price = (
                float(max_price) if max_price.replace(".", "", 1).isdigit() else None
            )
            min_acc = int(min_acc) if min_acc.isdigit() else None
            env = env or None

            filtered = filter_combined(
                listings,
                environment=env,
                min_price=min_price,
                max_price=max_price,
                min_accommodates=min_acc,
            )
            if not filtered:
                print("No listings match your criteria.")
            else:
                limit = input(
                    f"Show how many? (default {min(5, len(filtered))}): "
                ).strip()
                default = min(5, len(filtered))
                limit = int(limit) if limit.isdigit() else default
                view_listings(filtered, limit=limit)

        elif choice == "4":
            print("Sort by: price, review_rating, accommodates")
            key = input("Field: ").strip()
            order = input("Ascending? (y/n): ").strip().lower()
            ascending = order in ("y", "yes", "")

            sorted_list = sort_listings(
                listings, by_what=key, ascending=ascending, user=user
            )

            limit = input("Show how many? (default 10): ").strip()
            limit = int(limit) if limit.isdigit() else 10
            view_listings(sorted_list, limit=limit)

        elif choice == "5":
            listing_id = input("Enter listing ID to favorite: ").strip()
            if not listing_id.isdigit():
                print("Please enter a valid numeric ID.")
                continue
            listing_id = int(listing_id)
            listing = find_listing_by_id(listings, listing_id)
            if not listing:
                print("Listing not found.")
                continue
            add_favorite(user.user_id, listing_id)
            print(f"Added to favorites: [ID {listing_id}] {listing.name}")

        elif choice == "6":
            fav_ids = get_user_favorites(user.user_id)
            if not fav_ids:
                print("You have no favorites yet.")
                continue

            fav_listings = [l for l in listings if l.listing_id in fav_ids]

            print(f"\n=== {user.name}'s Favorites ===")
            for listing in fav_listings:
                print(
                    f"[ID {listing.listing_id}] {listing.name} | Location: {listing.location} | Price: ${listing.price}"
                )
            print("-" * 40)

        elif choice == "7":
            listing_id = input("Enter listing ID to remove from favorites: ").strip()
            if not listing_id.isdigit():
                print("Please enter a valid numeric ID.")
                continue
            listing_id = int(listing_id)
            success = remove_favorite(user.user_id, listing_id)
            if success:
                print(f"Removed listing ID {listing_id} from favorites.")
            else:
                print(f"Listing ID {listing_id} was not in your favorites.")

        elif choice == "8":
            topn = input("How many recommendations? (default 5): ").strip()
            topn = int(topn) if topn.isdigit() else 5

            recs = get_recommendations(user, listings, top_n=topn)
            if not recs:
                print(
                    "No recommendations found. Try widening your budget or reducing group size."
                )
            else:
                print("\n--- Recommended Properties ---")
                view_listings(recs, limit=len(recs))

        elif choice == "9":
            prompt = input(
                "Enter your prompt for synthetic listings (Instruct model to generate listings in JSON format): "
            ).strip()

            if not prompt:
                print("Prompt cannot be empty. Please try again.")
                continue

            print("Generating synthetic listings...")

            try:
                raw_output = generate_synthetic_listings(prompt, LLM_API_KEY)
                save_synthetic_listings(
                    raw_output,
                    SYNTHETIC_LISTING_CSV_PATH,
                )
                merge_with_real_listings(
                    real_file=CLEANED_LISTING_CSV_PATH,
                    synthetic_file=SYNTHETIC_LISTING_CSV_PATH,
                    output_file=MERGED_LISTING_CSV_PATH,
                )
                print(
                    "Synthetic listings generated and merged successfully! You can now view them along with real listings."
                )

                df_merged_path = MERGED_LISTING_CSV_PATH

                df = pd.read_csv(df_merged_path)

                listings = [
                    listings_module.Listing(
                        name=row["name"],
                        location=row["location"],
                        property_type=row["property_type"],
                        accommodates=row["accommodates"],
                        amenities=row["amenities"],
                        price=row["price"],
                        min_nights=row["min_nights"],
                        max_nights=row["max_nights"],
                        review_rating=row["review_rating"],
                        tags=row["tags"],
                        listing_id=i,
                    )
                    for i, (_, row) in enumerate(df.iterrows())
                ]

            except Exception as e:
                print("Error generating synthetic listings:", e)

        elif choice == "10":
            listing_id = input("Enter the Listing ID to book: ").strip()
            if not listing_id.isdigit():
                print("Enter a valid numeric Listing ID.")
                continue

            listing_id = int(listing_id)
            listing = find_listing_by_id(listings, listing_id)
            if not listing:
                print("Listing not found.")
                continue

            check_in = (
                input("Enter check-in date (YYYY-MM-DD) or leave blank: ").strip()
                or None
            )
            check_out = (
                input("Enter check-out date (YYYY-MM-DD) or leave blank: ").strip()
                or None
            )

            if not check_in or not check_out:
                print(
                    "You must provide both check-in and check-out dates in YYYY-MM-DD format."
                )
                continue

            if not is_listing_available(listing_id, check_in, check_out):
                print("Sorry, this listing is already booked for the selected dates.")
                continue

            booking = create_booking(user.user_id, listing_id, check_in, check_out)
            print(
                f"Booking confirmed! Booking ID: {booking['booking_id']} for {listing.name}"
            )

        elif choice == "11":
            bookings_list = get_user_bookings(user.user_id)
            if not bookings_list:
                print("You have no bookings yet.")

            print(f"\n=== {user.name}'s Bookings ===")
            for b in bookings_list:
                listing = find_listing_by_id(listings, b["listing_id"])
                print(
                    f"[Booking ID {b['booking_id']}] {listing.name} | Check-in: {b['check_in']} | Check-out: {b['check_out']}"
                )
            print("-" * 40)

        elif choice == "12":
            booking_id = input("Enter Booking ID to cancel: ").strip()
            if not booking_id.isdigit():
                print("Please enter a valid numeric Booking ID.")
                continue

            booking_id = int(booking_id)
            success = cancel_booking(user.user_id, booking_id)
            if success:
                print(f"Booking ID {booking_id} has been cancelled.")
            else:
                print(f"Booking ID {booking_id} not found or could not be cancelled.")

        elif choice == "13":
            print("Returning to main menu...")
            break


def main():
    users = load_users()
    listings = load_listings()

    print("=== Welcome to LLM-Powered Summer Home Recommender ===")

    while True:
        print("\nMain Menu:")
        print("1. Select/Create User")
        print("2. Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            user = choose_user(users)
            if user:
                listings_menu_for_user(user, listings, users)
        elif choice == "2":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
