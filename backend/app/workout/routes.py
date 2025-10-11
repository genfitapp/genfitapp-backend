from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.db import db  # Your database helper
from .utils import recommend_split, workout_generator, determine_user_exercise_weight
from .route_helpers import (
    compute_age, 
    DAY_MAP, 
    build_available_weights, 
    build_exercise_payloads, 
    persist_generated_workout, 
    fetch_exercise_list,
    check_user_equipment_for_exercise,
    get_today_workout,
    workout_has_any_completed_set,
)

workout_bp = Blueprint("workout", __name__, url_prefix="/workout")

FREE_WEIGHT = ["Kettlebells", "Dumbbells", "FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"]

@workout_bp.route("/generate_workout/<int:user_id>", methods=["POST"])
def generate_user_workout(user_id: int):
    try:
        data = request.get_json() or {}
        user_device_timezone = data.get("timezone") or "UTC"
        was_venue_changed = bool(data.get("wasVenueChanged") or False)
        user_wants_new_workout = bool(data.get("user_wants_new_workout") or False)

        # ---- User-local "today" ----
        try:
            user_tz = ZoneInfo(user_device_timezone)
        except Exception:
            user_tz = ZoneInfo("UTC")
        now_utc = datetime.now(timezone.utc)
        local_today = now_utc.astimezone(user_tz).date()

        # ---- Most recent generated workout ----
        latest = db.execute(
            """
            SELECT 
                w.workout_id,
                w.date,
                w.split_group,
                sw.suggested_workout_id,
                aw.actual_workout_id,
                COALESCE(aw.duration_actual, 0) AS duration_actual
            FROM workouts w
            JOIN suggested_workouts sw ON sw.workout_id = w.workout_id
            LEFT JOIN actual_workout aw ON aw.workout_id = w.workout_id
            WHERE w.user_id = %s
            ORDER BY w.date DESC, w.workout_id DESC
            LIMIT 1
            """,
            (user_id,),
            fetch=True
        )
        
        # -------------------------------
        # Reuse short-circuits (ONLY when user did NOT request a new workout and no venue change)
        # -------------------------------
        if latest and not was_venue_changed and not user_wants_new_workout:
            (mr_workout_id, mr_date, mr_split, mr_sw_id, mr_aw_id, mr_dur) = latest[0]
            if not workout_has_any_completed_set(db, workout_id=mr_workout_id):
                exercise_list = fetch_exercise_list(db, mr_aw_id)
                return jsonify({
                    "success": True,
                    "user_id": user_id,
                    "workout_id": mr_workout_id,
                    "split_group": mr_split,
                    "suggested_workout_id": mr_sw_id,
                    "actual_workout_id": mr_aw_id,
                    "exercise_list": exercise_list
                }), 200


        if not was_venue_changed and not user_wants_new_workout:
            today_row = db.execute(
                """
                SELECT 
                    w.workout_id,
                    w.split_group,
                    sw.suggested_workout_id,
                    aw.actual_workout_id
                FROM workouts w
                JOIN suggested_workouts sw ON sw.workout_id = w.workout_id
                LEFT JOIN actual_workout aw ON aw.workout_id = w.workout_id
                WHERE w.user_id = %s
                  AND w.date = %s
                ORDER BY w.workout_id DESC
                LIMIT 1
                """,
                (user_id, local_today),
                fetch=True
            )
            if today_row:
                (tw_workout_id, tw_split, tw_sw_id, tw_aw_id) = today_row[0]
                exercise_list = fetch_exercise_list(db, tw_aw_id)
                return jsonify({
                    "success": True,
                    "user_id": user_id,
                    "workout_id": tw_workout_id,
                    "split_group": tw_split,
                    "suggested_workout_id": tw_sw_id,
                    "actual_workout_id": tw_aw_id,
                    "exercise_list": exercise_list
                }), 200

        # -------------------------------
        # Load user/venue context
        # -------------------------------
        rows = db.execute(
            """
            SELECT 
                u.birthday,
                u.level AS user_level,
                v.days_of_week,
                v.workout_frequency,
                v.time_per_workout,
                v.goals,
                v.pain_points,
                v.priority_muscles,
                v.split,
                u.workout_number,
                v.rest_time_between_set
            FROM Users u
            LEFT JOIN Venues v ON v.venue_id = u.current_venue_id
            WHERE u.user_id = %s
            """,
            (user_id,),
            fetch=True
        )

        if not rows or not rows[0]:
            return jsonify({"success": False, "error": "User not found"}), 404

        (birthday, user_level, days_of_week_raw, wf_raw, tpw_raw,
         goals_raw, pains_raw, pri_musc_raw, split_raw,
         workout_number, rest_time_between_set) = rows[0]

        age = compute_age(birthday)
        time_per_workout = int(tpw_raw or 120)
        level = str(user_level if user_level is not None else "1")
        workout_number = int(workout_number or 0)

        user_goals = list(goals_raw or [])
        pains_raw = [p.split(" ")[0] for p in (pains_raw or [])]
        pain_points = list(pains_raw or [])
        priority_muscles = list(pri_musc_raw or [])

        pref_rows = db.execute(
            """
            SELECT e.name, ep.preference
            FROM exercise_preferences ep
            JOIN Exercises e ON e.exercise_id = ep.exercise_id
            WHERE ep.user_id = %s
            """,
            (user_id,),
            fetch=True
        ) or []
        user_favorites, suggest_less, dont_show_again = set(), set(), set()
        for (exercise_name, pref_val) in pref_rows:
            if pref_val == 3: user_favorites.add(exercise_name)
            elif pref_val == 2: suggest_less.add(exercise_name)
            elif pref_val == 1: dont_show_again.add(exercise_name)

        # Venue + equipment
        venue_rows = db.execute(
            "SELECT u.current_venue_id FROM Users u WHERE u.user_id = %s",
            (user_id,), fetch=True
        )
        if not venue_rows:
            return jsonify({"success": False, "error": "No venue found"}), 404
        venue_id = venue_rows[0][0]

        equip_rows = db.execute(
            """
            SELECT e.equipment_id, e.name, ve.quantity, e.weight_resistance_time
            FROM Venue_equipment ve
            JOIN equipment e ON e.equipment_id = ve.equipment_id
            WHERE ve.venue_id = %s AND COALESCE(ve.quantity, 0) > 0
            ORDER BY e.name
            """,
            (venue_id,), fetch=True
        )

        equipment = []
        for (equipment_id, name, quantity, weight_resistance_time) in (equip_rows or []):
            equipment.append({
                "equipment_id": equipment_id,
                "name": name,
                "quantity": quantity,
                "weight_resistance_time": weight_resistance_time,
            })

        none_free_weight_equipment = [
            eq['name'] for eq in equipment
            if eq['name'] not in FREE_WEIGHT
        ]
        free_weight_equipment = [
            eq for eq in equipment
            if eq['name'] in FREE_WEIGHT
        ]

        available_weights = build_available_weights(free_weight_equipment) or {}
        for eq_name, weights in available_weights.items():
            for w, count in weights.items():
                # Only add labels for Dumbbells / Kettlebells, matching your earlier logic
                if eq_name in ("Dumbbells", "Kettlebells", "Regular loop band", "Handle band"):
                    name_lower = eq_name.lower()
                    if "dumbbell" in name_lower:
                        eq_label = "Dumbbell"
                    elif "kettlebell" in name_lower:
                        eq_label = "Kettlebell"
                    elif "loop band" in name_lower:
                        eq_label = "Loop Band"
                    elif "handle band" in name_lower:
                        eq_label = "Handle Band"
                    else:
                        continue  # skip unknown types
                    
                    # label = f"{1 if count == 1 else 2} {'Dumbbell' if eq_name == 'Dumbbells' else 'Kettlebell'}"
                    label = f"{1 if count == 1 else 2} {eq_label}"
                    if label not in none_free_weight_equipment:
                        none_free_weight_equipment.append(label)

        # Ensure "None" exists for bodyweight exercises ---
        if "None" not in none_free_weight_equipment:
            none_free_weight_equipment.append("None")

        # History → user_records
        user_records = {str(user_id): {"by_exercise": {}}}
        hist_rows = db.execute(
            """
            SELECT e.name, aer.intensity, aer.reps, aer.sets, e.movement, e.level, e.main_muscles, e.secondary_muscles
            FROM actual_exercise_records aer
            JOIN actual_workout aw ON aw.actual_workout_id = aer.actual_workout_id
            JOIN workouts w ON w.workout_id = aw.workout_id
            JOIN Exercises e ON e.exercise_id = aer.exercise_id
            WHERE w.user_id = %s
            ORDER BY aw.actual_workout_id DESC, aer.order_index ASC
            LIMIT 200
            """,
            (user_id,), fetch=True
        ) or []

        for (ex_name, intensity_arr, reps_arr, sets_arr, movement, level_str, main_muscles, secondary_muscles) in hist_rows:
            exercise_type = "Gym Equipment"
            if isinstance(intensity_arr, list) and intensity_arr and isinstance(intensity_arr[-1], (int, float)):
                exercise_intensity = float(intensity_arr[-1])
            elif exercise_type == "Resistance Band":
                exercise_intensity = intensity_arr[-1]
            else:
                exercise_intensity = None
            entry = {
                "phase": "Unknown",
                "weight": exercise_intensity,
                "reps": reps_arr,
                "time": intensity_arr[-1] if exercise_type == 'Timed Exercise' else None
            }
            user_records[str(user_id)]["by_exercise"].setdefault(ex_name, []).append(entry)

        # -------------------------------
        # Decide split + replacing/adding
        # -------------------------------
        latest_incomplete = bool(
            latest and not workout_has_any_completed_set(db, workout_id=latest[0][0])
        )

        # Venue-change replacement keeps SAME split (use workout_number-1)
        replacing_due_to_venue = bool(was_venue_changed and latest_incomplete)
        same_split_workout_count = max(0, workout_number - 1)

        # User-request replacement ADVANCES split (use workout_number)
        replacing_due_to_user = bool(user_wants_new_workout and latest_incomplete)

        if replacing_due_to_venue:
            effective_workout_count = same_split_workout_count
            split_group = get_today_workout(split_raw, effective_workout_count)  # same split
        elif user_wants_new_workout:
            effective_workout_count = workout_number
            split_group = get_today_workout(split_raw, effective_workout_count)  # NEXT split
        else:
            # normal path (generate with current split implied by workout_number or reuse already handled)
            effective_workout_count = workout_number
            split_group = get_today_workout(split_raw, effective_workout_count)

        # -------------------------------
        # Generate workout
        # -------------------------------
        exercises, estimated_session_time = workout_generator(
            user_id=user_id,
            age=age,
            user_split=split_raw,
            user_workout_count=effective_workout_count,
            rest_time=rest_time_between_set,
            user_records=user_records,
            time_per_workout=time_per_workout,
            level=level,
            user_goals=user_goals,
            pain_points=pain_points,
            priority_muscles=priority_muscles,
            equipment=none_free_weight_equipment,
            user_available_weights=build_available_weights(free_weight_equipment),
            user_favorites=user_favorites,
            suggest_less=suggest_less,
            dont_show_again=dont_show_again,
        )
        generated_exercises = build_exercise_payloads(db, exercises)
        total_estimated_time = estimated_session_time + rest_time_between_set * 4 * len(generated_exercises)

        # -------------------------------
        # Replacement paths
        # -------------------------------
        if replacing_due_to_venue or replacing_due_to_user:
            # mr_* from latest
            (_, _, _, mr_sw_id, mr_aw_id, _) = latest[0]

            # For safety: rebuild per-ex arrays like your existing code
            def _coerce_list(x, default, pad_to=4, cast=int):
                arr = list(x or default)
                if cast:
                    try: arr = [cast(v) for v in arr]
                    except Exception: pass
                if len(arr) == 1:
                    arr = arr * pad_to
                return arr

            per_ex = []
            for idx, ge in enumerate(generated_exercises):
                sets = _coerce_list(ge.get("sets"), [0], cast=int)
                reps = _coerce_list(ge.get("reps"), [10], cast=int)
                time_list = _coerce_list(ge.get("time"), [0], cast=int)
                intensity = ge.get("intensity")
                intensity_arr = [intensity if intensity is not None else None] * 4
                per_ex.append({
                    "exercise_id": ge.get("exercise_id"),
                    "sets": sets,
                    "reps": reps,
                    "time": time_list,
                    "intensity": intensity_arr,
                    "exercise_type": ge.get("exercise_type"),
                    "order_index": idx,
                })

            try:
                db.execute("BEGIN")
                # update the container rows (date & split)
                db.execute(
                    """
                    UPDATE workouts 
                    SET date = %s, split_group = %s
                    WHERE workout_id = (SELECT workout_id FROM actual_workout WHERE actual_workout_id = %s)
                    """,
                    (local_today, split_group, int(mr_aw_id))
                )
                db.execute(
                    "UPDATE suggested_workouts SET duration_predicted = %s WHERE suggested_workout_id = %s",
                    (int(total_estimated_time), int(mr_sw_id))
                )
                db.execute("DELETE FROM suggested_exercise_records WHERE suggested_workout_id = %s", (int(mr_sw_id),))
                db.execute("DELETE FROM actual_exercise_records    WHERE actual_workout_id   = %s", (int(mr_aw_id),))

                for rec in per_ex:
                    db.execute(
                        """
                        INSERT INTO suggested_exercise_records
                            (suggested_workout_id, exercise_id, exercise_type, intensity, reps, sets, time, order_index)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            int(mr_sw_id),
                            rec["exercise_id"],
                            rec["exercise_type"],
                            rec["intensity"],
                            rec["reps"],
                            rec["sets"],
                            rec["time"],
                            rec["order_index"],
                        )
                    )
                    db.execute(
                        """
                        INSERT INTO actual_exercise_records
                            (actual_workout_id, exercise_id, exercise_type, intensity, reps, sets, time, order_index)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            int(mr_aw_id),
                            rec["exercise_id"],
                            rec["exercise_type"],
                            rec["intensity"],
                            rec["reps"],
                            rec["sets"],
                            rec["time"],
                            rec["order_index"],
                        )
                    )

                # IMPORTANT: advance workout_number ONLY when the user explicitly requested a new workout;
                # venue-change replacement keeps the same split and does NOT advance.
                if user_wants_new_workout and not was_venue_changed:
                    db.execute(
                        """
                        UPDATE Users
                        SET workout_number = COALESCE(workout_number, 0) + 1
                        WHERE user_id = %s
                        """,
                        (user_id,)
                    )

                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

            exercise_list = fetch_exercise_list(db, int(mr_aw_id))
            # Re-read workout_id for completeness
            (re_wid,) = db.execute(
                "SELECT workout_id FROM actual_workout WHERE actual_workout_id = %s",
                (int(mr_aw_id),), fetch=True
            )[0]
            return jsonify({
                "success": True,
                "user_id": user_id,
                "split_group": split_group,
                "workout_id": int(re_wid),
                "suggested_workout_id": int(mr_sw_id),
                "actual_workout_id": int(mr_aw_id),
                "exercise_list": exercise_list
            }), 200

        # -------------------------------
        # Default ADD NEW (includes user_wants_new_workout when latest is complete or missing)
        # -------------------------------
        created_ids = persist_generated_workout(
            db=db,
            user_id=user_id,
            user_timezone=user_device_timezone,
            generated_exercises=generated_exercises,
            split_group=split_group,
            estimated_time=total_estimated_time,
        )
        exercise_list = fetch_exercise_list(db, int(created_ids["actual_workout_id"]))

        # Advance workout_number for newly added workout
        db.execute(
            """
            UPDATE Users
            SET workout_number = COALESCE(workout_number, 0) + 1
            WHERE user_id = %s
            """,
            (user_id,),
        )

        return jsonify({
            "success": True,
            "user_id": user_id,
            "split_group": created_ids["split_group"],
            "workout_id": created_ids["workout_id"],
            "suggested_workout_id": created_ids["suggested_workout_id"],
            "actual_workout_id": created_ids["actual_workout_id"],
            "exercise_list": exercise_list
        }), 200

    except Exception as e:
        print('printing the error', e)
        return jsonify({
            "success": False,
            "error": str(e),
            "details": "Failed to build workout context",
        }), 500
    

