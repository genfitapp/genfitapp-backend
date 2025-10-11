from flask import Blueprint, request, jsonify
from app.db import db  # import the db instance from app/db.py
# import json

equipment_bp = Blueprint("equipment", __name__, url_prefix="/equipment")


@equipment_bp.route("/<int:user_id>", methods=["GET"])
def get_equipment(user_id):
    try:
        # Retrieve the user's current venue id.
        venue_query = "SELECT current_venue_id FROM Users WHERE user_id = %s;"
        venue_result = db.execute(venue_query, (user_id,), fetch=True)
        
        if not venue_result or not venue_result[0]:
            return jsonify({"error": "User not found or current venue not set"}), 404

        current_venue_id = venue_result[0][0]

        # Retrieve all equipment associated with the user's current venue.
        equipment_query = """
            SELECT e.equipment_id, e.name, e.weight_resistance_time, ve.quantity
            FROM Venue_equipment ve
            JOIN equipment e ON ve.equipment_id = e.equipment_id
            WHERE ve.venue_id = %s;
        """
        equipment_results = db.execute(equipment_query, (current_venue_id,), fetch=True)

        equipment_list = [{
            "id": row[0],
            "name": row[1],
            "weight_resistance_time": row[2],
            "quantity": row[3]
        } for row in equipment_results]

    except Exception as e:
        return jsonify({"error": "Error retrieving equipment", "details": str(e)}), 500

    return jsonify({"equipment": equipment_list})


@equipment_bp.route("/free_weight_type/<string:name>", methods=["GET"])
def get_equipment_by_type(name):
    try:
        query = """
            SELECT 
                equipment_id,
                name,
                weight_resistance_time
            FROM equipment
            WHERE LOWER(name) LIKE %s;
        """
        pattern = f"%{name.lower()}%"
        results = db.execute(query, (pattern,), fetch=True)

        equipment_list = [{
            "equipment_id": row[0],
            "name": row[1],
            "weight_resistance_time": row[2]
        } for row in results]

        return jsonify({"equipment": equipment_list})

    except Exception as e:
        return jsonify({"error": f"Error retrieving equipment for type '{name}'", "details": str(e)}), 500


# Return the list of free weight equipment associated with the user based on the name -> Dumbbells/Kettlebells
@equipment_bp.route("/free_weight/<string:name>/<int:user_id>", methods=["GET"])
def get_free_weight(name, user_id):
    try:
        query = """
            SELECT 
                e.equipment_id,
                e.name,
                ve.quantity,
                e.weight_resistance_time
            FROM Users u
            JOIN Venues v ON u.current_venue_id = v.venue_id
            JOIN Venue_equipment ve ON v.venue_id = ve.venue_id
            JOIN equipment e ON ve.equipment_id = e.equipment_id
            WHERE u.user_id = %s
              AND LOWER(e.name) LIKE %s;
        """
        # Build a wildcard pattern for filtering
        pattern = f"%{name.lower()}%"
        results = db.execute(query, (user_id, pattern), fetch=True)
        free_weights = [{
            "equipment_id": row[0],
            "name": row[1],
            "quantity": row[2],
            "weight_resistance_time": row[3]
        } for row in results]
    except Exception as e:
        return jsonify({"error": f"Error retrieving free weight {name}", "details": str(e)}), 500
    return jsonify({"data": free_weights})

    

@equipment_bp.route("/update/<int:equipment_id>/<int:user_id>", methods=["POST"])
def update_user_equipment(equipment_id, user_id):
    try:
        # 1. Retrieve the user's current venue id.
        query = "SELECT current_venue_id FROM Users WHERE user_id = %s;"
        result = db.execute(query, (user_id,), fetch=True)
        
        if not result or not result[0]:
            return jsonify({"error": "User not found or no current venue set"}), 404

        current_venue_id = result[0][0]

        # 2. Check if the equipment is already associated with this venue.
        check_query = """
            SELECT venue_equipment_id FROM Venue_equipment
            WHERE venue_id = %s AND equipment_id = %s;
        """
        check_result = db.execute(check_query, (current_venue_id, equipment_id), fetch=True)

        if check_result and len(check_result) > 0:
            # Equipment exists; remove it.
            delete_query = """
                DELETE FROM Venue_equipment
                WHERE venue_id = %s AND equipment_id = %s;
            """
            db.execute(delete_query, (current_venue_id, equipment_id))
            action = "removed"
        else:
            # Equipment does not exist; add it with a default quantity (e.g. 1).
            insert_query = """
                INSERT INTO Venue_equipment (venue_id, equipment_id, quantity)
                VALUES (%s, %s, %s);
            """
            db.execute(insert_query, (current_venue_id, equipment_id, 1))
            action = "added"

    except Exception as e:
        return jsonify({"error": "Error updating user equipment", "details": str(e)}), 500
    
    return jsonify({"data": f"Equipment {action} successfully"})


