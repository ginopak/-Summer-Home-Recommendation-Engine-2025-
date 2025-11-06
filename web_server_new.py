#!/usr/bin/env python3
"""
Flask Web Server for StayFinder - Airbnb-style Listings API
Wraps existing CLI modules into REST API endpoints
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import traceback
import os
from datetime import datetime
import pandas as pd

# Import existing modules
from user_crud import (
    load_users, save_users, create_user, find_user_by_id, 
    update_user, delete_user, User
)
from favourites import get_user_favorites, add_favorite, remove_favorite
from recommender import get_recommendations
from listings import (
    load_listings, filter_combined, sort_listings, 
    find_listing_by_id, Listing
)
from bookings import (
    create_booking, get_user_bookings, cancel_booking, 
    is_listing_available, load_bookings
)
from synthetic_data import (
    generate_synthetic_listings, save_synthetic_listings,
    merge_with_real_listings
)
from config import LLM_API_KEY
# Ensure users are stored in a local JSON file within this project directory
import user_crud as user_crud_module
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(BASE_DIR, "users.json")
os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
user_crud_module.USERS_FILE = USERS_PATH

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Global data stores
users_data = []
listings_data = []
current_dataset = "original"

def init_data():
    """Initialize data on server startup"""
    global users_data, listings_data
    try:
        users_data = load_users()
        listings_data = load_listings()
        print(f"✅ Loaded {len(users_data)} users and {len(listings_data)} listings")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        users_data = []
        listings_data = []

def error_response(message, status_code=400):
    """Standard error response"""
    return jsonify({"error": message}), status_code

def success_response(data=None, message="Success"):
    """Standard success response"""
    response = {"ok": True}
    if data is not None:
        if isinstance(data, dict):
            response.update(data)
        else:
            response["data"] = data
    if message != "Success":
        response["message"] = message
    return jsonify(response)

# ==================== HEALTH & STATUS ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "users_count": len(users_data),
        "listings_count": len(listings_data),
        "timestamp": datetime.now().isoformat()
    })

# ==================== USERS API ====================

@app.route('/api/users', methods=['GET'])
def get_all_users():
    """Get all users (for admin purposes)"""
    try:
        users_list = [user.to_dict() for user in users_data]
        return jsonify(users_list)
    except Exception as e:
        return error_response(f"Failed to get users: {str(e)}", 500)

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get user by ID"""
    try:
        user = find_user_by_id(users_data, user_id)
        if not user:
            # Return a light ephemeral profile as per requirements
            return jsonify({
                "user_id": user_id,
                "name": "Unknown User",
                "group_size": 1,
                "preferred_environment": "any",
                "budget_min": 0.0,
                "budget_max": 1000.0
            })
        return jsonify(user.to_dict())
    except Exception as e:
        return error_response(f"Failed to get user: {str(e)}", 500)

@app.route('/api/users', methods=['POST'])
def create_new_user():
    """Create a new user"""
    try:
        data = request.get_json()
        if not data:
            return error_response("No JSON data provided")
        
        # Validate required fields
        required_fields = ['name', 'group_size', 'preferred_environment', 'budget_min', 'budget_max']
        for field in required_fields:
            if field not in data:
                return error_response(f"Missing required field: {field}")
        
        # Create user
        new_user = create_user(
            users_data,
            name=data['name'],
            group_size=int(data['group_size']),
            preferred_environment=data['preferred_environment'],
            budget_min=float(data['budget_min']),
            budget_max=float(data['budget_max'])
        )
        
        return jsonify(new_user.to_dict()), 201
        
    except ValueError as e:
        return error_response(f"Invalid data: {str(e)}")
    except Exception as e:
        return error_response(f"Failed to create user: {str(e)}", 500)

# ==================== LISTINGS API ====================