@workout_bp.route("/actual/add_exercise/<int:user_id>/<int:actual_workout_id>", methods=["POST"])
def add_exercise_to_actual_workout(user_id: int, actual_workout_id: int):
    """
    Add an exercise (by name) into the given actual_workout_id.

    POST body:
    {
        "exercise_name": "Dumbbell Bench Press"
    }
    """
    try:
        data = request.get_json() or {}
        exercise_name = (data.get("exercise_name") or "").strip()
        if not exercise_name:
            return jsonify({"success": False, "error": "exercise_name is required"}), 400
        
        has_all, missing, missing_ids = check_user_equipment_for_exercise(db, user_id, exercise_name=exercise_name)
        if not has_all:
            return jsonify({
                "success": False,
                "error": "Missing required equipment for this exercise.",
                "missing": missing,
                "missing_ids": missing_ids
            })

        # print(data, user_id, actual_workout_id)

        # 0) Validate that this actual_workout belongs to the user, and fetch workout_id
        wrow = db.execute(
            """
            SELECT aw.actual_workout_id, w.workout_id
            FROM actual_workout aw
            JOIN workouts w ON w.workout_id = aw.workout_id
            WHERE aw.actual_workout_id = %s AND w.user_id = %s
            """,
            (actual_workout_id, user_id),
            fetch=True
        )
        if not wrow:
            # print(wrow, {"success": False, "error": "actual_workout_id not found for user"})
            return jsonify({"success": False, "error": "actual_workout_id not found for user"}), 404
        workout_id = wrow[0][1]

        # 1) Pull user/venue/equipment context (same as your determine_weight route)
        rows = db.execute(
            """
            SELECT 
                u.birthday, u.level AS user_level, v.days_of_week, v.workout_frequency,
                v.time_per_workout, v.goals, v.pain_points, v.priority_muscles, v.split,
                u.workout_number, v.rest_time_between_set
            FROM Users u
            LEFT JOIN Venues v ON v.venue_id = u.current_venue_id
            WHERE u.user_id = %s
            """,
            (user_id,),
            fetch=True
        )
        if not rows:
            return jsonify({"success": False, "error": "User not found"}), 404
        (birthday, user_level, days_of_week_raw, wf_raw, tpw_raw,
         goals_raw, pains_raw, pri_musc_raw, split_raw, workout_number,
         rest_time_between_set) = rows[0]

        age = compute_age(birthday)
        days_of_week_raw = [
            DAY_MAP[day.lower()]
            for day in (days_of_week_raw or [])
            if isinstance(day, str) and day.lower() in DAY_MAP
        ]
        # days_of_week = [int(d) for d in (days_of_week_raw or [1,2,3,4,5,6,7])]
        # workout_frequency = int(wf_raw or 1)
        # time_per_workout = int(tpw_raw or 120)
        level = str(user_level if user_level is not None else "1")
        workout_number = int(workout_number or 0)
        user_goals = list(goals_raw or [])
        pains_raw = [p.split(" ")[0] for p in (pains_raw or [])]
        pain_points = list(pains_raw or [])
        # priority_muscles = list(pri_musc_raw or [])

        # Venue + equipment
        venue_id_row = db.execute("SELECT u.current_venue_id FROM Users u WHERE u.user_id = %s", (user_id,), fetch=True)
        if not venue_id_row:
            return jsonify({"success": False, "error": "User not found"}), 404
        (venue_id,) = venue_id_row[0]
        if venue_id is None:
            return jsonify({"success": False, "error": "User has no current venue set"}), 404

        equip_rows = db.execute(
            """
            SELECT e.equipment_id, e.name, ve.quantity, e.weight_resistance_time
            FROM Venue_equipment ve
            JOIN equipment e ON e.equipment_id = ve.equipment_id
            WHERE ve.venue_id = %s AND COALESCE(ve.quantity, 0) > 0
            ORDER BY e.name
            """,
            (venue_id,),
            fetch=True
        )
        equipment = [{"equipment_id": r[0], "name": r[1], "quantity": r[2], "weight_resistance_time": r[3]} for r in (equip_rows or [])]
        none_free_weight_equipment = [eq['name'] for eq in equipment if eq['name'] not in ["Kettlebells","Dumbbells","FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"]]
        free_weight_equipment = [eq for eq in equipment if eq['name'] in ["Kettlebells","Dumbbells","FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"]]
        available_weights = build_available_weights(free_weight_equipment)
        for eq_name in available_weights:
            for w, c in available_weights[eq_name].items():
                label = f"{1 if c==1 else 2} {'Dumbbell' if eq_name=='Dumbbells' else 'Kettlebell'}"
                if label not in none_free_weight_equipment:
                    none_free_weight_equipment.append(label)
        # if "2 Dumbbell" not in none_free_weight_equipment:
        # none_free_weight_equipment.append("2 Dumbbell")
        
        # Database does not contain None as equipment.Therefore adding it for
        # bodyweight exercises
        if "None" not in none_free_weight_equipment: none_free_weight_equipment.append("None")
        # print(free_weight_equipment)
        # Prior user records (for determine_user_exercise_weight)
        rec_rows = db.execute(
            """
            SELECT e.name, w.phase, w.date, aer.intensity, aer.reps, aer.time, aer.exercise_type
            FROM actual_exercise_records aer
            JOIN actual_workout aw ON aw.actual_workout_id = aer.actual_workout_id
            JOIN workouts w        ON w.workout_id = aw.workout_id
            JOIN Exercises e       ON e.exercise_id = aer.exercise_id
            WHERE w.user_id = %s
            ORDER BY w.date ASC, aw.actual_workout_id ASC, aer.order_index ASC
            """,
            (user_id,),
            fetch=True
        )
        user_records = {str(user_id): {"by_exercise": {}}}
        for (ex_name, phase, w_date, intensity_arr, reps_arr, set_time, exercise_type) in (rec_rows or []):
            if exercise_type == 'Gym Equipment':
                exercise_intensity = float(intensity_arr[-1])
            elif exercise_type == "Resistance Band":
                exercise_intensity = intensity_arr[-1]
            else:
                exercise_intensity = None

            user_records[str(user_id)]["by_exercise"].setdefault(ex_name, []).append({
                "phase": phase,
                "weight": exercise_intensity,
                "reps": reps_arr,
                "time": intensity_arr[-1] if exercise_type == 'Timed Exercise' else None #[int(secs) for secs in (set_time or []) if secs is not None],
            })

        # Suggested intensity
        result = determine_user_exercise_weight(
            exercise_name=exercise_name, user_id=user_id, age=age,
            user_workout_count=workout_number, user_split=split_raw,
            user_records=user_records, level=level, user_goals=user_goals,
            pain_points=pain_points, equipment=none_free_weight_equipment,
            user_available_weights=available_weights
        )

        # print(result)

        si = result.get("suggested_intensity") or {}

        if si.get("exercise_type") == 'Gym Equipment' or si.get("exercise_type") == 'Resistance Band':
            exercise_intensity = str(si.get("weight"))
        elif si.get("exercise_type") == 'Bodyweight':
            exercise_intensity = "Bodyweight"
        elif si.get("exercise_type") == 'Timed Exercise':
            exercise_intensity = si.get("time")
        else:
            exercise_intensity = None

        intensity = [exercise_intensity] * 4    # exercise_intensity          # [si.get("weight")] * 4 if si.get("weight") is not None else [0] * 4
        reps   = [si.get("reps")] * 4           # si.get("reps")
        sets   = [0] * 4
        time   = [0] * 4
        # print((sets), (reps), (intensity), (time))
        # target_len = 4

        # def _pad(a,f): 
        #     a=list(a or [])
        #     print("a -> ", a, f)
        #     a += [f]*(target_len-len(a))
        #     return a[:target_len]
        
        # sets, reps, intensity, time = sets, reps * 4,  
        
        # _pad(sets,0), _pad(reps,10), [x for x in _pad(intensity,0.0)], [int(x) for x in _pad(time,0)]

        # Resolve exercise_id
        ex_rows = db.execute("SELECT exercise_id FROM Exercises WHERE name = %s LIMIT 1", (exercise_name,), fetch=True)
        if not ex_rows:
            return jsonify({"success": False, "error": f"Exercise not found: {exercise_name}"}), 404
        
        exercise_id = ex_rows[0][0]
        # Next order_index within this actual_workout
        (max_idx,) = db.execute(
            "SELECT COALESCE(MAX(order_index), -1) FROM actual_exercise_records WHERE actual_workout_id = %s",
            (actual_workout_id,),
            fetch=True
        )[0]
        order_index = int(max_idx) + 1

        # Insert
        inserted = db.execute(
            """
            INSERT INTO actual_exercise_records (actual_workout_id,
            exercise_id, exercise_type, intensity, reps, sets, time, order_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING actual_record_id
            """,
            (actual_workout_id, exercise_id, si.get("exercise_type"), intensity, reps, sets, time, order_index),
            fetch=True
        )
        actual_record_id = inserted[0][0]

        return jsonify({
            "success": True,
            "user_id": user_id,
            "workout_id": workout_id,
            "actual_workout_id": actual_workout_id,
            "actual_record_id": actual_record_id,
            "exercise_type": si.get("exercise_type"),
            "exercise_id": exercise_id,
            "exercise_name": exercise_name,
            "intensity": { "intensity": intensity, "reps": reps, "sets": sets, "time": time, "order_index": order_index }
        }), 200

    except Exception as e:
        print(e)
        return jsonify({"success": False, "error": str(e), "details": "Failed to add exercise"}), 500