@equipment_bp.route("/id_by_name_weight/<string:name>/<string:weight>", methods=["GET"])
def get_equipment_by_name_and_weight(name, weight):
    try:
        query = """
            SELECT equipment_id, name, weight_resistance_time 
            FROM equipment
            WHERE LOWER(name) = %s
              AND weight_resistance_time = %s;
        """
        results = db.execute(query, (name.lower(), str(float(weight))), fetch=True)

        if results and len(results) > 0:
            return jsonify({
                "equipment_id": results[0][0],
                "name": results[0][1],
                "weight_resistance_time": results[0][2]
            })
        else:
            return jsonify({"error": "Equipment not found"}), 404
    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@equipment_bp.route("/id_free_weight/<string:name>/<string:weight_resistance>/<int:quantity>/<int:user_id>", methods=["GET"])
def get_free_weight_equipment_id(name, weight_resistance, quantity, user_id):
    try:
        query = """
            SELECT e.equipment_id 
            FROM equipment e
            JOIN Venue_equipment ve ON e.equipment_id = ve.equipment_id
            JOIN Venues v ON ve.venue_id = v.venue_id
            JOIN Users u ON v.venue_id = u.current_venue_id
            WHERE LOWER(e.name) = %s 
              AND e.weight_resistance_time = %s 
              AND ve.quantity = %s
              AND u.user_id = %s;
        """
        results = db.execute(query, (name.lower(), str(float(weight_resistance)), quantity, user_id), fetch=True)
        if results and len(results) > 0:
            equipment_id = results[0][0]
            return jsonify({"equipment_id": equipment_id})
        else:
            return jsonify({"error": "Equipment not found"}), 404
    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@equipment_bp.route("/id/<string:name>", methods=["GET"])
def get_equipment_id_by_name(name):
    try:
        query = "SELECT equipment_id FROM equipment WHERE name = %s;"
        results = db.execute(query, (name,), fetch=True)
        if results and len(results) > 0:
            equipment_id = results[0][0]
            return jsonify({"equipment_id": equipment_id})
        else:
            return jsonify({"error": "Equipment not found"}), 404
    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@equipment_bp.route("/add", methods=["POST"])
