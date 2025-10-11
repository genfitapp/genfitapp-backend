from flask import Blueprint, request, jsonify
from app.db import db  # import the db instance from app/db.py
from .utils import gym_equipment, INDEX_TO_SETUP, set_gym_setup, seed_venue_equipment_from_setup
from ..workout.utils import get_training_phase_and_group_for_day, get_reps_and_rest_time

venues_bp = Blueprint("venues", __name__, url_prefix="/venues")

@venues_bp.route("/", methods=["POST"])
def get_venues():
    data = request.get_json(silent=True)
    user_token = data.get('user_token') if data else None

    if not user_token:
        return jsonify({"error": "Please send request with valid token"}), 400

    try:
        query = "SELECT venue_id, name FROM Venues WHERE user_id = %s;"
        results = db.execute(query, (user_token,), fetch=True)
        venues = [{"venue_id": row[0], "name": row[1]} for row in results]
    except Exception as e:
        return jsonify({"error": 'Error retrieving venues list'}), 500

    try:
        query = "SELECT current_venue_id FROM Users WHERE user_id = %s;"
        results = db.execute(query, (user_token,), fetch=True)
        
        if results and len(results) > 0:
            current_venue_id = results[0][0]
        else:
            return jsonify({"error": 'Error retrieving current venue id'}), 500

    except Exception as e:
        return jsonify({"error": 'Error retrieving venues list'}), 500

    return jsonify({"venues": venues, 'current_venue_id': current_venue_id})