# POST /workout/actual/replace_exercise/<user_id>/<actual_workout_id>/<old_exercise_id>
@workout_bp.route("/actual/replace_exercise/<int:user_id>/<int:actual_workout_id>/<int:old_exercise_id>", methods=["POST"])
def replace_actual_exercise_by_workout_and_exercise(user_id: int, actual_workout_id: int, old_exercise_id: int):
    """
    Replace one (default) or all occurrences of old_exercise_id in an actual_workout
    with a new exercise. Uses determine_user_exercise_weight to set sets/reps/intensity/time.

    Body:
      {
        "exercise_name": "Seated Cable Row"   // or "exercise_id": 123
        "scope": "first" | "all"              // optional, default "first"
      }
    """
    try:
        data = request.get_json(force=True) or {}
        exercise_name = (data.get("exercise_name") or "").strip()
        new_exercise_id = data.get("exercise_id")

        has_all, missing, missing_ids = check_user_equipment_for_exercise(db, user_id, exercise_id=new_exercise_id)
        if not has_all:
            return jsonify({
                "success": False,
                "error": "Missing required equipment for this exercise.",
                "missing": missing,
                "missing_ids": missing_ids
            })

        scope = (data.get("scope") or "first").lower()

        # 0) Validate workout belongs to user; also get parent workout_id
        wrow = db.execute(
            """
            SELECT aw.actual_workout_id, w.workout_id
            FROM actual_workout aw
            JOIN workouts w ON w.workout_id = aw.workout_id
            WHERE aw.actual_workout_id = %s AND w.user_id = %s
            """,
            (actual_workout_id, user_id),
            fetch=True
        )
        if not wrow:
            return jsonify({"success": False, "error": "actual_workout_id not found for user"}), 404
        workout_id = wrow[0][1]

        # 1) Find candidate rows to replace (ordered for deterministic 'first')
        rows = db.execute(
            """
            SELECT actual_record_id, order_index
            FROM actual_exercise_records
            WHERE actual_workout_id = %s AND exercise_id = %s
            ORDER BY order_index ASC, actual_record_id ASC
            """,
            (actual_workout_id, old_exercise_id),
            fetch=True
        )
        if not rows:
            return jsonify({"success": False, "error": "Old exercise not found in this workout"}), 404

        target_rows = rows if scope == "all" else [rows[0]]

        # 2) Resolve new_exercise_id (by id or by name)
        if new_exercise_id is None:
            if not exercise_name:
                return jsonify({"success": False, "error": "Provide exercise_name or exercise_id"}), 400
            er = db.execute("SELECT exercise_id FROM Exercises WHERE name = %s LIMIT 1", (exercise_name,), fetch=True)
            if not er:
                return jsonify({"success": False, "error": f"Exercise not found: {exercise_name}"}), 404
            new_exercise_id = er[0][0]
        else:
            nr = db.execute("SELECT name FROM Exercises WHERE exercise_id = %s", (new_exercise_id,), fetch=True)
            if not nr:
                return jsonify({"success": False, "error": f"Exercise not found: id={new_exercise_id}"}), 404
            exercise_name = nr[0][0]

        # 3) Build the same context (user/venue/equipment/records) used elsewhere
        #    — this mirrors your existing routes so suggestions stay consistent. :contentReference[oaicite:0]{index=0}
        rows_user = db.execute(
            """
            SELECT 
                u.birthday, u.level AS user_level, v.days_of_week, v.workout_frequency,
                v.time_per_workout, v.goals, v.pain_points, v.priority_muscles, v.split,
                u.workout_number, v.rest_time_between_set
            FROM Users u
            LEFT JOIN Venues v ON v.venue_id = u.current_venue_id
            WHERE u.user_id = %s
            """,
            (user_id,),
            fetch=True
        )
        if not rows_user:
            return jsonify({"success": False, "error": "User not found"}), 404

        (birthday, user_level, days_of_week_raw, wf_raw, tpw_raw,
         goals_raw, pains_raw, pri_musc_raw, split_raw, workout_number,
         rest_time_between_set) = rows_user[0]

        age = compute_age(birthday)
        level = str(user_level if user_level is not None else "1")
        user_goals = list(goals_raw or [])
        pains_raw = [p.split(" ")[0] for p in (pains_raw or [])]
        pain_points = list(pains_raw or [])

        vrow = db.execute("SELECT u.current_venue_id FROM Users u WHERE u.user_id = %s", (user_id,), fetch=True)
        if not vrow:
            return jsonify({"success": False, "error": "User not found"}), 404
        (venue_id,) = vrow[0]
        if venue_id is None:
            return jsonify({"success": False, "error": "User has no current venue set"}), 404

        equip_rows = db.execute(
            """
            SELECT e.equipment_id, e.name, ve.quantity, e.weight_resistance_time
            FROM Venue_equipment ve
            JOIN equipment e ON e.equipment_id = ve.equipment_id
            WHERE ve.venue_id = %s AND COALESCE(ve.quantity, 0) > 0
            ORDER BY e.name
            """,
            (venue_id,),
            fetch=True
        )
        # print(equip_rows)
        equipment = [{"equipment_id": r[0], "name": r[1], "quantity": r[2], "weight_resistance_time": r[3]} for r in (equip_rows or [])]
        none_free_weight_equipment = [eq['name'] for eq in equipment if eq['name'] not in ["Kettlebells","Dumbbells","FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"]]
        free_weight_equipment = [eq for eq in equipment if eq['name'] in ["Kettlebells","Dumbbells", "FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"]]

        # for w in free_weight_equipment:
        #     print(f"ye: {w}")

        available_weights = build_available_weights(free_weight_equipment)
        for eq_name in available_weights:
            for _, c in available_weights[eq_name].items():
                label = f"{1 if c==1 else 2} {'Dumbbell' if eq_name=='Dumbbells' else 'Kettlebell'}"
                if label not in none_free_weight_equipment:
                    none_free_weight_equipment.append(label)
        # if "2 Dumbbell" not in none_free_weight_equipment: none_free_weight_equipment.append("2 Dumbbell")
        if "None" not in none_free_weight_equipment: none_free_weight_equipment.append("None")

        rec_rows = db.execute(
            """
            SELECT e.name, w.phase, w.date, aer.intensity, aer.reps, aer.time, aer.exercise_type
            FROM actual_exercise_records aer
            JOIN actual_workout aw ON aw.actual_workout_id = aer.actual_workout_id
            JOIN workouts w        ON w.workout_id = aw.workout_id
            JOIN Exercises e       ON e.exercise_id = aer.exercise_id
            WHERE w.user_id = %s
            ORDER BY w.date ASC, aw.actual_workout_id ASC, aer.order_index ASC
            """,
            (user_id,),
            fetch=True
        )
        user_records = {str(user_id): {"by_exercise": {}}}
        for (ex_name, phase, w_date, intensity_arr, reps_arr, set_time, exercise_type) in (rec_rows or []):
            if exercise_type == 'Gyme Equipment':
                exercise_intensity = float(intensity_arr[-1])
            elif exercise_type == "Resistance Band":
                exercise_intensity = intensity_arr[-1]
            else:
                exercise_intensity = None
        
            user_records[str(user_id)]["by_exercise"].setdefault(ex_name, []).append({
                "phase": phase,
                "weight": exercise_intensity,
                "reps": reps_arr,
                "time": intensity_arr[-1] if exercise_type == 'Timed Exercise' else None
            })

        # 4) Determine suggested intensity ONCE (apply to all targets)
        result = determine_user_exercise_weight(
            exercise_name=exercise_name,
            user_id=user_id,
            age=age,
            user_workout_count=workout_number,
            user_split=split_raw,
            user_records=user_records,
            level=level,
            user_goals=user_goals,
            pain_points=pain_points,
            equipment=none_free_weight_equipment,
            user_available_weights=available_weights
        )
        # print("results: ", result)
        si = result.get("suggested_intensity") or {}
        
        if si.get("exercise_type") == 'Gym Equipment' or si.get("exercise_type") == 'Resistance Band':
            exercise_intensity = str(si.get("weight"))
        elif si.get("exercise_type") == 'Bodyweight':
            exercise_intensity = "Bodyweight"
        elif si.get("exercise_type") == 'Timed Exercise':
            exercise_intensity = si.get("time")
        else:
            exercise_intensity = None

        intensity = [exercise_intensity] * 4 
        reps   = [si.get("reps")] * 4
        sets   = [0] * 4
        time   = [0] * 4

        target_len = max(len(sets), len(reps), len(intensity), len(time), 4)

        def _pad(a, f): 
            a = list(a or [])
            a += [f] * (target_len - len(a))
            return a[:target_len]

        sets   = _pad(sets, 1)
        reps   = _pad(reps, 10)
        intensity = [x for x in _pad(intensity, 0.0)]
        time   = [int(x)   for x in _pad(time, 0)]

        # 5) Update 1 or many rows (preserve order_index)
        updated_ids = []
        for (actual_record_id, _) in target_rows:
            db.execute(
                """
                UPDATE actual_exercise_records
                SET exercise_id = %s, intensity = %s, reps = %s, sets = %s,
                time = %s, exercise_type = %s
                WHERE actual_record_id = %s
                """,
                (new_exercise_id, intensity, reps, sets, time, si.get("exercise_type"), actual_record_id)
            )
            updated_ids.append(int(actual_record_id))

        return jsonify({
            "success": True,
            "user_id": user_id,
            "workout_id": workout_id,
            "actual_workout_id": actual_workout_id,
            "scope": scope,
            "replaced_count": len(updated_ids),
            "old_exercise_id": int(old_exercise_id),
            "new_exercise_id": int(new_exercise_id),
            "exercise_name": exercise_name,
            "updated_record_ids": updated_ids,
            "intensity": { "intensity": intensity, "reps": reps, "sets": sets, "time": time }
        }), 200

    except Exception as e:
        print("replace_actual_exercise_by_workout_and_exercise error:", e)
        return jsonify({"success": False, "error": "Failed to replace exercise", "details": str(e)}), 500


