import json
import os
from pathlib import Path
from datetime import datetime

BOOKINGS_FILE = os.path.join(
    os.path.dirname(__file__),  # Current file (src/)
    "..", 
    "data", # Moving up one level
    "bookings.json",
)


def load_bookings():
    """
    The function reads all bookings from the JSON file. If the file doesn’t exist or is corrupted, returns an empty list.
    """

    if not os.path.exists(BOOKINGS_FILE):
        return []
    with open(BOOKINGS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


# Saving bookings to the JSON file
def save_bookings(bookings):
    """
    Saving bookings to the JSON file
    """
    with open(BOOKINGS_FILE, "w") as f:
        json.dump(bookings, f, indent=4)


def create_booking(user_id, listing_id, check_in=None, check_out=None):

    bookings = load_bookings()

    # This line assigns a unique booking_id to each new booking by setting it to one more than the current number of bookings.
    booking_id = len(bookings) + 1

    booking = {
        "booking_id": booking_id,
        "user_id": user_id,
        "listing_id": listing_id,
        "check_in": check_in,
        "check_out": check_out,
    }

    bookings.append(booking)
    save_bookings(bookings)
    return booking


def get_user_bookings(user_id):
    """
    This function retrieves all bookings for a specific user.
    """
    bookings = load_bookings()
    return [b for b in bookings if b["user_id"] == user_id]


def cancel_booking(user_id, booking_id):
    """
    Remove a booking by user_id and booking_id.
    Returns True if deleted, False if not found.
    """
    bookings = load_bookings()
    initial_len = len(bookings)

    bookings = [
        b
        for b in bookings
        if not (b["user_id"] == user_id and b["booking_id"] == booking_id)
    ]

    if len(bookings) < initial_len:
        save_bookings(bookings)
        return True
    return False


def is_listing_available(listing_id, check_in, check_out):
    """
    Checks if a listing is available for the requested dates by ensuring there’s no overlap with existing bookings.
    """
    bookings = load_bookings()
    requested_start = datetime.strptime(check_in, "%Y-%m-%d").date()
    requested_end = datetime.strptime(check_out, "%Y-%m-%d").date()

    for b in bookings:
        if b["listing_id"] != listing_id:
            continue
        existing_start = datetime.strptime(b["check_in"], "%Y-%m-%d").date()
        existing_end = datetime.strptime(b["check_out"], "%Y-%m-%d").date()

        # Checking for overlapping dates
        if requested_start <= existing_end and requested_end >= existing_start:
            return False  # Booking Not available
    return True  # Booking Available


"""
Workflow:

is_listing_available checks if the dates are free.
If available, create_booking adds the booking to the JSON file.
User wants to view their bookings:

get_user_bookings retrieves all bookings for that user.
User wants to cancel a booking:

cancel_booking removes the booking from the JSON file.
All booking data is stored and managed in bookings.json.
"""
