from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
import json
import ast

def build_available_weights(equipment_rows):
    """
    equipment_rows: list of dicts, each like:
      {"equipment_id": 1, "name": "Dumbbells", "quantity": 3, "weight_resistance_time": "5.0"}
    Returns:
      {
        "Dumbbells": {5.0: 3, 10.0: 2, ...},
        "Kettlebells": {5.0: 2, 10.0: 2, ...},
        ...
      }
    """
    available_weights = defaultdict(dict)
    # print(equipment_rows)
    for row in equipment_rows:
        name = row["name"]
        qty = row.get("quantity", 0)
        weight_str = row.get("weight_resistance_time")
        # print(f"{name} {weight_str} {qty}")
        if not weight_str:  # skip if no weight info
            continue

        try:
            weight = float(weight_str)
            # Store as int if it's a whole number (e.g., 5.0 → 5)
            if weight.is_integer():
                weight = int(weight)
        except ValueError:
            weight = weight_str

        available_weights[name][weight] = qty

    return dict(available_weights)


DAY_MAP = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7
}


def compute_age(bday) -> int:
    if not bday:
        return 0  # or a sensible default
    if isinstance(bday, str):
        try:
            bday = datetime.strptime(bday, "%Y-%m-%d").date()
            # print(bday)
        except ValueError:
            return 0
    today = date.today()
    return today.year - bday.year - ((today.month, today.day) < (bday.month, bday.day))


def build_exercise_payloads(db, exercises_list):
    """
    Given exercises_list like:
        [{'exercise': 'Close-grip barbell floor press', 'suggested_intensity': {'weight': 20, 'reps': 10}}, ...]
    Look up each by Exercises.name (case-insensitive, trimmed) and return the payloads in the same order.
    """
    # 1) Normalize incoming names
    incoming = []
    for item in exercises_list or []:
        name_raw = (item.get("exercise") or "").strip()
        si = item.get("suggested_intensity")

        if si.get("exercise_type") == 'Gym Equipment' or si.get("exercise_type") == 'Resistance Band':
            exercise_intensity = str(si.get("weight"))
        elif si.get("exercise_type") == 'Bodyweight':
            exercise_intensity = "Bodyweight"
        elif si.get("exercise_type") == 'Timed Exercise':
            exercise_intensity = si.get("time")
        else:
            exercise_intensity = None

        incoming.append({
            "name_raw": name_raw,
            "name_norm": name_raw.lower().strip(),   
            "reps": si.get("reps"),
            "exercise_type": si.get("exercise_type"), 
            "intensity": exercise_intensity,
            "time": si.get("time"),
        })

    if not incoming:
        return []

    # 2) Unique normalized names for query
    uniq_names = sorted({x["name_norm"] for x in incoming if x["name_norm"]})

    rows = db.execute(
        """
        SELECT
            exercise_id,
            name,
            animation AS video_link,
            written_instructions AS instructions
        FROM Exercises
        WHERE LOWER(TRIM(name)) = ANY(%s)
        ORDER BY array_position(%s, LOWER(TRIM(name)))
        """,
        (uniq_names, uniq_names),
        fetch=True
    ) or []

    # 3) Map normalized DB name → row
    by_norm_name = {
        (r[1] or "").strip().lower(): {
            "exercise_id": r[0],
            "title": r[1].strip(),
            "video_link": r[2],
            "instructions": r[3],
            # "exercise_type": exercises_type[i],         #r[4],
        }
        for r in rows
    }
    # 4) Build payloads in original order
    payloads = []
    for x in incoming:
        found = by_norm_name.get(x["name_norm"])

        payloads.append({
            "exercise_id": (found["exercise_id"] if found else None),
            "title": (found["title"] if found else x["name_raw"]),
            "video_link": (found["video_link"] if found else None),
            "instructions": (found["instructions"] if found else None),
            "exercise_type": (x.get("exercise_type")),
            "sets": [0],
            "reps": [int(x["reps"])] if x["reps"] else None,
            "time": [0],
            "intensity": x.get('intensity'),
        })
    return payloads