def _as_list(x):
    if x is None: return []
    if isinstance(x, (list, tuple)): return list(x)
    return [x]

def normalize_intensity(si):
    if si.get("exercise_type") == 'Gym Equipment' or si.get("exercise_type") == 'Resistance Band':
        i = _as_list(si.get("weight") or si.get("weights"))
    elif si.get("exercise_type") == 'Timed Exercise':
        i = _as_list(si.get("time"))
    elif si.get("exercise_type") == 'Bodyweight':
        i = _as_list(['Bodyweight'] * 4)
    else:
        i = None

    r = _as_list(si.get("reps"))
    s = _as_list(si.get("sets"))

    target_len = max(len(s), len(r), len(i), 1)
    if target_len == 1 and s == [] and r == [] and i == []:
        target_len = 4

    def _pad(arr, fill):
        arr = list(arr)
        if len(arr) < target_len:
            arr += [fill] * (target_len - len(arr))
        return arr[:target_len]

    s = _pad(s or [1], 1)
    r = _pad(r or [], 10)
    i = _pad([x for x in (i or [])], 0.0)
    return i, r, s


def _build_user_context_for_intensity(user_id):
    # Pull user + venue + equipment + records (mirrors existing routes)
    rows = db.execute(
        """
        SELECT 
            u.birthday, u.level AS user_level, v.days_of_week, v.workout_frequency,
            v.time_per_workout, v.goals, v.pain_points, v.priority_muscles, v.split,
            u.workout_number, v.rest_time_between_set
        FROM Users u
        LEFT JOIN Venues v ON v.venue_id = u.current_venue_id
        WHERE u.user_id = %s
        """,
        (user_id,),
        fetch=True
    )
    if not rows:
        raise ValueError("User not found")
    (birthday, user_level, days_of_week_raw, wf_raw, tpw_raw,
     goals_raw, pains_raw, pri_musc_raw, split_raw, workout_number,
     rest_time_between_set) = rows[0]

    age = compute_age(birthday)
    level = str(user_level if user_level is not None else "1")
    user_goals = list(goals_raw or [])
    pains_raw = [p.split(" ")[0] for p in (pains_raw or [])]
    pain_points = list(pains_raw or [])

    vrow = db.execute("SELECT u.current_venue_id FROM Users u WHERE u.user_id = %s",
                      (user_id,), fetch=True)
    if not vrow:
        raise ValueError("User not found")
    (venue_id,) = vrow[0]
    if venue_id is None:
        raise ValueError("User has no current venue set")

    equip_rows = db.execute(
        """
        SELECT e.equipment_id, e.name, ve.quantity, e.weight_resistance_time
        FROM Venue_equipment ve
        JOIN equipment e ON e.equipment_id = ve.equipment_id
        WHERE ve.venue_id = %s AND COALESCE(ve.quantity, 0) > 0
        ORDER BY e.name
        """,
        (venue_id,),
        fetch=True
    )
    equipment = [{"equipment_id": r[0], "name": r[1], "quantity": r[2], "weight_resistance_time": r[3]} for r in (equip_rows or [])]
    none_free_weight_equipment = [eq['name'] for eq in equipment if eq['name'] not in ["Kettlebells","Dumbbells","FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"]]
    free_weight_equipment = [eq for eq in equipment if eq['name'] in ["Kettlebells","Dumbbells","FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"]]
    available_weights = build_available_weights(free_weight_equipment)
    for eq_name in available_weights:
        for _, c in available_weights[eq_name].items():
            label = f"{1 if c==1 else 2} {'Dumbbell' if eq_name=='Dumbbells' else 'Kettlebell'}"
            if label not in none_free_weight_equipment:
                none_free_weight_equipment.append(label)
    if "2 Dumbbell" not in none_free_weight_equipment: none_free_weight_equipment.append("2 Dumbbell")
    if "None" not in none_free_weight_equipment: none_free_weight_equipment.append("None")

    rec_rows = db.execute(
        """
        SELECT e.name, w.phase, w.date, aer.intensity, aer.reps, aer.time, exercise_type
        FROM actual_exercise_records aer
        JOIN actual_workout aw ON aw.actual_workout_id = aer.actual_workout_id
        JOIN workouts w        ON w.workout_id = aw.workout_id
        JOIN Exercises e       ON e.exercise_id = aer.exercise_id
        WHERE w.user_id = %s
        ORDER BY w.date ASC, aw.actual_workout_id ASC, aer.order_index ASC
        """,
        (user_id,),
        fetch=True
    )
    user_records = {str(user_id): {"by_exercise": {}}}
    for (ex_name, phase, w_date, intensity_arr, reps_arr, set_time, exercise_type) in (rec_rows or []):
        if exercise_type == 'Gyme Equipment':
            exercise_intensity = float(intensity_arr[-1])
        elif exercise_type == "Resistance Band":
            exercise_intensity = intensity_arr[-1]
        else:
            exercise_intensity = None
    
        user_records[str(user_id)]["by_exercise"].setdefault(ex_name, []).append({
            "phase": phase,
            "weight": exercise_intensity,
            "reps": reps_arr,
            "time": intensity_arr[-1] if exercise_type == 'Timed Exercise' else None
        })

    return {
        "age": age,
        "level": level,
        "split": split_raw,
        "workout_number": int(workout_number or 0),
        "user_goals": user_goals,
        "pain_points": pain_points,
        "equipment_names": none_free_weight_equipment,
        "available_weights": available_weights,
        "records": user_records
    }


