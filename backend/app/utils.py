import json
from pathlib import Path
import psycopg2
from database.store import EQUIPMENT_LIST


def to_list(value):
    return value if isinstance(value, list) else [value]

def populate_exercise_table(db, drop=True):
    # db = Database()
    if drop:
        DROP_TABLE_COMMANDS = [
            "DROP TABLE IF EXISTS Milestones CASCADE;",
            "DROP TABLE IF EXISTS actual_exercise_records CASCADE;",
            "DROP TABLE IF EXISTS actual_workout CASCADE;",
            "DROP TABLE IF EXISTS Venue_equipment CASCADE;",
            "DROP TABLE IF EXISTS equipment CASCADE;",
            "DROP TABLE IF EXISTS suggested_exercise_records CASCADE;",
            "DROP TABLE IF EXISTS Exercises CASCADE;",
            "DROP TABLE IF EXISTS suggested_workouts CASCADE;",
            "DROP TABLE IF EXISTS workouts CASCADE;",
            "DROP TABLE IF EXISTS Venues CASCADE;",
            "DROP TABLE IF EXISTS Users CASCADE;",
            "DROP TABLE IF EXISTS exercise_preferences CASCADE;",
        ]

        # This is for pure initialization(First time). Might have to remove the
        # line below
        for command in DROP_TABLE_COMMANDS:
            db.execute(command)


    try:
        db.initialiaze_database()
    except psycopg2.errors.DuplicateTable:
        print("Table already exists — skipping creation.")

    # Adjust path as needed depending on where your JSON file is
    json_path = Path(__file__).resolve().parent.parent.parent / 'algorithm' / 'dataset_7.json'

    with open(json_path, 'r') as file:
        json_data = json.load(file)

    insert_query = """
    INSERT INTO Exercises (
        name,
        main_muscles,
        secondary_muscles,
        animation,
        written_instructions,
        movement,
        lower_bound,
        level,
        difficulty,
        equipment_type,
        equipment,
        prerequisite_exercise,
        variations,
        regression,
        progression,
        loading_type,
        risk_level,
        exercise_purpose,
        force_type,
        pain_exclusions
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """


    for exercise in json_data:
        anim = exercise.get("Animation name")

        # Skip if Animation name is None, empty string, whitespace only, or NA
        # TODO: Once we have all videos we should remove this condition to keep
        # all exercises.
        if not anim or str(anim).strip() == "" or str(anim).strip().upper() == "NA":
            print("Skipping: ", exercise.get('Exercise'), "...")
            continue

        data = [
            exercise.get('Exercise', ''),
            exercise.get('Main muscle(s)', []),
            exercise.get('Secondary muscles', []),
            anim.strip(),
            exercise.get('Exercise Description', ''),
            exercise.get('Movement', ''),
            exercise.get('Lower bound (lbs/resistance/time)', 0),
            to_list(exercise.get("Level")),
            exercise.get('Difficulty', 0),
            exercise.get('Equipment Type (Gym:0, Body:1, Band:2)', 0),
            exercise.get('Equipment'),
            exercise.get('Prerequesite Exercise', []),
            exercise.get('Variations', []),
            exercise.get('Regression', []),
            exercise.get('Progression', []),
            exercise.get('Loading type (Asymmetrical / Symmetrical)'),
            exercise.get('Risk level', 0),
            exercise.get('Exercise Purpose', []),
            exercise.get('Force type (Push, Pull, Rotation, Isomatric)', []),
            exercise.get('Pain Exclusions', [])
        ]

        try:
            db.execute(insert_query, tuple(data))
        except Exception as e:
            print(f"Failed to insert exercise: {exercise.get('Exercise', '')}")
            print(f"Error: {e}")


    # Populating the equipment table
    insert_query = """
        INSERT INTO equipment (name, weight_resistance_time)
        VALUES (%s, %s)
        RETURNING equipment_id;
    """

    for equipment in EQUIPMENT_LIST:
        attributes = equipment.split('_')
        name = " ".join(attributes[:-1]) if len(attributes) > 1 else attributes[0]
        # weight_resistance_time = float(attributes[-1]) if len(attributes) > 1 else ''
        
        if len(attributes) > 1:
            if isinstance(attributes[-1], str):
                val = attributes[-1]
                if 'E' in val:
                    val = 'Extra Light'
                elif 'X' in val:
                    val = 'Extra Heavy'

                weight_resistance_time = val
            else:
                val = float(attributes[-1])
                weight_resistance_time = int(val) if val.is_integer() else val
        else:
            weight_resistance_time = ''


        try:
            # Execute the query with parameters, fetching the new equipment_id
            result = db.execute(insert_query, (name, weight_resistance_time), fetch=True)
            new_id = result[0][0]
            print(f"Inserted '{name}' with equipment_id: {new_id}")
        except Exception as e:
            print(f"Error inserting '{name}':", e)

    print("✅ Exercise table populated successfully.")