def add_equipment():
    data = request.get_json(silent=True)
    if not data:
        print(1)
        return jsonify({"error": "No data provided"}), 400

    user_id = data.get("user_id")
    equipment_id = data.get("equipment_id")
    # Keep None here so we can detect "not provided" and trigger bulk mode.
    quantity = data.get("quantity", None)

    if not user_id or not equipment_id:
        print(user_id, equipment_id)
        return jsonify({"error": "user_id and equipment_id are required"}), 400

    try:
        # 1) Find user's current venue
        venue_q = "SELECT current_venue_id FROM Users WHERE user_id = %s;"
        venue_r = db.execute(venue_q, (user_id,), fetch=True)
        if not venue_r or not venue_r[0]:
            return jsonify({"error": "User not found or current venue not set"}), 404
        current_venue_id = venue_r[0][0]

        # If quantity is provided (even 0), use single-item behavior (update/insert that one id).
        if quantity is not None:
            # Check if already exists
            check_q = """
                SELECT venue_equipment_id FROM Venue_equipment
                WHERE venue_id = %s AND equipment_id = %s;
            """
            exists = db.execute(check_q, (current_venue_id, equipment_id), fetch=True)

            if exists:
                update_q = """
                    UPDATE Venue_equipment
                    SET quantity = %s
                    WHERE venue_id = %s AND equipment_id = %s;
                """
                db.execute(update_q, (quantity, current_venue_id, equipment_id))
                return jsonify({"message": "Equipment quantity updated successfully"}), 200
            else:
                insert_q = """
                    INSERT INTO Venue_equipment (venue_id, equipment_id, quantity)
                    VALUES (%s, %s, %s);
                """
                db.execute(insert_q, (current_venue_id, equipment_id, quantity))
                return jsonify({"message": "Equipment added successfully"}), 200

        # --- Bulk add path (quantity is null / not provided) ---
        # 2) Look up the base equipment name for the provided equipment_id
        name_q = "SELECT name FROM equipment WHERE equipment_id = %s;"
        name_r = db.execute(name_q, (equipment_id,), fetch=True)
        if not name_r:
            return jsonify({"error": "equipment_id not found"}), 404
        base_name = name_r[0][0]

        # 3) Gather all equipment_ids with same name and non-empty weight_resistance_time
        variants_q = """
            SELECT equipment_id
            FROM equipment
            WHERE name = %s
              AND weight_resistance_time IS NOT NULL
              AND TRIM(weight_resistance_time) <> '';
        """
        variant_rows = db.execute(variants_q, (base_name,), fetch=True) or []
        variant_ids = [row[0] for row in variant_rows]

        if not variant_ids:
            # If none qualify, just fall back to adding the provided one with quantity 2
            fallback_insert = """
                INSERT INTO Venue_equipment (venue_id, equipment_id, quantity)
                VALUES (%s, %s, %s);
            """
            db.execute(fallback_insert, (current_venue_id, equipment_id, 2))
            return jsonify({
                "message": "No variants found; added the provided equipment with quantity 2"
            }), 200

        # 4) Fetch what's already present to avoid duplicates
        existing_q = """
            SELECT equipment_id
            FROM Venue_equipment
            WHERE venue_id = %s AND equipment_id = ANY(%s);
        """
        existing_rows = db.execute(existing_q, (current_venue_id, variant_ids), fetch=True) or []
        existing_set = {row[0] for row in existing_rows}

        to_insert = [eid for eid in variant_ids if eid not in existing_set]

        # 5) Insert new ones with default quantity = 2
        if to_insert:
            insert_many_q = """
                INSERT INTO Venue_equipment (venue_id, equipment_id, quantity)
                VALUES (%s, %s, %s);
            """
            for eid in to_insert:
                db.execute(insert_many_q, (current_venue_id, eid, 2))

        added_count = len(to_insert)
        skipped_count = len(variant_ids) - added_count

        return jsonify({
            "message": "Bulk equipment assignment complete",
            "base_name": base_name,
            "added": added_count,
            "skipped_already_present": skipped_count
        }), 200

    except Exception as e:
        return jsonify({"error": "Error adding equipment", "details": str(e)}), 500


@equipment_bp.route("/remove", methods=["POST"])
def remove_equipment():
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = data.get("user_id")
    equipment_id = data.get("equipment_id")
    
    if not user_id or not equipment_id:
        return jsonify({"error": "user_id and equipment_id are required"}), 400

    try:
        # Retrieve the user's current venue ID
        query = "SELECT current_venue_id FROM Users WHERE user_id = %s;"
        result = db.execute(query, (user_id,), fetch=True)
        
        if not result or not result[0]:
            return jsonify({"error": "User not found or current venue not set"}), 404
        
        current_venue_id = result[0][0]
        
        # Check if the equipment exists in the user's list
        check_query = """
            SELECT venue_equipment_id FROM Venue_equipment
            WHERE venue_id = %s AND equipment_id = %s;
        """
        
        check_result = db.execute(check_query, (current_venue_id, equipment_id), fetch=True)
        
        if not check_result or len(check_result) == 0:
            return jsonify({"error": "Equipment not found in user's list"}), 404
        
        # Remove the equipment record
        delete_query = """
            DELETE FROM Venue_equipment
            WHERE venue_id = %s AND equipment_id = %s;
        """
        db.execute(delete_query, (current_venue_id, equipment_id))
    except Exception as e:
        return jsonify({"error": "Error removing equipment", "details": str(e)}), 500

    return jsonify({"message": "Equipment removed successfully"}), 200