def _pick_candidates_for_mode(old_exercise_id, mode):
    # get progression/regression names from the old exercise
    row = db.execute(
        "SELECT name, progression, regression FROM Exercises WHERE exercise_id = %s",
        (old_exercise_id,), fetch=True
    )
    if not row:
        raise ValueError("Old exercise not found")
    old_name, progression, regression = row[0]
    names = (progression if mode == "challenge" else regression) or []
    if not names:
        return old_name, []
    # print(old_name, names)
    # resolve names to (id, name, difficulty)
    candidates = []
    for nm in names:
        r = db.execute("SELECT exercise_id, name, difficulty FROM Exercises WHERE LOWER(name) = %s LIMIT 1",
                       (nm.lower(),), fetch=True)
        # print("r: ", r)
        if r:
            candidates.append({"exercise_id": r[0][0], "name": r[0][1], "difficulty": r[0][2]})
        # print(candidates)
    return old_name, candidates


def _pick_first_equipped_candidate(db, user_id: int, candidates: list[dict]):
    """
    candidates: [{"exercise_id": int, "name": str, "difficulty": int}, ...]

    Returns:
        selected: dict | None
        audit: list[{"exercise_id": int, "name": str, "missing": [str]}]
    """
    audit = []
    for c in candidates:
        has_all, missing, missing_ids = check_user_equipment_for_exercise(db, user_id, exercise_id=c["exercise_id"])
        if not has_all:
            return c, audit  # we return early on first match

        # has_all, missing = check_user_equipment_for_exercise(db, user_id, exercise_id=c["exercise_id"])
        # if has_all:
        #     return c, audit  # we return early on first match
        audit.append({"exercise_id": c["exercise_id"], "name": c["name"], "missing": missing, "missing_ids": missing_ids})
    return None, audit


@workout_bp.route("/actual/adjust_and_replace/<int:user_id>/<int:actual_workout_id>/<int:old_exercise_id>/<string:mode>", methods=["POST"])
def adjust_and_replace(user_id: int, actual_workout_id: int, old_exercise_id: int, mode: str):
    try:
        if mode not in ("challenge", "easy"):
            return jsonify({"success": False, "error": "mode must be 'challenge' or 'easy'"}), 400

        # validate workout belongs to user
        wrow = db.execute(
            """
            SELECT w.workout_id
            FROM actual_workout aw
            JOIN workouts w ON w.workout_id = aw.workout_id
            WHERE aw.actual_workout_id = %s AND w.user_id = %s
            """,
            (actual_workout_id, user_id), fetch=True
        )
        if not wrow:
            return jsonify({"success": False, "error": "actual_workout_id not found for user"}), 404
        workout_id = wrow[0][0]

        # locate the single row to replace
        row = db.execute(
            """
            SELECT actual_record_id, order_index
            FROM actual_exercise_records
            WHERE actual_workout_id = %s AND exercise_id = %s
            LIMIT 1
            """,
            (actual_workout_id, old_exercise_id), fetch=True
        )
        if not row:
            return jsonify({"success": False, "error": "old_exercise_id not in workout"}), 404
        actual_record_id, order_index = row[0]

        # choose the progression/regression target
        _, candidates = _pick_candidates_for_mode(old_exercise_id, mode)
        if not candidates:
            return jsonify({"success": True, "message": "No alternative found", "replaced_count": 0}), 200
        
        selected, audit = _pick_first_equipped_candidate(db, user_id, candidates)
        if not selected:
            return jsonify({
                "success": True,
                "message": "No suitable alternative with your equipment settings.",
                "replaced_count": 0,
                "candidates_missing": audit
            }), 200

        # use the selected candidate (not candidates[0])
        new_ex_id, new_ex_name = selected["exercise_id"], selected["name"]

        # compute intensity for the new exercise
        ctx = _build_user_context_for_intensity(user_id)
        result = determine_user_exercise_weight(
            exercise_name=new_ex_name,
            user_id=user_id,
            age=ctx["age"],
            user_workout_count=ctx["workout_number"],
            user_split=ctx["split"],
            user_records=ctx["records"],
            level=ctx["level"],
            user_goals=ctx["user_goals"],
            pain_points=ctx["pain_points"],
            equipment=ctx["equipment_names"],
            user_available_weights=ctx["available_weights"],
        )
        si = result.get("suggested_intensity") or {}
        intensity, reps, sets = normalize_intensity(si)

        sets = [0] * 4
        time = [0] * 4

        # update that one row in place
        db.execute(
            """
            UPDATE actual_exercise_records
            SET exercise_id = %s, intensity = %s, reps = %s, sets = %s, time =
            %s, exercise_type = %s
            WHERE actual_record_id = %s
            """,
            (new_ex_id, intensity, reps, sets, time, si.get("exercise_type"), actual_record_id)
        )

        return jsonify({
            "success": True,
            "user_id": user_id,
            "workout_id": workout_id,
            "actual_workout_id": actual_workout_id,
            "actual_record_id": int(actual_record_id),
            "order_index": int(order_index),
            "old_exercise_id": int(old_exercise_id),
            "new_exercise_id": int(new_ex_id),
            "exercise_name": new_ex_name,
            "intensity": {"intensity": intensity, "reps": reps, "sets": sets, "time": time},
            "replaced_count": 1
        }), 200
    except Exception as e:
        print("adjust_and_replace error:", e)
        return jsonify({"success": False, "error": "Failed to adjust & replace", "details": str(e)}), 500