def get_today_workout(split, workout_counter):
    """
    Determine today's workout based on the split and the number of workouts
    the user has COMPLETED SO FAR (pre-increment).

    Parameters:
    - split (str): Name of the workout split.
    - workout_counter (int): Number of workouts completed so far (0,1,2,...).

    Returns:
    - str: Today's workout.
    """
    split_cycles = {
        "Full-Body": ["Full-Body"],
        "Upper-Lower": ["Upper", "Lower"],
        "Push-Pull-Legs": ["Push", "Pull", "Legs"],
        "Power Hypertrophy Upper Lower": [
            "Power Upper", "Power Lower", "Hypertrophy Upper", "Hypertrophy Lower"
        ],
        "Hybrid PPL + Upper-Lower": [
            "Push", "Pull", "Legs", "Upper", "Lower"
        ],
        "Body Part Split": [
            "Chest", "Back", "Shoulders", "Arms", "Legs"
        ],
        "6-Day Body Part Split": [
            "Chest", "Back", "Shoulders", "Arms", "Legs", "Core"
        ],
        "Push-Pull-Legs + active rest": [
            "Push", "Pull", "Legs", "Active Rest"
        ]
    }

    if split not in split_cycles:
        raise ValueError(f"Unknown split: {split}")

    cycle = split_cycles[split]

    # Pre-increment semantics: next workout = completed_so_far % len(cycle)
    today_index = workout_counter % len(cycle)

    # (Optional) clearer logging
    # print(f"[get_today_workout] completed_so_far={workout_counter} → idx={today_index} → {cycle[today_index]}")
    return cycle[today_index]

def persist_generated_workout(db, user_id, user_timezone, generated_exercises, split_group=None, estimated_time=0):
    """
    Persist generated_exercises into:
      workouts → suggested_workouts → suggested_exercise_records
               → actual_workout → actual_exercise_records

    Extracts split_group from the first exercise's 'exercise_type'
    and phase from the first exercise if available (else defaults).

    Returns:
        created: dict with ids and metadata:
            - workout_id
            - suggested_workout_id
            - actual_workout_id
            - split_group
            - reset_progress_timer = True  # signal to frontend to clear timer
    """
    if not generated_exercises:
        raise ValueError("No exercises provided to persist.")
    
    phase = generated_exercises[0].get("phase") or "Hypertrophy"

    # Normalize exercises for DB insert
    def _as_record_fields(ge, idx):
        sets = ge.get("sets") or [0]
        reps = ge.get("reps") or [10]
        time = ge.get("time") or [0]

        exercise_type = ge.get("exercise_type")
        intensity = ge.get("intensity")

        # store intensity as a 4-length array (to match reps/sets/time padding)
        intensity_arr = [intensity if intensity is not None else None] * 4

        sets_count = [int(s) for s in sets]
        reps_count = [int(r) for r in reps]
        time_count = [int(t) for t in time]

        return {
            "exercise_id": ge.get("exercise_id"),
            "sets": sets_count if len(sets_count) != 1 else sets_count * 4,
            "reps": reps_count if len(reps_count) != 1 else reps_count * 4,
            "intensity": intensity_arr,
            "exercise_type": exercise_type,
            "time": time_count if len(time_count) != 1 else time_count * 4,
            "order_index": idx,
        }

    per_ex = [_as_record_fields(ge, idx) for idx, ge in enumerate(generated_exercises)]

    created = {}
    try:
        db.execute("BEGIN")

        # Use user's timezone for the workout's calendar date
        user_tz = ZoneInfo(user_timezone)
        now_utc = datetime.now(timezone.utc)
        local_date = now_utc.astimezone(user_tz).date()

        # 1) workouts
        rows = db.execute(
            """
            INSERT INTO workouts (user_id, date, phase, split_group)
            VALUES (%s, %s, %s, %s)
            RETURNING workout_id
            """,
            (user_id, local_date, phase, split_group),
            fetch=True
        )
        workout_id = rows[0][0]
        created["workout_id"] = workout_id
        created["split_group"] = split_group

        # 2) suggested_workouts
        rows = db.execute(
            """
            INSERT INTO suggested_workouts (workout_id, duration_predicted)
            VALUES (%s, %s)
            RETURNING suggested_workout_id
            """,
            (workout_id, estimated_time),
            fetch=True
        )
        suggested_workout_id = rows[0][0]
        created["suggested_workout_id"] = suggested_workout_id

        # 3) suggested_exercise_records
        for rec in per_ex:
            db.execute(
                """
                INSERT INTO suggested_exercise_records
                    (suggested_workout_id, exercise_id, exercise_type, intensity, reps, sets, time, order_index)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    suggested_workout_id,
                    rec["exercise_id"],
                    rec["exercise_type"],
                    rec["intensity"],
                    rec["reps"],
                    rec["sets"],
                    rec["time"],
                    rec["order_index"],
                ),
                fetch=False
            )

        # 4) actual_workout
        rows = db.execute(
            """
            INSERT INTO actual_workout (workout_id, duration_actual)
            VALUES (%s, %s)
            RETURNING actual_workout_id
            """,
            (workout_id, 0),  # initialize as not-started / 0 duration
            fetch=True
        )
        actual_workout_id = rows[0][0]
        created["actual_workout_id"] = actual_workout_id

        # 5) actual_exercise_records
        for rec in per_ex:
            db.execute(
                """
                INSERT INTO actual_exercise_records
                    (actual_workout_id, exercise_id, exercise_type, intensity, reps, sets, time, order_index)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    actual_workout_id,
                    rec["exercise_id"],
                    rec["exercise_type"],
                    rec["intensity"],
                    rec["reps"],
                    rec["sets"],
                    rec["time"],
                    rec["order_index"],
                ),
                fetch=False
            )

        db.execute("COMMIT")

        # # Signal the caller that a NEW workout was created, 
        # so the app should clear any running timer.
        # created["reset_progress_timer"] = True

        return created

    except Exception:
        db.execute("ROLLBACK")
        raise