@venues_bp.route("/<int:venue_id>/pain_points", methods=["GET"])
def get_pain_points(venue_id):
    try:
        query = "SELECT pain_points FROM Venues WHERE venue_id = %s;"
        result = db.execute(query, (venue_id,), fetch=True)
        if not result or not result[0]:
            return jsonify({"error": "Venue not found"}), 404

        pain_points = result[0][0]  # This is already a list of strings
        return jsonify({"pain_points": pain_points})
    except Exception as e:
        print(e)
        return jsonify({"error": "Error fetching pain points", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/pain_points", methods=["PUT"])
def edit_pain_points(venue_id):
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Expecting a JSON payload like {"pain_points": ["Lower back", "Shoulders", ...]}
    new_pain_points = [p.split()[0] for p in data.get("pain_points")]
    # print(new_pain_points)
    
    if new_pain_points is None:
        return jsonify({"error": "No pain_points provided"}), 400

    try:
        # Update the pain_points column for the specified venue
        update_query = """
            UPDATE Venues
            SET pain_points = %s
            WHERE venue_id = %s
            RETURNING pain_points;
        """
        result = db.execute(update_query, (new_pain_points, venue_id), fetch=True)
        
        if not result:
            return jsonify({"error": "Venue not found"}), 404

        updated_pain_points = result[0][0]
        
        return jsonify({
            "message": "Pain points updated successfully",
            "pain_points": updated_pain_points
        })
    except Exception as e:
        return jsonify({"error": "Error updating pain points", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/goals", methods=["GET"])
def get_goals(venue_id):
    try:
        query = "SELECT goals FROM Venues WHERE venue_id = %s;"
        result = db.execute(query, (venue_id,), fetch=True)
        
        if not result or not result[0]:
            return jsonify({"error": "Venue not found"}), 404

        goals = result[0][0]  # This should be a list of strings (TEXT[])
        return jsonify({"goals": goals})
    except Exception as e:
        return jsonify({"error": "Error fetching goals", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/goals", methods=["PUT"])
def update_goals(venue_id):
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "No data provided"}), 400

    new_goals = data.get("goals")
    if new_goals is None:
        return jsonify({"error": "No goals provided"}), 400

    try:
        update_query = """
            UPDATE Venues
            SET goals = %s
            WHERE venue_id = %s
            RETURNING goals;
        """
        result = db.execute(update_query, (new_goals, venue_id), fetch=True)
        if not result:
            return jsonify({"error": "Venue not found"}), 404

        updated_goals = result[0][0]

        return jsonify({
            "message": "Goals updated successfully",
            "goals": updated_goals
        })
    except Exception as e:
        return jsonify({"error": "Error updating goals", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/priority_muscles", methods=["GET"])
def get_priority_muscles(venue_id):
    try:
        query = "SELECT priority_muscles FROM Venues WHERE venue_id = %s;"
        result = db.execute(query, (venue_id,), fetch=True)
        
        if not result or not result[0]:
            return jsonify({"error": "Venue not found"}), 404

        priority_muscles = result[0][0]
        return jsonify({"venue_id": venue_id, "priority_muscles": priority_muscles})
    except Exception as e:
        return jsonify({"error": "Error fetching priority muscles", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/priority_muscles", methods=["PUT"])
def update_priority_muscles(venue_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    new_priority_muscles = data.get("priority_muscles")
    if new_priority_muscles is None:
        return jsonify({"error": "No priority_muscles provided"}), 400

    try:
        update_query = """
            UPDATE Venues
            SET priority_muscles = %s
            WHERE venue_id = %s
            RETURNING priority_muscles;
        """
        result = db.execute(update_query, (new_priority_muscles, venue_id), fetch=True)
        if not result:
            return jsonify({"error": "Venue not found"}), 404

        updated_priority_muscles = result[0][0]
        return jsonify({
            "message": "Priority muscles updated successfully",
            "priority_muscles": updated_priority_muscles
        })
    except Exception as e:
        return jsonify({"error": "Error updating priority muscles", "details": str(e)}), 500
    

# routes/venues.py
@venues_bp.route("/gym_setup/<int:venue_id>", methods=["GET"])
def get_gym_setup_route(venue_id):
    try:
        rows = db.execute(
            "SELECT gym_setup FROM Venues WHERE venue_id = %s;",
            (venue_id,),
            fetch=True,              # ✅ use fetch=True (list of tuples)
        )
        if not rows:
            return jsonify({"error": "Venue not found"}), 404

        val = rows[0][0]            # first row, first column (int or None)
        return jsonify({
            "venue_id": venue_id,
            "gym_setup": val,
            "gym_setup_label": INDEX_TO_SETUP.get(val) if val else None,
        }), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch gym setup", "details": str(e)}), 500


@venues_bp.route("/gym_setup/<int:venue_id>", methods=["PUT"])
def set_gym_setup_route(venue_id):
    data = request.get_json(silent=True) or {}
    val = data.get("gym_setup")
    print(val)
    try:
        val = int(val)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'gym_setup'. Use 1..5."}), 400
    if val not in (1, 2, 3, 4, 5):
        return jsonify({"error": "Invalid 'gym_setup'. Use 1..5."}), 400

    try:
        set_gym_setup(db, venue_id, val)
        summary = seed_venue_equipment_from_setup(
            db,
            venue_id=venue_id,
            setup_index=val,
            index_to_setup=INDEX_TO_SETUP,
            gym_equipment=gym_equipment,
            replace=True,  # set False if you want to merge instead of replace
        )
    except Exception as e:
        # Setup was updated; equipment seeding failed → partial success
        return jsonify({
            "message": "Gym setup updated, but equipment population encountered an error.",
            "gym_setup": val,
            "error": str(e),
        }), 207

    return jsonify({
        "message": "Gym setup updated successfully",
        "gym_setup": val,
        "seed_summary": summary,
    }), 200


""" ///////////////////////////////////////////////////////////////////////////////////////// """
@venues_bp.route("/<int:venue_id>/days_of_week", methods=["GET"])
def get_days_of_week(venue_id):
    try:
        query = "SELECT days_of_week FROM Venues WHERE venue_id = %s;"
        result = db.execute(query, (venue_id,), fetch=True)
        if not result or not result[0]:
            return jsonify({"error": "Venue not found"}), 404

        days_of_week = result[0][0]
        return jsonify({"venue_id": venue_id, "days_of_week": days_of_week})
    except Exception as e:
        return jsonify({"error": "Error fetching days of week", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/days_of_week", methods=["PUT"])
def update_days_of_week(venue_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    new_days = data.get("days_of_week")
    if new_days is None:
        return jsonify({"error": "No days_of_week provided"}), 400

    try:
        update_query = """
            UPDATE Venues
            SET days_of_week = %s
            WHERE venue_id = %s
            RETURNING days_of_week;
        """
        result = db.execute(update_query, (new_days, venue_id), fetch=True)
        if not result:
            return jsonify({"error": "Venue not found"}), 404

        updated_days = result[0][0]
        return jsonify({
            "message": "Days of week updated successfully",
            "days_of_week": updated_days
        })
    except Exception as e:
        return jsonify({"error": "Error updating days of week", "details": str(e)}), 500


# ----- TIME PER WORKOUT -----

@venues_bp.route("/<int:venue_id>/time_per_workout", methods=["GET"])
def get_time_per_workout(venue_id):
    try:
        query = "SELECT time_per_workout FROM Venues WHERE venue_id = %s;"
        result = db.execute(query, (venue_id,), fetch=True)
        if not result or not result[0]:
            return jsonify({"error": "Venue not found"}), 404

        time_per_workout = result[0][0]
        return jsonify({"venue_id": venue_id, "time_per_workout": time_per_workout})
    except Exception as e:
        return jsonify({"error": "Error fetching time per workout", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/time_per_workout", methods=["PUT"])
def update_time_per_workout(venue_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    new_time = data.get("time_per_workout")
    if new_time is None:
        return jsonify({"error": "No time_per_workout provided"}), 400

    try:
        update_query = """
            UPDATE Venues
            SET time_per_workout = %s
            WHERE venue_id = %s
            RETURNING time_per_workout;
        """
        result = db.execute(update_query, (new_time, venue_id), fetch=True)
        if not result:
            return jsonify({"error": "Venue not found"}), 404

        updated_time = result[0][0]
        return jsonify({
            "message": "Time per workout updated successfully",
            "time_per_workout": updated_time
        })
    except Exception as e:
        return jsonify({"error": "Error updating time per workout", "details": str(e)}), 500

# ----- REST TIME BETWEEN SET -----

@venues_bp.route("/<int:venue_id>/rest_time_between_set", methods=["GET"])
def get_rest_time_between_set(venue_id):
    try:
        query = "SELECT rest_time_between_set FROM Venues WHERE venue_id = %s;"
        result = db.execute(query, (venue_id,), fetch=True)
        if not result or not result[0]:
            return jsonify({"error": "Venue not found"}), 404

        rest_time = result[0][0]
        return jsonify({"venue_id": venue_id, "rest_time_between_set": rest_time})
    except Exception as e:
        return jsonify({"error": "Error fetching rest time between set", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/rest_time_between_set", methods=["PUT"])
def update_rest_time_between_set(venue_id):
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"error": "No data provided"}), 400

    new_rest_time = data.get("rest_time_between_set")
    use_default  = data.get("use_default")
    
    if new_rest_time is None:
        return jsonify({"error": "No rest_time_between_set provided"}), 400

    if use_default is not None and use_default or new_rest_time == 0:
        goals = data.get('goals')
        split = data.get('split')
        workout_count = data.get('workout_count')

        training_phase, _ = get_training_phase_and_group_for_day(goals, split, workout_count)
        new_rest_time = get_reps_and_rest_time(training_phase)["rest_time"] * 60

    try:
        update_query = """
            UPDATE Venues
            SET rest_time_between_set = %s
            WHERE venue_id = %s
            RETURNING rest_time_between_set;
        """
        result = db.execute(update_query, (new_rest_time, venue_id), fetch=True)
        if not result:
            return jsonify({"error": "Venue not found"}), 404

        updated_rest_time = result[0][0]
        print("Rest timer is: ", updated_rest_time)
        return jsonify({
            "message": "Rest time between set updated successfully",
            "rest_time_between_set": updated_rest_time
        })
    except Exception as e:
        return jsonify({"error": "Error updating rest time between set", "details": str(e)}), 500

# ----- SPLIT -----

@venues_bp.route("/<int:venue_id>/split", methods=["GET"])
def get_split(venue_id):
    try:
        query = "SELECT split FROM Venues WHERE venue_id = %s;"
        result = db.execute(query, (venue_id,), fetch=True)
        if not result or not result[0]:
            return jsonify({"error": "Venue not found"}), 404

        split_value = result[0][0]
        return jsonify({"venue_id": venue_id, "split": split_value})
    except Exception as e:
        return jsonify({"error": "Error fetching split", "details": str(e)}), 500


@venues_bp.route("/<int:venue_id>/split", methods=["PUT"])
def update_split(venue_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    new_split = data.get("split")
    if new_split is None:
        return jsonify({"error": "No split provided"}), 400

    try:
        update_query = """
            UPDATE Venues
            SET split = %s
            WHERE venue_id = %s
            RETURNING split, user_id;
        """
        result = db.execute(update_query, (new_split, venue_id), fetch=True)
        if not result:
            return jsonify({"error": "Venue not found"}), 404

        updated_split, user_id = result[0]

        reset_query = """
            UPDATE Users
            SET workout_number = 0
            WHERE user_id = %s
        """
        db.execute(reset_query, (user_id,))

        return jsonify({
            "message": "Split updated successfully",
            "split": updated_split
        })
    except Exception as e:
        print("Error split: ", e)
        return jsonify({"error": "Error updating split", "details": str(e)}), 500


# ----- CREATE VENUE -----
@venues_bp.route("/<int:user_id>/create", methods=["POST"])
def create_venue(user_id):
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"error": "No data provided"}), 400

    venue_name = data.get("name")
    
    if not venue_name:
        return jsonify({"error": "Venue name is required"}), 400

    # Check for duplicate name
    try:
        check_query = "SELECT venue_id FROM Venues WHERE user_id = %s AND LOWER(name) = LOWER(%s);"
        existing = db.execute(check_query, (user_id, venue_name), fetch=True)
        if existing:
            return jsonify({"error": "This venue name already exists"}), 400
    except Exception as e:
        print("Error 1")
        return jsonify({"error": "Error checking for existing venue", "details": str(e)}), 500

    def to_pg_array(pylist):
        return pylist if isinstance(pylist, list) else None

    # Optional fields from frontend
    priority_muscles = to_pg_array(data.get("priority_muscles"))
    pain_points = to_pg_array(data.get("pain_points"))
    split = data.get("split")
    days_of_week = to_pg_array(data.get("days_of_week"))
    time_per_workout = data.get("time_per_workout")
    rest_time_between_set = data.get("rest_time_between_set")
    workout_frequency = len(days_of_week) if days_of_week else None
    equipment_list = data.get("equipment", [])

    # Defaults from last venue
    try:
        default_query = """
            SELECT gym_setup, goals, workout_frequency
            FROM Venues
            WHERE user_id = %s
            ORDER BY venue_id DESC
            LIMIT 1;
        """
        last_venue = db.execute(default_query, (user_id,), fetch=True)
        if last_venue:
            gym_setup, goals, default_workout_frequency = last_venue[0]
            goals = to_pg_array(goals)

            if not workout_frequency:
                workout_frequency = default_workout_frequency
        else:
            gym_setup = None
            goals = None
    except Exception as e:
        print("Error 2")
        return jsonify({"error": "Error retrieving previous venue settings", "details": str(e)}), 500

    # Insert new venue
    try:
        insert_query = """
            INSERT INTO Venues (
                name, user_id, gym_setup, goals, priority_muscles, pain_points,
                split, days_of_week, workout_frequency, time_per_workout, rest_time_between_set
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING venue_id;
        """
        venue_id = db.execute(
            insert_query,
            (
                venue_name,
                user_id,
                gym_setup,
                goals,
                priority_muscles,
                pain_points,
                split,
                days_of_week,
                workout_frequency,
                time_per_workout,
                rest_time_between_set
            ),
            fetch=True
        )[0][0]

        # Add venue equipment
        for item in equipment_list:
            equipment_id = item.get("equipment_id")
            quantity = item.get("quantity", 1)

            if equipment_id:
                db.execute(
                    """
                    INSERT INTO Venue_equipment (venue_id, equipment_id, quantity)
                    VALUES (%s, %s, %s);
                    """,
                    (venue_id, equipment_id, quantity)
                )

        return jsonify({"message": "Venue created successfully", "venue_id": venue_id}), 200

    except Exception as e:
        print("Error 333")
        print(e)
        return jsonify({"error": "Error creating venue", "details": str(e)}), 500
    

@venues_bp.route("/<int:user_id>/create_simple_venue", methods=["POST"])
def create_simple_venue(user_id):
    from flask import request, jsonify
    from app.db import db  # Adjust based on your actual import path

    data = request.get_json(silent=True)

    if not data or "name" not in data:
        return jsonify({"error": "Missing 'name' in request body"}), 400

    venue_name = data["name"]

    try:
        # Step 1: Check if user exists
        user_check = db.execute("SELECT user_id FROM Users WHERE user_id = %s;", (user_id,), fetch=True)
        if not user_check:
            return jsonify({"error": "User not found"}), 404

        # Step 2: Prevent duplicate venue names (case-insensitive)
        check_query = "SELECT venue_id FROM Venues WHERE user_id = %s AND LOWER(name) = LOWER(%s);"
        existing = db.execute(check_query, (user_id, venue_name), fetch=True)
        if existing:
            return jsonify({"error": "This venue name already exists for the user"}), 400

        # Step 3: Get user's current venue ID
        current_venue_result = db.execute(
            "SELECT current_venue_id FROM Users WHERE user_id = %s;", 
            (user_id,), fetch=True
        )
        if not current_venue_result or not current_venue_result[0][0]:
            return jsonify({"error": "User has no current venue set"}), 400

        current_venue_id = current_venue_result[0][0]

        # Step 4: Fetch current venue's settings
        fetch_settings_query = """
            SELECT gym_setup, goals, priority_muscles, pain_points, split, days_of_week,
                   workout_frequency, time_per_workout, rest_time_between_set
            FROM Venues
            WHERE venue_id = %s;
        """
        settings = db.execute(fetch_settings_query, (current_venue_id,), fetch=True)

        if not settings:
            return jsonify({"error": "Failed to fetch current venue settings"}), 500

        (
            gym_setup, goals, priority_muscles, pain_points, split, days_of_week,
            workout_frequency, time_per_workout, rest_time_between_set
        ) = settings[0]

        # Step 5: Insert the new venue with copied settings
        insert_query = """
            INSERT INTO Venues (
                name, user_id, gym_setup, goals, priority_muscles, pain_points, split,
                days_of_week, workout_frequency, time_per_workout, rest_time_between_set
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING venue_id;
        """
        result = db.execute(insert_query, (
            venue_name, user_id, gym_setup, goals, priority_muscles, pain_points, split,
            days_of_week, workout_frequency, time_per_workout, rest_time_between_set
        ), fetch=True)

        new_venue_id = result[0][0]

        return jsonify({
            "message": "Venue created successfully",
            "venue_id": new_venue_id,
            "user_id": user_id,
            "name": venue_name
        }), 201

    except Exception as e:
        return jsonify({"error": "Error creating venue", "details": str(e)}), 500



# # ----- DELETE VENUE -----
@venues_bp.route("/<int:user_id>/delete/<int:venue_id>", methods=["DELETE"])
def delete_venue(user_id, venue_id):
    try:
        # Verify the venue exists and belongs to the user
        check_query = "SELECT venue_id FROM Venues WHERE venue_id = %s AND user_id = %s;"
        result = db.execute(check_query, (venue_id, user_id), fetch=True)
        
        if not result:
            return jsonify({"error": "Venue not found or does not belong to this user"}), 404

        # Get all venues belonging to this user
        all_venues_query = "SELECT venue_id FROM Venues WHERE user_id = %s ORDER BY venue_id;"
        all_venues = db.execute(all_venues_query, (user_id,), fetch=True)

        if len(all_venues) <= 1:
            return jsonify({"error": "You must have at least one venue. Cannot delete your only venue."}), 400

        # Determine next venue_id for setting current_venue_id
        next_venue_id = None
        for v in all_venues:
            if v[0] != venue_id:
                next_venue_id = v[0]
                break

        # Delete associated equipment
        db.execute("DELETE FROM Venue_equipment WHERE venue_id = %s;", (venue_id,))

        # Delete the venue
        db.execute("DELETE FROM Venues WHERE venue_id = %s;", (venue_id,))

        # Set current_venue_id to another remaining venue
        db.execute(
            "UPDATE Users SET current_venue_id = %s WHERE user_id = %s;",
            (next_venue_id, user_id)
        )

        return jsonify({
            "message": "Venue deleted successfully",
            "current_venue_id": next_venue_id
        }), 200

    except Exception as e:
        return jsonify({"error": "Error deleting venue", "details": str(e)}), 500