@workout_bp.route("/actual/replace_with_variation/<int:user_id>/<int:actual_workout_id>/<int:old_exercise_id>", methods=["POST"])
def replace_with_variation(user_id: int, actual_workout_id: int, old_exercise_id: int):
    try:
        data = request.get_json(force=True) or {}
        variation_id = data.get("variation_id")

        has_all, missing, missing_ids = check_user_equipment_for_exercise(db, user_id, exercise_id=variation_id)
        if not has_all:
            return jsonify({
                "success": False,
                "error": "Missing required equipment for this exercise.",
                "missing": missing,
                "missing_ids": missing_ids
            })

        variation_name = (data.get("variation_name") or "").strip()

        # validate workout belongs to user
        wrow = db.execute(
            """
            SELECT w.workout_id
            FROM actual_workout aw
            JOIN workouts w ON w.workout_id = aw.workout_id
            WHERE aw.actual_workout_id = %s AND w.user_id = %s
            """,
            (actual_workout_id, user_id), fetch=True
        )
        if not wrow:
            return jsonify({"success": False, "error": "actual_workout_id not found for user"}), 404
        workout_id = wrow[0][0]

        # locate the single row to replace
        row = db.execute(
            """
            SELECT actual_record_id, order_index
            FROM actual_exercise_records
            WHERE actual_workout_id = %s AND exercise_id = %s
            LIMIT 1
            """,
            (actual_workout_id, old_exercise_id), fetch=True
        )
        if not row:
            return jsonify({"success": False, "error": "old_exercise_id not in workout"}), 404
        actual_record_id, order_index = row[0]

        # resolve the variation exercise
        if variation_id is not None:
            vr = db.execute("SELECT exercise_id, name FROM Exercises WHERE exercise_id = %s",
                            (variation_id,), fetch=True)
            if not vr:
                return jsonify({"success": False, "error": f"Variation id not found: {variation_id}"}), 404
            new_ex_id, new_ex_name = vr[0]
        elif variation_name:
            vr = db.execute("SELECT exercise_id, name FROM Exercises WHERE name = %s LIMIT 1",
                            (variation_name,), fetch=True)
            if not vr:
                return jsonify({"success": False, "error": f"Variation not found: {variation_name}"}), 404
            new_ex_id, new_ex_name = vr[0]
        else:
            return jsonify({"success": False, "error": "Provide variation_id or variation_name"}), 400

        # compute intensity for the variation
        ctx = _build_user_context_for_intensity(user_id)
        result = determine_user_exercise_weight(
            exercise_name=new_ex_name,
            user_id=user_id,
            age=ctx["age"],
            user_workout_count=ctx["workout_number"],
            user_split=ctx["split"],
            user_records=ctx["records"],
            level=ctx["level"],
            user_goals=ctx["user_goals"],
            pain_points=ctx["pain_points"],
            equipment=ctx["equipment_names"],
            user_available_weights=ctx["available_weights"],
        )
        si = result.get("suggested_intensity") or {}
        intensity, reps, sets = normalize_intensity(si)

        intensity = intensity * 4
        reps = reps * 4
        sets = [0] * 4
        time = [0] * 4

        # update the row
        db.execute(
            """
            UPDATE actual_exercise_records
            SET exercise_id = %s, intensity = %s, reps = %s, sets = %s, time =
            %s, exercise_type = %s
            WHERE actual_record_id = %s
            """,
            (new_ex_id, intensity, reps, sets, time, si.get("exercise_type"), actual_record_id)
        )

        return jsonify({
            "success": True,
            "user_id": user_id,
            "workout_id": workout_id,
            "actual_workout_id": actual_workout_id,
            "actual_record_id": int(actual_record_id),
            "order_index": int(order_index),
            "old_exercise_id": int(old_exercise_id),
            "new_exercise_id": int(new_ex_id),
            "exercise_name": new_ex_name,
            "intensity": {"intensity": intensity, "reps": reps, "sets": sets, "time": time},
            "replaced_count": 1
        }), 200
    except Exception as e:
        print("replace_with_variation error:", e)
        return jsonify({"success": False, "error": "Failed to replace with variation", "details": str(e)}), 500


