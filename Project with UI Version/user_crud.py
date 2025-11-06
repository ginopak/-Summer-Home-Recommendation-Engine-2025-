import json
import os
import uuid
from typing import Optional
from typing import List
from configs import USERS_DATA_FILE


class User:
    def __init__(
        self,
        name: str,
        group_size: int,
        preferred_environment: str,
        budget_min: float,
        budget_max: float,
        user_id: Optional[str] = None,
    ):

        self.user_id = user_id if user_id else str(uuid.uuid4())
        self.name = name.strip()
        self.group_size = group_size
        self.preferred_environment = preferred_environment.strip().lower()
        self.budget_min = budget_min
        self.budget_max = budget_max

    # Converting User object to Dictionary to save as JSON
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "group_size": self.group_size,
            "preferred_environment": self.preferred_environment,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
        }

    # Creating a User object from a dictionary (loaded from JSON)
    @staticmethod
    def from_dict(data: dict):
        return User(
            user_id=data.get("user_id"),
            name=data["name"],
            group_size=data["group_size"],
            preferred_environment=data["preferred_environment"],
            budget_min=data["budget_min"],
            budget_max=data["budget_max"],
        )


USERS_FILE = USERS_DATA_FILE


def save_users(users: List[User], filename=USERS_FILE):

    user_dicts = []
    for user in users:
        user_dicts.append(user.to_dict())

    with open(filename, "w") as f:
        json.dump(user_dicts, f, indent=4)

    print(f"Saved {len(users)} user profiles to {filename}.")


def load_users(filename=USERS_FILE) -> List[User]:
    try:
        with open(filename, "r") as f:
            user_dicts = json.load(f)

        users = []
        for user_data in user_dicts:
            user = User.from_dict(user_data)
            users.append(user)

        print(f"Loaded {len(users)} user profiles from {filename}.")
        return users

    except FileNotFoundError:
        print(f"No user file found at {filename}. Starting with empty list.")
        return []
    except json.JSONDecodeError:
        print(f"User file at {filename} is empty or corrupted. Starting fresh.")
        return []


# CRUD Operations for User Management - Create, Read, Update, Delete


def create_user(
    users: List[User],
    name: str,
    group_size: int,
    preferred_environment: str,
    budget_min: float,
    budget_max: float,
) -> User:

    new_user = User(name, group_size, preferred_environment, budget_min, budget_max)
    users.append(new_user)
    save_users(users)

    save_user_id_to_file(new_user.user_id)
    return new_user


def save_user_id_to_file(user_id: str):
    secret_file = os.path.join(os.path.expanduser("~"), "summer_home_user_id.txt")
    with open(secret_file, "w") as f:
        f.write(user_id)

    print(f"\n Your secret User ID has been saved to {secret_file}")
    print("Keep it safe! You will need this ID to login again.")


def view_users(users: List[User]) -> None:

    if not users:
        print("No users found.")
        return

    for user in users:
        print(
            f"Name: {user.name} | Group Size: {user.group_size} | "
            f"Environment: {user.preferred_environment} | Budget: {user.budget_min}-{user.budget_max}"
        )


def find_user_by_id(users: List[User], user_id: str) -> Optional[User]:

    for user in users:
        if user.user_id == user_id:
            return user
    return None


def update_user(
    users,
    user_id,
    name=None,
    group_size=None,
    preferred_environment=None,
    budget_min=None,
    budget_max=None,
):

    user = find_user_by_id(users, user_id)
    if not user:
        return False

    if name is not None:
        user.name = name
    if group_size is not None:
        user.group_size = group_size
    if preferred_environment is not None:
        user.preferred_environment = preferred_environment
    if budget_min is not None:
        user.budget_min = budget_min
    if budget_max is not None:
        user.budget_max = budget_max

    save_users(users)
    return True


def delete_user(users: List[User], user_id: str) -> bool:

    for i, user in enumerate(
        users
    ):  # I used enumerate to get index of user while iterating along with user_id.
        if user.user_id == user_id:
            users.pop(i)
            save_users(users)
            return True
    return False


# Main function to run the CLI for user management
"""
The special variable __name__ in Python is set to "__main__" only when you run the script directly -> CLI gets opened.

Inside that main() function, there is a loop that:

1. Shows you a menu of options (Create, View, Update, Delete User)
2. Waits for you to type what you want to do
3. Runs the right function depending on your choice (like creating a user, viewing users, etc.)
4. Keeps repeating this until you decide to exit

"""
if __name__ == "__main__":

    users = load_users()

    while True:
        print("\n ---- Summer Home Recommender (User Management) ----")
        print("1. Create User Profile")
        print("2. View All Users")
        print("3. Update User Profile")
        print("4. Delete User Profile")
        print("5. Exit")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == "1":
            # Create user
            name = input("Enter user name: ").strip()
            group_size = int(input("Enter group size (number): ").strip())
            preferred_env = (
                input(
                    "Enter your preferred environment (mountain, lake, beach, city etc.): "
                )
                .strip()
                .lower()
            )
            budget_min = float(input("Enter minimum budget: ").strip())
            budget_max = float(input("Enter maximum budget: ").strip())

            new_user = create_user(
                users, name, group_size, preferred_env, budget_min, budget_max
            )
            print(f"Your User ID (save this securely!): {new_user.user_id}")

            # Save user_id to a text file -> Privacy Matters
            user_id_file = os.path.join(os.getcwd(), f"user_{new_user.name}_id.txt")
            with open(user_id_file, "w") as f:
                f.write(f"Your User ID: {new_user.user_id}\n")
            print(f"A copy of your User ID has been saved to: {user_id_file}")

        elif choice == "2":
            # View users
            print("\nCurrent Users:")
            view_users(users)

        elif choice == "3":
            # Update user
            user_id = input("Enter User ID to update: ").strip()
            user = find_user_by_id(users, user_id)
            if not user:
                print("User not found.")
                continue

            print("Leave field blank to keep current value.")
            name = input(f"Name [{user.name}]: ").strip() or None
            group_size_input = input(f"Group Size [{user.group_size}]: ").strip()
            group_size = int(group_size_input) if group_size_input else None
            preferred_env = (
                input(f"Preferred Environment [{user.preferred_environment}]: ")
                .strip()
                .lower()
                or None
            )
            budget_min_input = input(f"Budget Min [{user.budget_min}]: ").strip()
            budget_min = float(budget_min_input) if budget_min_input else None
            budget_max_input = input(f"Budget Max [{user.budget_max}]: ").strip()
            budget_max = float(budget_max_input) if budget_max_input else None

            updated = update_user(
                users, user_id, name, group_size, preferred_env, budget_min, budget_max
            )
            if updated:
                print("User profile updated successfully!")
            else:
                print("Failed to update user profile.")

        elif choice == "4":
            # Delete user
            user_id = input("Enter User ID to delete: ").strip()
            deleted = delete_user(users, user_id)
            if deleted:
                print("User deleted successfully!")
            else:
                print("User not found. No deletion performed.")

        elif choice == "5":
            print("Exiting program. Goodbye!")
            break

        else:
            print("Invalid choice. Please enter a number from 1 to 5.")


"""
Steps to run this script:
1. Ensure you have Python 3.X installed on your system.
2. Save this script as user_crud.py in your desired directory.
3. Open a terminal and navigate to the directory where user_crud.py is saved.
4. Run the script using the command: python user_crud.py

"""