@app.route('/api/listings', methods=['GET'])
def get_listings():
    """Get listings with optional filtering, sorting, and pagination"""
    try:
        # Get query parameters
        environment = request.args.get('environment') or request.args.get('env')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        accommodates = request.args.get('accommodates', type=int)
        amenities = request.args.get('amenities')
        sort_by = request.args.get('sort_by', 'price')
        ascending = request.args.get('ascending', 'true').lower() == 'true'
        limit = request.args.get('limit', 20, type=int)
        page = request.args.get('page', 1, type=int)
        
        # Start with all listings
        filtered_listings = listings_data[:]
        
        # Apply filters
        if any([environment, min_price is not None, max_price is not None, accommodates]):
            filtered_listings = filter_combined(
                filtered_listings,
                environment=environment,
                min_price=min_price,
                max_price=max_price,
                min_accommodates=accommodates
            )
        
        # Apply amenities filter (manual implementation)
        if amenities:
            amenity_list = [a.strip().lower() for a in amenities.split(',')]
            filtered_listings = [
                listing for listing in filtered_listings
                if all(amenity in str(listing.amenities).lower() for amenity in amenity_list)
            ]
        
        # Apply sorting
        if sort_by in ['price', 'review_rating', 'accommodates']:
            filtered_listings = sorted(
                filtered_listings,
                key=lambda l: getattr(l, sort_by),
                reverse=not ascending
            )
        
        # Calculate pagination
        total = len(filtered_listings)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_listings = filtered_listings[start_idx:end_idx]
        
        # Convert to dictionaries
        items = [listing.to_dict() for listing in paginated_listings]
        
        return jsonify({
            "total": total,
            "page": page,
            "limit": limit,
            "items": items
        })
        
    except Exception as e:
        return error_response(f"Failed to get listings: {str(e)}", 500)

@app.route('/api/listings/<int:listing_id>', methods=['GET'])
def get_listing_by_id(listing_id):
    """Get single listing by ID"""
    try:
        listing = find_listing_by_id(listings_data, listing_id)
        if not listing:
            return error_response("Listing not found", 404)
        
        return jsonify(listing.to_dict())
        
    except Exception as e:
        return error_response(f"Failed to get listing: {str(e)}", 500)

# ==================== FAVORITES API ====================

@app.route('/api/favorites/<user_id>', methods=['GET'])
def get_favorites(user_id):
    """Get user's favorites"""
    try:
        favorite_ids = get_user_favorites(user_id)
        
        # Get full listing objects
        favorites = [
            listing.to_dict() for listing in listings_data 
            if listing.listing_id in favorite_ids
        ]
        
        return jsonify({
            "user_id": user_id,
            "favorite_ids": favorite_ids,
            "favorites": favorites
        })
        
    except Exception as e:
        return error_response(f"Failed to get favorites: {str(e)}", 500)

@app.route('/api/favorites', methods=['POST'])
def add_to_favorites():
    """Add listing to favorites"""
    try:
        data = request.get_json()
        if not data or 'user_id' not in data or 'listing_id' not in data:
            return error_response("user_id and listing_id required")
        
        user_id = data['user_id']
        listing_id = int(data['listing_id'])
        
        # Verify listing exists
        if not find_listing_by_id(listings_data, listing_id):
            return error_response("Listing not found", 404)
        
        success = add_favorite(user_id, listing_id)
        if success:
            return success_response(message="Added to favorites")
        else:
            return error_response("Failed to add favorite")
            
    except Exception as e:
        return error_response(f"Failed to add favorite: {str(e)}", 500)

@app.route('/api/favorites', methods=['DELETE'])
def remove_from_favorites():
    """Remove listing from favorites"""
    try:
        data = request.get_json()
        if not data or 'user_id' not in data or 'listing_id' not in data:
            return error_response("user_id and listing_id required")
        
        user_id = data['user_id']
        listing_id = int(data['listing_id'])
        
        success = remove_favorite(user_id, listing_id)
        if success:
            return success_response(message="Removed from favorites")
        else:
            return error_response("Favorite not found")
            
    except Exception as e:
        return error_response(f"Failed to remove favorite: {str(e)}", 500)

# ==================== RECOMMENDATIONS API ====================

@app.route('/api/recommend', methods=['GET'])
def get_user_recommendations():
    """Get personalized recommendations"""
    try:
        user_id = request.args.get('user_id')
        limit = request.args.get('limit', 12, type=int)
        
        if not user_id:
            return error_response("user_id parameter required")
        
        user = find_user_by_id(users_data, user_id)
        if not user:
            return error_response("User not found", 404)
        
        recommendations = get_recommendations(user, listings_data, top_n=limit)
        
        return jsonify({
            "total": len(listings_data),
            "items": [listing.to_dict() for listing in recommendations]
        })
        
    except Exception as e:
        return error_response(f"Failed to get recommendations: {str(e)}", 500)