@workout_bp.route("/update_workout_date/<int:user_id>", methods=["POST"])
def update_workout_date(user_id: int):
    """
    If the user's most recent workout is from yesterday
    and has no 'actual_workout' entry, update its date to today.
    """
    try:
        # Find the most recent workout
        rows = db.execute(
            """
            SELECT w.workout_id, w.date,
                   aw.actual_workout_id
            FROM workouts w
            LEFT JOIN actual_workout aw ON aw.workout_id = w.workout_id
            WHERE w.user_id = %s
            ORDER BY w.date DESC, w.workout_id DESC
            LIMIT 1
            """,
            (user_id,),
            fetch=True
        )

        if not rows:
            return jsonify({"success": False, "message": "No workouts found"}), 404

        workout_id, workout_date, actual_workout_id = rows[0]

        # If already completed, do nothing
        if actual_workout_id is not None:
            return jsonify({"success": False, "message": "Last workout already completed"}), 200

        # If the workout is from yesterday, update its date
        db.execute(
            """
            UPDATE workouts
            SET date = CURRENT_DATE
            WHERE workout_id = %s
              AND date = CURRENT_DATE - INTERVAL '1 day'
            """,
            (workout_id,),
            commit=True
        )

        return jsonify({
            "success": True,
            "message": "Workout date updated to today",
            "workout_id": workout_id
        }), 200

    except Exception as e:
        print("Error in update_incomplete_workout:", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@workout_bp.route("/actual/set_time/<int:workout_id>", methods=["POST"])
def set_actual_workout_time(workout_id: int):
    try:
        data = request.get_json() or {}
        duration_actual = data.get("duration_actual")

        if duration_actual is None:
            return jsonify({"success": False, "error": "Missing duration_actual"}), 400

        # Ensure the workout has a linked actual_workout row
        rows = db.execute(
            """
            SELECT actual_workout_id
            FROM actual_workout
            WHERE workout_id = %s
            """,
            (workout_id,),
            fetch=True
        )

        if not rows:
            return jsonify({"success": False, "error": "Workout not found"}), 404

        (actual_workout_id,) = rows[0]

        # Update time (no commit kwarg; your db wrapper handles it)
        db.execute(
            """
            UPDATE actual_workout
            SET duration_actual = %s
            WHERE actual_workout_id = %s
            """,
            (int(duration_actual), int(actual_workout_id))
        )

        return jsonify({
            "success": True,
            "workout_id": workout_id,
            "actual_workout_id": actual_workout_id,
            "duration_actual": int(duration_actual)
        }), 200

    except Exception as e:
        print(e)
        return jsonify({
            "success": False,
            "error": str(e),
            "details": "Failed to update actual workout time"
        }), 500

    
@workout_bp.route("/fetch_workout/<int:workout_id>/<int:suggested_workout_id>", methods=["GET"])
def fetch_workout_by_ids(workout_id: int, suggested_workout_id: int):
    try:
        # Validate that these IDs belong together (defensive)
        rows = db.execute(
            """
            SELECT 
                w.user_id, 
                w.split_group,
                sw.suggested_workout_id, 
                aw.actual_workout_id
            FROM workouts w
            LEFT JOIN suggested_workouts sw ON sw.workout_id = w.workout_id
            LEFT JOIN actual_workout aw     ON aw.workout_id = w.workout_id
            WHERE w.workout_id = %s
            """,
            (workout_id,),
            fetch=True
        )

        if not rows:
            return jsonify({"success": False, "error": "Workout not found"}), 404

        (user_id, split_group, sw_id, actual_workout_id) = rows[0]
        if sw_id != suggested_workout_id:
            return jsonify({"success": False, "error": "Mismatched suggested_workout_id"}), 400

        exercise_list = fetch_exercise_list(db, suggested_workout_id)
        return jsonify({
            "success": True,
            "user_id": user_id,
            "split_group": split_group,
            "workout_id": workout_id,
            "suggested_workout_id": suggested_workout_id,
            "actual_workout_id": actual_workout_id,
            "exercise_list": exercise_list
        }), 200

    except Exception as e:
        print(e)
        return jsonify({"success": False, "error": str(e)}), 500


@workout_bp.route("/actual/exercise/<int:actual_workout_id>/<int:exercise_id>", methods=["DELETE"])
def delete_actual_exercise(actual_workout_id: int, exercise_id: int):
    """
    Delete the selected exercise from the actual_exercise_records table,
    scoped by actual_workout_id + exercise_id (does NOT touch suggested_exercise_records).

    Returns:
        {
            "success": True,
            "deleted": <int>,              # number of rows removed
            "actual_workout_id": <int>,
            "exercise_id": <int>
        }

    Note:
        If an exercise appears multiple times for the same actual workout (uncommon),
        this will remove ALL matching rows. If you need single-row precision,
        extend to accept an actual_record_id.
    """
    try:
        # print(actual_workout_id, exercise_id)
        # Check existence first
        exists = db.execute(
            """
            SELECT COUNT(*) 
            FROM actual_exercise_records
            WHERE actual_workout_id = %s AND exercise_id = %s
            """,
            (actual_workout_id, exercise_id),
            fetch=True
        )

        if not exists or exists[0][0] == 0:
            # print({
            #     "success": False,
            #     "error": "Exercise not found for this actual workout"
            # })
            return jsonify({
                "success": False,
                "error": "Exercise not found for this actual workout"
            }), 404

        # Delete the exercise row(s)
        db.execute(
            """
            DELETE FROM actual_exercise_records
            WHERE actual_workout_id = %s AND exercise_id = %s
            """,
            (actual_workout_id, exercise_id)
        )

        # Resequence order_index to keep neighbors logic consistent
        # Make order_index dense starting at 0 in the original ordering.
        db.execute(
            """
            WITH reseq AS (
                SELECT
                    actual_record_id,
                    ROW_NUMBER() OVER (ORDER BY order_index ASC, actual_record_id ASC) - 1 AS new_idx
                FROM actual_exercise_records
                WHERE actual_workout_id = %s
            )
            UPDATE actual_exercise_records aer
            SET order_index = r.new_idx
            FROM reseq r
            WHERE aer.actual_record_id = r.actual_record_id
              AND aer.actual_workout_id = %s
            """,
            (actual_workout_id, actual_workout_id)
        )

        # Report how many were removed (re-check count difference)
        remaining = db.execute(
            """
            SELECT COUNT(*)
            FROM actual_exercise_records
            WHERE actual_workout_id = %s
            """,
            (actual_workout_id,),
            fetch=True
        )[0][0]

        return jsonify({
            "success": True,
            "deleted": int(exists[0][0]),
            "remaining_in_workout": int(remaining),
            "actual_workout_id": actual_workout_id,
            "exercise_id": exercise_id
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Failed to delete exercise",
            "details": str(e)
        }), 500


@workout_bp.route("/exercise_navigation/<int:workout_id>/<int:exercise_id>", methods=["GET"])
def get_exercise_with_neighbors_by_workout(workout_id, exercise_id):
    """
    Given a workout_id and exercise_id, returns the full exercise data,
    the IDs of the previous and next exercises from actual_exercise_records,
    and the workout's split_group.
    """
    try:
        # Step 1: Get actual_workout_id AND split_group
        actual_workout_row = db.execute(
            """
            SELECT aw.actual_workout_id, w.split_group
            FROM actual_workout aw
            JOIN workouts w ON w.workout_id = aw.workout_id
            WHERE aw.workout_id = %s;
            """,
            (workout_id,),
            fetch=True
        )

        if not actual_workout_row:
            return jsonify({
                "error": "No actual_workout found for the given workout_id",
                "success": False
            }), 404

        actual_workout_id, split_group = actual_workout_row[0]

        # Step 2: Get all exercises for this actual workout, ordered by order_index
        records = db.execute(
            """
            SELECT
                aer.exercise_id,
                aer.intensity,
                aer.reps,
                aer.sets,
                aer.time,
                aer.exercise_type,
                aer.order_index,
                e.name,
                e.animation,
                e.written_instructions,
                e.equipment_type,
                e.loading_type,
                e.main_muscles,
                e.secondary_muscles
            FROM actual_exercise_records aer
            JOIN Exercises e ON aer.exercise_id = e.exercise_id
            WHERE aer.actual_workout_id = %s
            ORDER BY aer.order_index ASC;
            """,
            (actual_workout_id,),
            fetch=True
        )

        if not records:
            return jsonify({
                "error": "No exercises found for this workout",
                "success": False
            }), 404

        exercise_list = []
        target_index = None

        for idx, row in enumerate(records):
            (
                eid, intensity, reps, sets, time, exercise_type, order_index,
                name, video_link, instructions, equipment_type, loading_type,
                main_muscles, secondary_muscles
            ) = row

            if exercise_type == 'Gym Equipment':
                intensity = [round(float(w), 1) for w in intensity]
            elif exercise_type == 'Timed Exercise':
                intensity = [int(i.split(' ')[0]) for i in intensity]
            elif exercise_type == 'Resistance Band' or exercise_type == 'Bodyweight':
                intensity = intensity
            else: 
                intensity = None

            if eid == exercise_id:
                target_index = idx

            exercise_data = {
                "exercise_id": eid,
                "title": name,
                "video_link": video_link,
                "instructions": instructions,
                "exercise_type": exercise_type,
                "sets": sets,
                "reps": reps,
                "intensity": intensity,
                "time": time,
                "main_muscles": main_muscles,
                "secondary_muscles": secondary_muscles,
            }
            exercise_list.append(exercise_data)

        if target_index is None:
            return jsonify({
                "error": "Exercise not found in this workout",
                "success": False
            }), 404

        prev_exercise_id = (
            exercise_list[target_index - 1]["exercise_id"]
            if target_index > 0 else None
        )
        next_exercise_id = (
            exercise_list[target_index + 1]["exercise_id"]
            if target_index < len(exercise_list) - 1 else None
        )

        return jsonify({
            "exercise": exercise_list[target_index],
            "prev_exercise_id": prev_exercise_id,
            "next_exercise_id": next_exercise_id,
            "split_group": split_group,  # <-- Added here
            "success": True
        }), 200

    except Exception as e:
        print("Error: ", e)
        return jsonify({
            "error": "Failed to fetch exercise and navigation data",
            "details": str(e),
            "success": False
        }), 500


@workout_bp.route("/update_exercise_sets/<int:workout_id>/<int:exercise_id>", methods=["POST"])
def update_exercise_sets(workout_id, exercise_id):
    """
        Updates the sets, reps, weight, and done status for a given exercise
        in an actual workout.

        Expects:
        {
            "sets": [1, 0, 1, 1],
            "reps": [8, 10, 10, 12],
            "weight": [50.0, 50.0, 50.0, 50.0],
            "time": [5, 5, 5, 5]
        }
    """
    try:
        data = request.get_json()

        sets = data.get("sets")
        reps = data.get("reps")
        intensity = data.get("intensity")
        time = data.get("time")

        # print(sets, reps, intensity, time)

        if not all([sets, reps, intensity, time]) or not (
            len(sets) == len(reps) == len(intensity) == len(time)
        ):
            # print("yaya")
            return jsonify({
                "error": "sets, reps, and intensity must be lists of the same length",
                "success": False
            }), 400

        # Get actual_workout_id
        result = db.execute(
            "SELECT actual_workout_id FROM actual_workout WHERE workout_id = %s;",
            (workout_id,),
            fetch=True
        )

        if not result:
            return jsonify({"error": "Workout not found", "success": False}), 404

        actual_workout_id = result[0][0]

        # Update the record
        update_query = """
            UPDATE actual_exercise_records
            SET
                sets = %s,
                reps = %s,
                intensity = %s,
                time = %s
            WHERE
                actual_workout_id = %s AND exercise_id = %s;
        """

        db.execute(update_query, (
            sets,
            reps,
            intensity,
            time,
            actual_workout_id,
            exercise_id
        ))

        return jsonify({
            "message": "Exercise sets updated successfully",
            "success": True
        }), 200

    except Exception as e:
        print("ek", e)
        return jsonify({
            "error": "Failed to update exercise sets",
            "details": str(e),
            "success": False
        }), 500


""" Might not need this route. Initially created it for database """
@workout_bp.route("/database/exercise/<int:exercise_id>", methods=["GET"])
def get_specific_exercise(exercise_id):
    """
    Fetch detailed data for a single exercise by its ID.
    
    Returns:
        - exercise_id
        - name
        - animation (video_link)
        - written_instructions
        - equipment_type
        - loading_type
        - main_muscles
        - secondary_muscles
        - difficulty
        - progression
        - regression
        - variations
    """
    try:
        query = """
            SELECT exercise_id, name, animation, written_instructions,
                   equipment_type, loading_type, main_muscles, secondary_muscles,
                   difficulty, progression, regression, variations
            FROM Exercises
            WHERE exercise_id = %s;
        """
        result = db.execute(query, (exercise_id,), fetch=True)

        if not result:
            return jsonify({"error": "Exercise not found", "success": False}), 404

        row = result[0]
        exercise_data = {
            "exercise_id": row[0],
            "name": row[1],
            "video_link": row[2],
            "instructions": row[3],
            "equipment_type": row[4],
            "loading_type": row[5],
            "main_muscles": row[6],
            "secondary_muscles": row[7],
            "difficulty": row[8],
            "progression": row[9],
            "regression": row[10],
            "variations": row[11]
        }

        return jsonify({"exercise": exercise_data, "success": True}), 200

    except Exception as e:
        return jsonify({"error": "Failed to retrieve exercise", "details": str(e), "success": False}), 500


@workout_bp.route("/recommend_split/<int:user_id>", methods=["GET"])
def get_recommend_split(user_id):
    try:
        # Fetch user’s venue info
        row = db.execute(
            """
            SELECT v.days_of_week,
                   v.workout_frequency,
                   v.time_per_workout,
                   u.level,
                   v.goals
            FROM Venues v
            JOIN Users u ON u.current_venue_id = v.venue_id
            WHERE u.user_id = %s
            """,
            (user_id,),
            fetch=True
        )

        if not row:
            return jsonify({"success": False, "error": "No venue data found for user"}), 404

        days_of_week, workout_frequency, time_per_workout, level, goals = row[0]

        day_to_int = {
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
            "sunday": 7,
        }

        days_of_week = [day_to_int[w.lower()] for w in days_of_week]

        # Call your recommend_split function
        split = recommend_split(
            days_of_week=days_of_week,
            workout_frequency=workout_frequency,
            time_per_workout=time_per_workout,
            level=level,
            goals=goals,
        )

        return jsonify({
            "success": True,
            "recommended_split": split
        })

    except Exception as e:
        print(e)
        return jsonify({"success": False, "error": str(e)}), 500


@workout_bp.route("/adjust_difficulty/<string:mode>/<int:exercise_id>/<int:user_id>", methods=["POST"])
def adjust_exercise_difficulty(mode, exercise_id, user_id):
    try:
        if mode not in ["challenge", "easy"]:
            return jsonify({"error": "Invalid mode. Must be 'challenge' or 'easy'."}), 400

        # Get the user’s experience level
        user_query = "SELECT level FROM Users WHERE user_id = %s;"
        user_result = db.execute(user_query, (user_id,), fetch=True)
        if not user_result:
            return jsonify({"error": "User not found"}), 404
        user_level = user_result[0][0]

        # Get the current exercise data
        exercise_query = """
            SELECT name, progression, regression, difficulty 
            FROM Exercises 
            WHERE exercise_id = %s;
        """
        result = db.execute(exercise_query, (exercise_id,), fetch=True)
        if not result:
            return jsonify({"error": "Exercise not found"}), 404

        current_name, progression, regression, current_difficulty = result[0]
        candidates = progression if mode == "challenge" else regression
        candidates = candidates or []

        # Load candidate exercises and compare difficulty
        filtered_exercises = []
        for name in candidates:
            alt_query = "SELECT exercise_id, name, difficulty FROM Exercises WHERE name = %s;"
            alt_result = db.execute(alt_query, (name,), fetch=True)
            if alt_result:
                ex_id, ex_name, ex_difficulty = alt_result[0]
                if (
                    (mode == "challenge" and ex_difficulty <= user_level + 1) or
                    (mode == "easy" and ex_difficulty <= user_level)
                ):
                    filtered_exercises.append({
                        "exercise_id": ex_id,
                        "name": ex_name,
                        "difficulty": ex_difficulty
                    })

        if not filtered_exercises:
            return jsonify({"message": "No suitable alternatives found"}), 200

        # For now, return the first match (you can randomize later)
        return jsonify({"replacement": filtered_exercises[0], "success": True}), 200

    except Exception as e:
        return jsonify({"error": "Failed to adjust difficulty", "details": str(e)}), 500


@workout_bp.route("/database", methods=["GET"])
def exercise_database():
    try:
        query = """
            SELECT exercise_id, name
            FROM Exercises;
        """
        rows = db.execute(query, fetch=True)

        """ Will have to add the exercise image path of the actual image. """
        exercises = [{"exercise_id": row[0], "name": row[1]} for row in rows]

        return jsonify({"exercises": exercises, "success": True}), 200

    except Exception as e:
        return jsonify({"error": "Error retrieving exercises", "details": str(e)}), 500


@workout_bp.route("/database/search/<string:keyword>", methods=["GET"])
def exercise_database_search(keyword):
    try:
        query = """
            SELECT exercise_id, name
            FROM Exercises
            WHERE name ILIKE %s;
        """
        pattern = f"%{keyword}%"  # Wildcard search
        rows = db.execute(query, (pattern,), fetch=True)

        exercises = [{"exercise_id": row[0], "name": row[1]} for row in rows]

        return jsonify({"exercises": exercises, "success": True}), 200

    except Exception as e:
        return jsonify({"error": "Error retrieving exercises", "details": str(e)}), 500


@workout_bp.route("/database/filter", methods=["POST"])
def exercise_database_filter():
    """
    Filters Exercises with:
      - AND across categories, OR within a category
      - Case-insensitive matching for muscle_groups & equipment
      - Favorites-only (preference=3) and hide-banned (preference!=1) via exercise_preferences
    """
    try:
        data = request.get_json(force=True) or {}

        # Incoming filters (only what the client actually sends)
        muscle_groups   = data.get("muscle_groups", [])        # TEXT[]
        equipment       = data.get("equipment", [])            # TEXT[]
        difficulty      = data.get("difficulty", [])           # INT[]
        equipment_type  = data.get("equipment_type", [])       # INT[]
        level           = data.get("level", [])                # TEXT[]
        risk_level      = data.get("risk_level", [])           # INT[]
        pain_exclusions = data.get("pain_exclusions", [])      # TEXT[]

        favorites_only  = bool(data.get("favorites_only", False))
        hide_banned     = bool(data.get("hide_banned", False))
        user_id         = data.get("user_id")

        # Case-insensitive helpers for text arrays
        mg_lower        = [m.lower() for m in muscle_groups] if muscle_groups else []
        lvl_lower       = [l.lower() for l in level] if level else []
        pain_lower      = [p.lower() for p in pain_exclusions] if pain_exclusions else []
        eq_lower_exact  = [e.lower() for e in equipment] if equipment else []              # exact (case-insensitive)
        eq_lower_ilike  = [f"%{e.lower()}%" for e in equipment] if equipment else []       # fuzzy (e.g., "%barbell%")

        # Only join preferences when necessary
        join_prefs = bool(user_id) and (favorites_only or hide_banned)

        where = []
        params = []

        # MUSCLES: case-insensitive on main OR secondary
        if mg_lower:
            where.append("""
                (
                  EXISTS (
                    SELECT 1 FROM UNNEST(COALESCE(e.main_muscles, '{}')) m
                    WHERE LOWER(m) = ANY(%s)
                  )
                  OR
                  EXISTS (
                    SELECT 1 FROM UNNEST(COALESCE(e.secondary_muscles, '{}')) s
                    WHERE LOWER(s) = ANY(%s)
                  )
                )
            """)
            params.extend([mg_lower, mg_lower])

        # EQUIPMENT: case-insensitive exact OR fuzzy (handles variants like "Olympic Barbell")
        if eq_lower_exact:
            where.append("""
                (
                  EXISTS (
                    SELECT 1 FROM UNNEST(COALESCE(e.equipment, '{}')) eq
                    WHERE LOWER(eq) = ANY(%s)
                  )
                  OR
                  EXISTS (
                    SELECT 1 FROM UNNEST(COALESCE(e.equipment, '{}')) eq2
                    WHERE eq2 ILIKE ANY(%s)
                  )
                )
            """)
            params.extend([eq_lower_exact, eq_lower_ilike])

        # LEVEL: case-insensitive overlap
        if lvl_lower:
            where.append("""
                EXISTS (
                  SELECT 1 FROM UNNEST(COALESCE(e.level, '{}')) lv
                  WHERE LOWER(lv) = ANY(%s)
                )
            """)
            params.append(lvl_lower)

        # DIFFICULTY / EQUIPMENT_TYPE / RISK_LEVEL: numeric arrays
        if difficulty:
            where.append("e.difficulty = ANY(%s)")
            params.append(difficulty)

        if equipment_type:
            where.append("e.equipment_type = ANY(%s)")
            params.append(equipment_type)

        if risk_level:
            where.append("e.risk_level = ANY(%s)")
            params.append(risk_level)

        # PAIN EXCLUSIONS: exclude if any overlap (case-insensitive)
        if pain_lower:
            where.append("""
                NOT EXISTS (
                  SELECT 1 FROM UNNEST(COALESCE(e.pain_exclusions, '{}')) pe
                  WHERE LOWER(pe) = ANY(%s)
                )
            """)
            params.append(pain_lower)

        # Preferences filters
        if favorites_only and user_id:
            where.append("ep.preference = 3")
        if hide_banned and user_id:
            # If no pref row exists, it's allowed (LEFT JOIN). Exclude explicit bans.
            where.append("(ep.preference IS NULL OR ep.preference <> 1)")

        # -------- Build SQL --------
        sql = """
            SELECT
                e.exercise_id, e.name, e.main_muscles, e.secondary_muscles,
                e.animation, e.written_instructions, e.movement, e.lower_bound,
                e.level, e.difficulty, e.equipment_type, e.equipment,
                e.prerequisite_exercise, e.variations, e.regression, e.progression,
                e.loading_type, e.risk_level, e.exercise_purpose, e.force_type, e.pain_exclusions
            FROM Exercises e
        """

        if join_prefs:
            # user_id param must come before WHERE params when we add it here
            sql += " LEFT JOIN exercise_preferences ep ON ep.exercise_id = e.exercise_id AND ep.user_id = %s"
            params.insert(0, user_id)

        if where:
            sql += " WHERE " + " AND ".join(where)

        # Favor favorites on top when joined, then alphabetical
        if join_prefs:
            sql += " ORDER BY CASE WHEN ep.preference = 3 THEN 0 ELSE 1 END, LOWER(e.name);"
        else:
            sql += " ORDER BY LOWER(e.name);"

        rows = db.execute(sql, tuple(params), fetch=True)

        exercises = [{
            "exercise_id": r[0],
            "name": r[1],
            "main_muscles": r[2] or [],
            "secondary_muscles": r[3] or [],
            "animation": r[4],
            "written_instructions": r[5],
            "movement": r[6],
            "lower_bound": r[7],
            "level": r[8] or [],
            "difficulty": r[9],
            "equipment_type": r[10],
            "equipment": r[11] or [],
            "prerequisite_exercise": r[12] or [],
            "variations": r[13] or [],
            "regression": r[14] or [],
            "progression": r[15] or [],
            "loading_type": r[16],
            "risk_level": r[17],
            "exercise_purpose": r[18] or [],
            "force_type": r[19] or [],
            "pain_exclusions": r[20] or [],
        } for r in rows]

        return jsonify({"exercises": exercises}), 200

    except Exception as e:
        print("exercise_database_filter error:", e)
        return jsonify({"error": "Failed to filter exercises"}), 500


@workout_bp.route("/variations/<int:exercise_id>", methods=["GET"])
def get_exercise_variations(exercise_id):
    try:
        query = "SELECT variations FROM Exercises WHERE exercise_id = %s;"
        result = db.execute(query, (exercise_id,), fetch=True)

        if not result:
            return jsonify({"error": "Exercise not found"}), 404

        variation_names = result[0][0] or []

        if not variation_names:
            return jsonify({"variations": [], "message": "No variations available", "success": True}), 200

        placeholder = ','.join(['%s'] * len(variation_names))
        variation_query = f"""
            SELECT exercise_id, name
            FROM Exercises
            WHERE name IN ({placeholder});
        """
        variation_rows = db.execute(variation_query, tuple(variation_names), fetch=True)

        variations = [{"exercise_id": row[0], "name": row[1]} for row in variation_rows]

        return jsonify({"variations": variations, "success": True}), 200

    except Exception as e:
        return jsonify({"error": "Failed to retrieve variations", "details": str(e)}), 500
    

@workout_bp.route("/exercise_preference/<int:user_id>/<int:exercise_id>", methods=["GET"])
def get_exercise_preference(user_id, exercise_id):
    """
    Fetch the user's preference for a specific exercise.
    """
    try:
        result = db.execute(
            """
            SELECT preference
            FROM exercise_preferences
            WHERE user_id = %s AND exercise_id = %s;
            """,
            (user_id, exercise_id),
            fetch=True
        )

        if not result:
            return jsonify({"preference": None, "success": True}), 200

        return jsonify({
            "preference": result[0][0],  # 1, 2, or 3
            "success": True
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Failed to fetch exercise preference",
            "details": str(e),
            "success": False
        }), 500


@workout_bp.route("/exercise_preference/<int:user_id>/<int:exercise_id>", methods=["POST"])
def set_exercise_preference(user_id, exercise_id):
    """
    Set or update the user's preference for a specific exercise.

    Expects:
    {
        "preference": 1 -> favorite | 2 -> suggest less | 3 -> don't show again
    }
    """
    try:
        data = request.get_json()
        preference = data.get("preference")

        if preference not in [1, 2, 3]:
            return jsonify({
                "error": "Invalid preference value. Must be 1 (favorite), 2 (suggest less), or 3 (don't show again).",
                "success": False
            }), 400

        db.execute(
            """
            INSERT INTO exercise_preferences (user_id, exercise_id, preference)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, exercise_id)
            DO UPDATE SET preference = EXCLUDED.preference;
            """,
            (user_id, exercise_id, preference)
        )

        return jsonify({
            "message": "Preference saved successfully",
            "success": True
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({
            "error": "Failed to save preference",
            "details": str(e),
            "success": False
        }), 500