from flask import Blueprint, request, jsonify
from app.db import db  # import the db instance from app/db.py

user_bp = Blueprint("user", __name__, url_prefix="/user")

@user_bp.route("/gender/<int:user_id>", methods=["GET"])
def get_user_gender(user_id):
    try:
        query = "SELECT gender FROM Users WHERE user_id = %s;"
        result = db.execute(query, (user_id,), fetch=True)
        
        if not result or len(result) == 0:
            return jsonify({"error": "User not found"}), 404

        gender = result[0][0]
        return jsonify({"user_id": user_id, "gender": gender})
    except Exception as e:
        return jsonify({"error": "Error retrieving user gender", "details": str(e)}), 500


@user_bp.route("/gender/<int:user_id>", methods=["PUT"])
def set_user_gender(user_id):
    data = request.get_json(silent=True) or {}
    gender = (data.get("gender") or "").strip().lower()

    # fits VARCHAR(10); map any long labels (e.g., "prefer_not_to_say") to "other" on the client
    allowed = {"male", "female", "other"}
    if gender not in allowed:
        return jsonify({"error": "Invalid 'gender'. Use 'male', 'female', or 'other'."}), 400

    try:
        db.execute("UPDATE Users SET gender = %s WHERE user_id = %s;", (gender, user_id))
        return jsonify({"message": "Gender updated successfully", "gender": gender}), 200
    except Exception as e:
        return jsonify({"error": "Error updating gender", "details": str(e)}), 500


@user_bp.route("/level/<int:user_id>", methods=["GET"])
def get_user_level(user_id):
    try:
        query = "SELECT level FROM Users WHERE user_id = %s;"
        result = db.execute(query, (user_id,), fetch=True)

        if not result or len(result) == 0:
            return jsonify({"error": "User not found"}), 404

        level = result[0][0]
        return jsonify({"user_id": user_id, "level": level}), 200

    except Exception as e:
        return jsonify({"error": "Error retrieving user level", "details": str(e)}), 500


@user_bp.route("/level/<int:user_id>", methods=["PUT"])
def set_user_level(user_id):
    data = request.get_json(silent=True) or {}
    level = data.get("level")

    try:
        level = int(level)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'level'. Use 1..4."}), 400

    if level not in (1, 2, 3, 4):  # Newcomer..Advanced
        return jsonify({"error": "Invalid 'level'. Use 1..4."}), 400

    try:
        db.execute("UPDATE Users SET level = %s WHERE user_id = %s;", (level, user_id))
        return jsonify({"message": "Level updated successfully", "level": level}), 200
    except Exception as e:
        return jsonify({"error": "Error updating level", "details": str(e)}), 500


@user_bp.route("/current_venue/<int:user_id>", methods=["GET"])
def get_current_venue(user_id):
    try:
        query = "SELECT current_venue_id FROM Users WHERE user_id = %s;"
        result = db.execute(query, (user_id,), fetch=True)
        
        if not result or len(result) == 0:
            return jsonify({"error": "User not found"}), 404

        current_venue_id = result[0][0]
        return jsonify({"user_id": user_id, "current_venue_id": current_venue_id})
    except Exception as e:
        return jsonify({"error": "Error retrieving user's current venue id", "details": str(e)}), 500
    

@user_bp.route("/current_venue/<int:user_id>", methods=["PUT"])
def set_current_venue(user_id):
    data = request.get_json(silent=True)
    if not data or "venue_id" not in data:
        return jsonify({"error": "Missing 'venue_id' in request body"}), 400

    venue_id = data["venue_id"]

    try:
        # Check if the venue exists and belongs to the user
        check_query = "SELECT venue_id FROM Venues WHERE venue_id = %s AND user_id = %s;"
        result = db.execute(check_query, (venue_id, user_id), fetch=True)

        if not result:
            return jsonify({"error": "Venue not found or does not belong to user"}), 404

        # Update the current_venue_id
        update_query = "UPDATE Users SET current_venue_id = %s WHERE user_id = %s;"
        db.execute(update_query, (venue_id, user_id))

        return jsonify({"message": "Current venue updated successfully", "user_id": user_id, "current_venue_id": venue_id}), 200

    except Exception as e:
        return jsonify({"error": "Error updating current venue", "details": str(e)}), 500