# ==================== BOOKINGS API ====================

@app.route('/api/availability', methods=['GET'])
def check_availability():
    """Check listing availability"""
    try:
        listing_id = request.args.get('listing_id', type=int)
        start = request.args.get('start')
        end = request.args.get('end')
        
        if not all([listing_id, start, end]):
            return error_response("listing_id, start, and end parameters required")
        
        available = is_listing_available(listing_id, start, end)
        
        # Get conflicting bookings for more detail
        conflicts = []
        if not available:
            bookings = load_bookings()
            conflicts = [
                b for b in bookings 
                if b['listing_id'] == listing_id and 
                b['check_in'] <= end and b['check_out'] >= start
            ]
        
        return jsonify({
            "available": available,
            "conflicts": conflicts
        })
        
    except Exception as e:
        return error_response(f"Failed to check availability: {str(e)}", 500)

@app.route('/api/book', methods=['POST'])
def make_booking():
    """Create a new booking"""
    try:
        data = request.get_json()
        if not data:
            return error_response("No JSON data provided")
        
        required_fields = ['user_id', 'listing_id', 'start', 'end']
        for field in required_fields:
            if field not in data:
                return error_response(f"Missing required field: {field}")
        
        user_id = data['user_id']
        listing_id = int(data['listing_id'])
        start = data['start']  # or check_in
        end = data['end']      # or check_out
        
        # Handle alternative field names
        if 'check_in' in data:
            start = data['check_in']
        if 'check_out' in data:
            end = data['check_out']
        
        # Verify user and listing exist
        if not find_user_by_id(users_data, user_id):
            return error_response("User not found", 404)
        
        if not find_listing_by_id(listings_data, listing_id):
            return error_response("Listing not found", 404)
        
        # Check availability
        if not is_listing_available(listing_id, start, end):
            return error_response("Listing not available for selected dates", 409)
        
        # Create booking
        booking = create_booking(user_id, listing_id, start, end)
        
        return jsonify({
            "ok": True,
            "booking": booking
        }), 201
        
    except Exception as e:
        return error_response(f"Failed to create booking: {str(e)}", 500)

@app.route('/api/bookings', methods=['GET'])
def get_user_bookings_api():
    """Get user's bookings"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return error_response("user_id parameter required")
        
        bookings = get_user_bookings(user_id)
        
        # Add created_at timestamp if missing
        for booking in bookings:
            if 'created_at' not in booking:
                booking['created_at'] = datetime.now().isoformat()
        
        return jsonify({"items": bookings})
        
    except Exception as e:
        return error_response(f"Failed to get bookings: {str(e)}", 500)

@app.route('/api/bookings/<int:booking_id>', methods=['DELETE'])
def cancel_user_booking(booking_id):
    """Cancel a booking"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return error_response("user_id parameter required")
        
        success = cancel_booking(user_id, booking_id)
        
        return jsonify({"removed": success})
        
    except Exception as e:
        return error_response(f"Failed to cancel booking: {str(e)}", 500)

# ==================== DATASET MANAGEMENT API ====================

@app.route('/api/dataset/status', methods=['GET'])
def dataset_status():
    """Get current dataset status"""
    try:
        return jsonify({
            "source": current_dataset,
            "count": len(listings_data)
        })
    except Exception as e:
        return error_response(f"Failed to get dataset status: {str(e)}", 500)

@app.route('/api/dataset/use_original', methods=['POST'])
def use_original_dataset():
    """Switch to original dataset"""
    try:
        global listings_data, current_dataset
        
        # Reload original listings
        listings_data = load_listings()  # This loads from cleaned_listings.csv
        current_dataset = "original"
        
        return jsonify({
            "ok": True,
            "source": current_dataset,
            "count": len(listings_data)
        })
        
    except Exception as e:
        return error_response(f"Failed to switch to original dataset: {str(e)}", 500)