def fetch_exercise_list(db, actual_workout_id: int):
    """
    Returns the exact shape UI uses for each exercise:
    {
        "exercise_id": int,
        "title": str,
        "video_link": str | None,
        "instructions": str | None,
        "exercise_type": str | None,
        "animation": str | None,
        "sets": [int],
        "reps": [int],
        "intensity_type": "Gym Equipment" | "Resistance Band" | "Time Exercise" | "Bodyweight",
        "intensity": float | int | None
    }
    """
    rows = db.execute(
        """
        SELECT
            aer.exercise_id,
            ex.name,
            ex.animation            AS video_link,
            ex.written_instructions AS instructions,
            aer.exercise_type       AS exercise_type,
            aer.intensity,          -- Text[]
            aer.reps,               -- INT[]
            aer.sets,               -- INT[]
            aer.time,               -- INT (seconds)
            aer.order_index
        FROM actual_exercise_records aer
        JOIN Exercises ex ON ex.exercise_id = aer.exercise_id
        WHERE aer.actual_workout_id = %s
        ORDER BY aer.order_index ASC
        """,
        (actual_workout_id,),
        fetch=True
    ) or []


    exercise_list = []
    for (exercise_id, name, video_link, instructions, exercise_type,
         intensity_arr, reps_arr, sets_arr, time_arr, order_index) in rows:

        exercise_list.append({
            "exercise_id": exercise_id,
            "title": name,
            "video_link": video_link or "animation_path_placeholder",
            "instructions": instructions or "written_instructions_placeholder",
            "exercise_type": exercise_type,  # e.g., "Push"
            "sets": [int(s or 0) for s in sets_arr],
            "reps": [int(r or 0) for r in reps_arr],
            "time": time_arr,
            "intensity": intensity_arr[-1],
            "intensity_arr": intensity_arr,
        })

    return exercise_list

