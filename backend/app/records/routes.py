from flask import Blueprint, jsonify
from app.db import db

records_bp = Blueprint("records", __name__, url_prefix="/records")

@records_bp.route("/<int:user_id>/<int:month>/<int:year>", methods=["GET"])
def get_user_records(user_id, month, year):
    try:
        workout_query = """
            SELECT w.workout_id, w.date, w.phase, w.split_group, aw.duration_actual
            FROM workouts w
            LEFT JOIN actual_workout aw ON w.workout_id = aw.workout_id
            WHERE w.user_id = %s
              AND EXTRACT(MONTH FROM w.date) = %s
              AND EXTRACT(YEAR  FROM w.date) = %s
            ORDER BY w.date DESC;
        """
        workouts = db.execute(workout_query, (user_id, month, year), fetch=True)

        sessions = []

        def flatten(lst):
            for item in (lst or []):
                if isinstance(item, list):
                    yield from flatten(item)
                else:
                    yield item

        for workout in workouts or []:
            workout_id, date, phase, split_group, duration_actual = workout

            # Pull intensity (TEXT[]), reps, sets, names, muscles, and exercise_type
            exercise_query = """
                SELECT
                    aer.exercise_id,
                    aer.intensity,           -- TEXT[]
                    aer.reps,                -- INT[]
                    aer.sets,                -- INT[]
                    e.name          AS exercise_name,
                    e.main_muscles,
                    e.secondary_muscles,
                    aer.exercise_type
                FROM actual_exercise_records aer
                JOIN Exercises e ON aer.exercise_id = e.exercise_id
                WHERE aer.actual_workout_id = (
                    SELECT actual_workout_id FROM actual_workout WHERE workout_id = %s
                );
            """
            exercise_records = db.execute(exercise_query, (workout_id,), fetch=True)

            total_volume = 0.0
            total_sets = 0
            exercises_completed = 0
            muscles_engaged = set()
            personal_bests = []
            exercise_dict = {}

            for record in exercise_records or []:
                (exercise_id, intensity_arr, reps_arr, sets_arr, exercise_name,
                 main_muscles, secondary_muscles, exercise_type) = record

                # Normalize arrays
                reps = []
                for x in flatten(reps_arr or []):
                    try:
                        reps.append(int(x))
                    except (TypeError, ValueError):
                        continue

                sets = []
                for x in flatten(sets_arr or []):
                    try:
                        sets.append(int(x))
                    except (TypeError, ValueError):
                        continue

                # Parse numeric intensities only (skip "Bodyweight", band colors/names, etc.)
                # numeric_intensity = []
                # for v in flatten(intensity_arr or []):
                #     if isinstance(v, (int, float)):
                #         numeric_intensity.append(float(v))
                #     elif isinstance(v, str):
                #         vv = v.strip()
                #         # digits with at most one decimal point
                #         if vv and all(ch.isdigit() or ch == '.' for ch in vv) and vv.replace('.', '', 1).isdigit():
                #             try:
                #                 numeric_intensity.append(float(vv))
                #             except ValueError:
                #                 pass

                numeric_intensity = []

                if exercise_type == 'Gym Equipment':
                    numeric_intensity = [float(i) for i in intensity_arr]
                else:
                    numeric_intensity = intensity_arr

                # Compute volume on aligned indices only; sets==1 means
                # completed
                # print(exercise_name, '\n', reps, sets, numeric_intensity)
                min_len = min(len(reps), len(sets))
                # print("min_len: ", min_len)
                completed_intensities = []
                for i in range(min_len):
                    r, s, wt = reps[i], sets[i], numeric_intensity[i]
                    # print(f"s is: {s}")
                    if s == 1:
                        total_volume += wt * r * s  if exercise_type == 'Gym Equipment' else r * s      # s is 1 here, but keep formula for clarity
                        total_sets += s
                        completed_intensities.append(wt)

                exercises_completed += 1

                # Normalize muscles for the per-session rollup
                for m in (main_muscles or []):
                    if m:
                        muscles_engaged.add(m.strip().capitalize())
                for m in (secondary_muscles or []):
                    if m:
                        muscles_engaged.add(m.strip().capitalize())

                # Build per-exercise rollup (keep legacy "weights" AND new "intensity")
                if exercise_name not in exercise_dict:
                    exercise_dict[exercise_name] = {
                        "sets": [],
                        "reps": [],
                        "intensity": [],   # canonical numeric intensities for completed sets
                        "weights": [],     # legacy alias (same values for now)
                        "muscle": list(set([
                            m.strip().capitalize()
                            for m in (main_muscles or []) + (secondary_muscles or [])
                            if m
                        ]))
                    }

                # We keep all reps for display, but intensity/weights track numeric ones (completed sets only)
                exercise_dict[exercise_name]["sets"].extend(sets)
                exercise_dict[exercise_name]["reps"].extend(reps)
                exercise_dict[exercise_name]["intensity"].extend(completed_intensities)
                exercise_dict[exercise_name]["weights"].extend(completed_intensities)

                # ----- Personal Best (historical) -----
                # Only completed sets (sets[i] = 1), numeric intensity, and strictly before this session date
                personal_best_query = """
                    SELECT MAX(val::DECIMAL) AS best_weight
                    FROM (
                        SELECT it.iv AS val
                        FROM actual_exercise_records aer
                        JOIN actual_workout aw ON aer.actual_workout_id = aw.actual_workout_id
                        JOIN workouts w ON w.workout_id = aw.workout_id
                        , UNNEST(aer.intensity) WITH ORDINALITY AS it(iv, i)
                        , UNNEST(aer.sets)      WITH ORDINALITY AS st(sr, j)
                        WHERE w.user_id = %s
                          AND aer.exercise_id = %s
                          AND w.date < %s
                          AND i = j              -- align indices
                          AND sr = 1             -- completed sets only
                          AND iv ~ '^[0-9]+(\\.[0-9]+)?$'  -- numeric intensity only
                    ) t;
                """
                past_best = db.execute(personal_best_query, (user_id, exercise_id, date), fetch=True)
                best_weight = float(past_best[0][0]) if past_best and past_best[0] and past_best[0][0] is not None else 0.0

                # Current-session PB should consider only completed sets

                if exercise_type == 'Gym Equipment':
                    current_max_weight = max(completed_intensities or [0.0])
                    if current_max_weight > best_weight:
                        personal_bests.append({
                            "exercise": exercise_name,
                            "weight": current_max_weight,
                            "reps": reps,
                            "sets": sets
                        })
                
            # Format list of exercises for this session
            exercise_list = [
                {
                    "title": name,
                    "sets": data["sets"],
                    "reps": data["reps"],
                    "intensity": data["intensity"],  # numeric, completed sets only
                    "weights": data["weights"],      # legacy alias
                    "muscle": data["muscle"]
                }
                for name, data in exercise_dict.items()
            ]

            # print(exercise_list)

            # print(f"final s: {total_sets} date: {date}")

            # Build session summary
            session = {
                "id": workout_id,
                "date": str(date),
                "workoutType": phase if phase else split_group,
                "duration": int(duration_actual or 0),
                "volume": float(total_volume),
                "totalSets": int(total_sets),
                "exercisesCompleted": int(exercises_completed),
                "personalBests": personal_bests,
                "musclesEngaged": sorted(list(muscles_engaged)),
                "exerciseList": exercise_list
            }

            sessions.append(session)

        return jsonify({
            "user_id": user_id,
            "sessions": sessions,
            "success": True
        }), 200

    except Exception as e:
        print("waaaaaa", str(e))
        return jsonify({
            "error": "Error retrieving workout records",
            "details": str(e)
        }), 500