@app.route('/api/dataset/use_synthetic', methods=['POST'])
def use_synthetic_dataset():
    """Generate and use synthetic dataset"""
    try:
        global listings_data, current_dataset
        
        data = request.get_json() or {}
        include_real = data.get('include_real', True)
        fake_rows = min(data.get('fake_rows', 100), 5000)  # Cap at 5000
        
        # Generate synthetic data
        prompt = f"""Generate {fake_rows} realistic Airbnb-style property listings in JSON format.
        Each listing should have these exact fields:
        - name (string): Creative property name
        - location (string): City or area name
        - property_type (string): "entire home", "private room", etc.
        - accommodates (integer): Number of guests (1-16)
        - amenities (string): Comma-separated amenities like "wifi, kitchen, parking"
        - price (float): Price per night (20-800)
        - min_nights (integer): Minimum stay (1-30)
        - max_nights (integer): Maximum stay (30-365)
        - review_rating (float): Rating 1.0-5.0
        - tags (string): Comma-separated tags like "cozy, modern, beach"
        
        Return as a JSON array of objects. Make it diverse and realistic."""
        
        raw_output = generate_synthetic_listings(prompt, LLM_API_KEY)
        
        # Save synthetic listings
        synthetic_file = "synthetic_listings.csv"
        save_synthetic_listings(raw_output, synthetic_file)
        
        # Load synthetic data
        df_synthetic = pd.read_csv(synthetic_file)
        
        if include_real:
            # Merge with real data
            output_file = "merged_listings.csv"
            merge_with_real_listings(
                real_file="cleaned_listings.csv",
                synthetic_file=synthetic_file,
                output_file=output_file
            )
            df_final = pd.read_csv(output_file)
        else:
            df_final = df_synthetic
        
        # Convert to Listing objects
        listings_data = []
        for i, (_, row) in enumerate(df_final.iterrows()):
            listing = Listing(
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
                listing_id=i
            )
            listings_data.append(listing)
        
        current_dataset = "synthetic"
        
        return jsonify({
            "ok": True,
            "source": current_dataset,
            "count": len(listings_data)
        })
        
    except Exception as e:
        return error_response(f"Failed to generate synthetic dataset: {str(e)}", 500)

@app.route('/api/synthetic_csv', methods=['POST'])
def download_synthetic_csv():
    """Generate and download synthetic CSV"""
    try:
        data = request.get_json() or {}
        include_real = data.get('include_real', True)
        fake_rows = min(data.get('fake_rows', 100), 5000)
        
        # Generate synthetic data (same as above)
        prompt = f"""Generate {fake_rows} realistic Airbnb-style property listings in JSON format.
        Each listing should have these exact fields:
        - name (string): Creative property name
        - location (string): City or area name  
        - property_type (string): "entire home", "private room", etc.
        - accommodates (integer): Number of guests (1-16)
        - amenities (string): Comma-separated amenities like "wifi, kitchen, parking"
        - price (float): Price per night (20-800)
        - min_nights (integer): Minimum stay (1-30)
        - max_nights (integer): Maximum stay (30-365)
        - review_rating (float): Rating 1.0-5.0
        - tags (string): Comma-separated tags like "cozy, modern, beach"
        
        Return as a JSON array of objects."""
        
        raw_output = generate_synthetic_listings(prompt, LLM_API_KEY)
        
        # Save to temporary file
        output_file = f"synthetic_listings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_synthetic_listings(raw_output, output_file)
        
        if include_real:
            merge_output = f"merged_listings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            merge_with_real_listings(
                real_file="cleaned_listings.csv",
                synthetic_file=output_file,
                output_file=merge_output
            )
            output_file = merge_output
        
        return send_file(
            output_file,
            as_attachment=True,
            download_name=f"synthetic_listings_{datetime.now().strftime('%Y%m%d')}.csv",
            mimetype='text/csv'
        )
        
    except Exception as e:
        return error_response(f"Failed to generate CSV: {str(e)}", 500)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return error_response("Endpoint not found", 404)

@app.errorhandler(405)
def method_not_allowed(error):
    return error_response("Method not allowed", 405)

@app.errorhandler(500)
def internal_error(error):
    return error_response("Internal server error", 500)

# ==================== MAIN ====================

if __name__ == '__main__':
    print("🚀 Starting StayFinder API Server...")
    print("📊 Initializing data...")
    
    init_data()
    
    print("🌐 Server starting on http://localhost:5000")
    print("📋 Available endpoints:")
    print("   GET  /health")
    print("   GET  /api/listings")
    print("   POST /api/users")
    print("   GET  /api/users/<id>")
    print("   GET  /api/favorites/<user_id>")
    print("   GET  /api/recommend")
    print("   POST /api/book")
    print("   ... and more!")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