@user_bp.route("/name/<int:user_id>", methods=["PUT"])
def update_user_name(user_id):
    data = request.get_json(silent=True)
    new_name = data.get("name")

    if not new_name:
        return jsonify({"error": "Missing 'name' in request body"}), 400

    try:
        db.execute("UPDATE Users SET name = %s WHERE user_id = %s;", (new_name, user_id))
        return jsonify({"message": "Name updated successfully", "name": new_name}), 200
    except Exception as e:
        return jsonify({"error": "Error updating name", "details": str(e)}), 500
    

@user_bp.route("/email/<int:user_id>", methods=["PUT"])
def update_user_email(user_id):
    data = request.get_json(silent=True)
    new_email = data.get("email")

    if not new_email:
        return jsonify({"error": "Missing 'email' in request body"}), 400

    try:
        db.execute("UPDATE Users SET email = %s WHERE user_id = %s;", (new_email, user_id))
        return jsonify({"message": "Email updated successfully", "email": new_email}), 200
    except Exception as e:
        return jsonify({"error": "Error updating email", "details": str(e)}), 500


@user_bp.route("/birthday/<int:user_id>", methods=["PUT"])
def update_user_birthday(user_id):
    data = request.get_json(silent=True)
    new_birthday = data.get("birthday")  # Expected in format "mm/dd/yyyy"

    if not new_birthday:
        return jsonify({"error": "Missing 'birthday' in request body"}), 400

    try:
        # Convert to SQL date format yyyy-mm-dd
        from datetime import datetime
        parsed_date = datetime.strptime(new_birthday, "%m/%d/%Y").date()

        db.execute("UPDATE Users SET birthday = %s WHERE user_id = %s;", (parsed_date, user_id))
        return jsonify({"message": "Birthday updated successfully", "birthday": new_birthday}), 200
    except ValueError:
        return jsonify({"error": "Invalid birthday format. Use mm/dd/yyyy."}), 400
    except Exception as e:
        return jsonify({"error": "Error updating birthday", "details": str(e)}), 500


@user_bp.route("/workout_frequency/<int:user_id>", methods=["GET"])
def get_workout_frequency(user_id):
    try:
        query = """
            SELECT v.workout_frequency
            FROM Venues v
            JOIN Users u ON v.venue_id = u.current_venue_id
            WHERE u.user_id = %s;
        """
        result = db.execute(query, (user_id,), fetch=True)

        if not result:
            return jsonify({"error": "Workout frequency not found for user"}), 404

        return jsonify({"user_id": user_id, "workout_frequency": result[0][0]}), 200

    except Exception as e:
        return jsonify({"error": "Error retrieving workout frequency", "details": str(e)}), 500


@user_bp.route("/workout_frequency/<int:user_id>", methods=["PUT"])
def set_workout_frequency(user_id):
    data = request.get_json(silent=True)
    new_frequency = data.get("workout_frequency")

    if new_frequency is None:
        return jsonify({"error": "Missing 'workout_frequency' in request body"}), 400

    try:
        # Update the workout_frequency for the user's current venue
        update_query = """
            UPDATE Venues
            SET workout_frequency = %s
            WHERE venue_id = (
                SELECT current_venue_id FROM Users WHERE user_id = %s
            );
        """
        db.execute(update_query, (new_frequency, user_id))

        return jsonify({"message": "Workout frequency updated successfully", "workout_frequency": new_frequency}), 200

    except Exception as e:
        return jsonify({"error": "Error updating workout frequency", "details": str(e)}), 500