def workout_has_any_completed_set(db, workout_id: int = None, actual_workout_id: int = None) -> bool:
    """
    Returns True if the workout has ANY completed set (i.e., a 1 appears in any 'sets' array)
    across its actual_exercise_records. Otherwise False.

    You can call with either workout_id OR actual_workout_id.
    """
    if actual_workout_id is None and workout_id is None:
        raise ValueError("Provide workout_id or actual_workout_id")

    # Resolve actual_workout_id from workout_id if needed
    if actual_workout_id is None:
        row = db.execute(
            "SELECT actual_workout_id FROM actual_workout WHERE workout_id = %s",
            (int(workout_id),),
            fetch=True
        )
        if not row or row[0][0] is None:
            return False
        actual_workout_id = int(row[0][0])

    # Check if any exercise row has a '1' in its sets array
    # COALESCE handles NULL arrays; UNNEST lets us search within the array.
    res = db.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM actual_exercise_records aer
            WHERE aer.actual_workout_id = %s
              AND EXISTS (
                    SELECT 1
                    FROM UNNEST(COALESCE(aer.sets, '{}')) AS s
                    WHERE s = 1
              )
        )
        """,
        (int(actual_workout_id),),
        fetch=True
    )
    return bool(res and res[0][0])


def _parse_equipment_spec(raw):
    """
    Normalize the Exercises.equipment value into OR-of-AND groups.

    Returns a list of groups; each group is a list of required items:
      [
        ["Functional trainer cable machine", "1 Single grip handle"],
        ["Adjustable pulley", "1 Single grip handle"]
      ]

    Accepted inputs:
      - None or []                          -> []
      - ["Cable Machine", "Ankle Strap"]    -> [["Cable Machine","Ankle Strap"]]   (AND only)
      - '{{"A","B"},{"C","B"}}'             -> [["A","B"], ["C","B"]]              (OR of AND)
      - '[["A","B"],["C","B"]]'             -> same as above (JSON)
      - '{"A","B"}'                         -> [["A","B"]]                         (single group)
    """
    if raw is None:
        return []

    # If DB already gives a Python list of strings (TEXT[])
    if isinstance(raw, list):
        # If it's a flat list of strings -> one AND-group
        if all(isinstance(x, str) for x in raw):
            return [ [x for x in raw if x] ]
        # If it's list of lists -> assume already groups
        if all(isinstance(g, list) for g in raw):
            return [ [x for x in g if x] for g in raw ]
        # Fallback
        return []

    # If it's a string, try JSON first
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []

        # JSON array-of-arrays
        try:
            data = json.loads(s)
            if isinstance(data, list) and all(isinstance(g, list) for g in data):
                return [ [str(x) for x in g if x] for g in data ]
            if isinstance(data, list) and all(isinstance(x, str) for x in data):
                return [ [x for x in data if x] ]
        except Exception:
            pass

        # Brace format: {{...},{...}} or {"A","B"}
        # Convert braces to brackets and safely eval
        try:
            t = s.replace("{", "[").replace("}", "]")
            data = ast.literal_eval(t)
            # data could be ["A","B"] or [["A","B"],["C","B"]]
            if isinstance(data, list) and all(isinstance(x, str) for x in data):
                return [ [x for x in data if x] ]
            if isinstance(data, list) and all(isinstance(g, list) for g in data):
                return [ [str(x) for x in g if x] for g in data ]
        except Exception:
            pass

    # Fallback: nothing we could parse
    return []


def _get_user_equipment_context(db, user_id: int):
    # Current venue
    vrow = db.execute(
        "SELECT current_venue_id FROM Users WHERE user_id = %s",
        (user_id,), fetch=True
    )
    if not vrow:
        raise ValueError("User not found")
    (venue_id,) = vrow[0]
    if venue_id is None:
        raise ValueError("User has no current venue set")

    # Equipment at venue
    rows = db.execute(
        """
        SELECT e.name, ve.quantity, e.weight_resistance_time
        FROM Venue_equipment ve
        JOIN equipment e ON e.equipment_id = ve.equipment_id
        WHERE ve.venue_id = %s AND COALESCE(ve.quantity,0) > 0
        """,
        (venue_id,), fetch=True
    ) or []

    names = [r[0] for r in rows]
    equipment_names = set(n.strip() for n in names if n and str(n).strip())

    # Build free-weight availability if you already have this util
    available_weights = {}
    try:
        # Reconstruct minimal records for your existing helper
        free_weight_names = {"Kettlebells", "Dumbbells", "FixedWeightBar", "Mini loop band", "Regular loop band", "Handle band"}
        fw = []
        for n, q, wrt in rows:
            if n in free_weight_names:
                fw.append({"name": n, "quantity": q, "weight_resistance_time": wrt})

            if n == "Regular loop band":
                fw.append({"name": f'Loop bands', "quantity": q, "weight_resistance_time": wrt})
        if fw:
            available_weights = build_available_weights(fw)  # your existing helper
    except NameError:
        # If build_available_weights isn't available here, just skip
        available_weights = {}

    # Convenience labels: "1 Dumbbell"/"2 Dumbbell", "1 Kettlebell"/"2 Kettlebell"
    def add_pair_labels(kind_label: str):
        if kind_label not in available_weights:
            print("Returning...")
            return
        counts = available_weights[kind_label].values()
        print(f"{kind_label} -> {counts}")
        if any(c >= 1 for c in counts):
            equipment_names.add(f"1 {kind_label[:-1]}")  # Dumbbells -> Dumbbell
        if any(c >= 2 for c in counts):
            equipment_names.add(f"1 {kind_label[:-1]}")
            equipment_names.add(f"2 {kind_label[:-1]}")

    add_pair_labels("Dumbbells")
    add_pair_labels("Kettlebells")
    add_pair_labels("Loop bands")
    equipment_names.add("None")  # always allow bodyweight
    # print(x.lower() for x in equipment_names)
    return {
        "venue_id": venue_id,
        "equipment_names": {x.lower() for x in equipment_names},
        "available_weights": available_weights,  # {"Dumbbells": {"10":2, ...}, "Kettlebells": {...}}
    }


def _has_free_weight(req_l: str, aw: dict) -> bool:
    """
    Interpret common free-weight tokens.
    Accepts either generic plural or explicit counts.
    """
    def has_pairs(kind: str, need_two: bool) -> bool:
        bucket = aw.get(kind, {}) or {}
        return any(cnt >= (2 if need_two else 1) for cnt in bucket.values())

    # Normalize a few common spellings
    r = req_l.strip()
    if r in {"dumbbell", "1 dumbbell"}:
        return has_pairs("Dumbbells", False)
    if r == "2 dumbbell":
        return has_pairs("Dumbbells", True)
    if r in {"kettlebell", "1 kettlebell"}:
        return has_pairs("Kettlebells", False)
    if r == "2 kettlebell":
        return has_pairs("Kettlebells", True)
    if r == "dumbbells":
        return has_pairs("Dumbbells", False) or has_pairs("Dumbbells", True)
    if r == "kettlebells":
        return has_pairs("Kettlebells", False) or has_pairs("Kettlebells", True)
    return False


def _get_exercise_equipment_raw(db, exercise_id: int = None, exercise_name: str = None):
    if exercise_id is not None:
        r = db.execute("SELECT name, equipment FROM Exercises WHERE exercise_id = %s", (exercise_id,), fetch=True)
    else:
        r = db.execute("SELECT name, equipment FROM Exercises WHERE name = %s LIMIT 1", (exercise_name,), fetch=True)
    if not r:
        raise ValueError("Exercise not found")
    ex_name, eq_raw = r[0]
    return ex_name, eq_raw


def _canonicalize_equipment_lookup_name(token: str) -> str | None:
    """
    Map a missing token to a canonical equipment.name for ID lookup.
    Examples:
      "1 Dumbbell" -> "dumbbells"
      "2 Kettlebell" -> "kettlebells"
      "1 Single grip handle" -> "single grip handle"
    Returns lowercase, or None for empty/None/"none".
    """
    if not token:
        return None
    t = token.strip().lower()
    if not t or t == "none":
        return None

    # Free-weight families → canonical base names
    if t in {"dumbbell", "1 dumbbell", "2 dumbbell", "dumbbells"}:
        return "dumbbells"
    if t in {"kettlebell", "1 kettlebell", "2 kettlebell", "kettlebells"}:
        return "kettlebells"
    if t in {"1 loop band", "2 loop band"}:
        return "regular loop band"

    # Strip leading count like "1 " / "2 " for named attachments, e.g. "1
    # single grip handle"
    parts = t.split(" ", 1)
    if parts and parts[0] in {"1", "2"} and len(parts) == 2:
        return parts[1].strip()

    return t


def _map_missing_to_equipment_ids(db, missing_tokens: list[str]) -> list[int | None]:
    """
    Resolve equipment IDs for each missing token (case-insensitive).
    Parallel output to input; returns None where no match is found.
    """
    lookup_names = []
    for tok in missing_tokens:
        cname = _canonicalize_equipment_lookup_name(tok)
        lookup_names.append(cname)

    names_set = sorted({n for n in lookup_names if n})
    name_to_id: dict[str, int] = {}

    if names_set:
        rows = db.execute(
            """
            SELECT equipment_id, name
            FROM equipment
            WHERE LOWER(name) = ANY(%s)
            """,
            (names_set,), fetch=True
        ) or []
        print(names_set, rows)
        for eq_id, eq_name in rows:
            print(eq_id, eq_name)
            if eq_name:
                name_to_id[eq_name.strip().lower()] = eq_id

    out: list[int | None] = []
    # for key in name_to_id:
    #     out.append(name_to_id[key])
    for cname in lookup_names:
        out.append(None if cname is None else name_to_id.get(cname))
    return out


def check_user_equipment_for_exercise(
    db,
    user_id: int,
    exercise_id: int = None,
    exercise_name: str = None
):
    """
    Always returns:
        (has_all: bool, missing: list[str], missing_ids: list[int|None])

    Semantics:
      - Supports AND and OR-of-AND groups from _parse_equipment_spec().
      - Empty requirements or any group containing 'None' → (True, [], []).
      - If no OR-group is fully satisfied, returns the *closest* group’s
        missing items (fewest missing; tie-break by group length, then index).
    """
    ex_name, eq_raw = _get_exercise_equipment_raw(db, exercise_id, exercise_name)
    groups = _parse_equipment_spec(eq_raw)
    ctx = _get_user_equipment_context(db, user_id)
    # print("ctx: ", ctx['equipment_names'])
    user_names = ctx["equipment_names"]     # lowercase set of venue equipment names
    aw = ctx["available_weights"]

    # No requirements → pass
    if not groups:
        return True, [], []

    # Bodyweight anywhere → pass
    for g in groups:
        if any((s or "").strip().lower() == "none" for s in g):
            return True, [], []

    def has_item(token: str) -> bool:
        t = (token or "").strip().lower()
        if not t:
            return True
        # Free-weight smart check (1/2 Dumbbell/Kettlebell, plurals, etc.)
        if _has_free_weight(t, aw):
            return True
        # Direct venue-equipment name match
        return t in user_names

    # Evaluate each OR-group; collect missing per group with metadata
    misses: list[tuple[list[str], int, int]] = []  # (missing_list, group_len, index)
    for idx, group in enumerate(groups):
        missing = [tok for tok in group if not has_item(tok)]
        if not missing:
            # This group satisfied → overall pass
            return True, [], []
        misses.append((missing, len(group), idx))

    # Choose the "best" missing list: fewest missing; then shorter group; then earliest
    best_missing, _, _ = min(misses, key=lambda t: (len(t[0]), t[1], t[2]))

    # Map missing names to equipment IDs
    best_missing_ids = _map_missing_to_equipment_ids(db, best_missing)

    return False, best_missing, best_missing_ids