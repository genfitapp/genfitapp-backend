import json
from pathlib import Path
from database import Database
from decimal import Decimal
from random import randint, uniform
from datetime import date, timedelta
from store import EQUIPMENT_LIST


def to_list(value):
    return value if isinstance(value, list) else [value]

def populate_exercise_table(drop=True):
    db = Database()

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


def create_and_populate_workout_for_user(user_id=2, num_exercises=5, workout_date=None):
    db = Database()

    if workout_date is None:
        workout_date = date.today()

    # Ensure user exists
    user_check = db.execute("SELECT user_id FROM Users WHERE user_id = %s", (user_id,), fetch=True)
    if not user_check:
        db.execute(
            """
            INSERT INTO Users (user_id, name, password, email, birthday, gender, level, workout_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, f"John Doe", "hashed_password", f"user{user_id}@example.com", date(2000, 3, 11), "Male", 1, 0)
        )

    # Create workout with specified date
    workout_id = db.execute(
        """
        INSERT INTO workouts (user_id, date, phase, split_group)
        VALUES (%s, %s, %s, %s)
        RETURNING workout_id
        """,
        (user_id, workout_date, "Strength", "Push"),
        fetch=True
    )[0][0]

    # Suggested workout
    suggested_id = db.execute(
        """
        INSERT INTO suggested_workouts (workout_id, duration_predicted)
        VALUES (%s, %s)
        RETURNING suggested_workout_id
        """,
        (workout_id, randint(45, 70)),
        fetch=True
    )[0][0]

    # Actual workout
    actual_id = db.execute(
        """
        INSERT INTO actual_workout (workout_id, duration_actual)
        VALUES (%s, %s)
        RETURNING actual_workout_id
        """,
        (workout_id, randint(50, 75)),
        fetch=True
    )[0][0]

    # Get random exercise IDs
    exercise_rows = db.execute(
        "SELECT exercise_id FROM Exercises ORDER BY RANDOM() LIMIT %s",
        (num_exercises,),
        fetch=True
    )
    exercise_ids = [row[0] for row in exercise_rows]

    # Suggested + actual records
    for i, ex_id in enumerate(exercise_ids):
        reps = [randint(8, 12) for _ in range(3)]
        sets = [1] * len(reps)
        weight = [Decimal(round(uniform(25, 100), 1)) for _ in reps]
        time = randint(30, 90)

        db.execute(
            """
            INSERT INTO suggested_exercise_records (
                suggested_workout_id, exercise_id, weight, reps, sets, time, order_index
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (suggested_id, ex_id, weight, reps, sets, time, i)
        )

    for i, ex_id in enumerate(exercise_ids):
        reps = [randint(6, 12) for _ in range(4)]
        sets = [1] * len(reps)
        weight = [Decimal(round(uniform(27.5, 110), 1)) for _ in reps]
        time = [randint(30, 90) * len(reps)]

        db.execute(
            """
            INSERT INTO actual_exercise_records (
                actual_workout_id, exercise_id, weight, reps, sets, time, order_index
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (actual_id, ex_id, weight, reps, sets, time, i)
        )


def generate_two_weeks_of_workouts(user_id=2):
    today = date.today()
    
    # Go back 2 weeks from today (start of the week)
    start_of_last_week = today - timedelta(days=today.weekday() + 7)

    # 5 workouts two weeks ago: Mon to Fri
    for i in range(5):
        workout_day = start_of_last_week + timedelta(days=i)
        create_and_populate_workout_for_user(user_id=user_id, num_exercises=5, workout_date=workout_day)
    
    # 4 workouts this week: Mon to Thu
    start_of_this_week = today - timedelta(days=today.weekday())
    for i in range(4):
        workout_day = start_of_this_week + timedelta(days=i)
        create_and_populate_workout_for_user(user_id=user_id, num_exercises=5, workout_date=workout_day)


def populate_user_and_venue(user_id=2):
    db = Database()

    # Step 1: Create user (if not exists)
    user_check = db.execute("SELECT user_id FROM Users WHERE user_id = %s", (user_id,), fetch=True)
    if not user_check:
        db.execute(
            """
            INSERT INTO Users (user_id, name, password, email, birthday, gender, level, workout_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, f"John Doe", "hashed_password", f"ouattarabilly33@hotmail.com", date(2000, 3, 11), "Male", 1, 0)
        )
        print(f"✅ Inserted user_id {user_id}")
    else:
        print(f"✅ user_id {user_id} already exists")

    # Step 2: Create a venue
    venue_id = db.execute(
        """
        INSERT INTO Venues (
            name, user_id, gym_setup, goals, priority_muscles, pain_points,
            split, days_of_week, workout_frequency, time_per_workout, rest_time_between_set
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING venue_id
        """,
        (
            f"{f'User{user_id}'}'s Home Gym",
            user_id,
            1,
            ['Build muscles', 'Get lean'],
            ['Chest', 'Back'],
            ['Shoulder Pain'],
            'Push-Pull-Legs',
            ['Monday', 'Wednesday', 'Friday'],
            3,
            60,
            90
        ),
        fetch=True
    )[0][0]
    print(f"✅ Created venue_id {venue_id}")

    # Step 3: Update user with current_venue_id
    db.execute(
        "UPDATE Users SET current_venue_id = %s WHERE user_id = %s",
        (venue_id, user_id)
    )
    print(f"✅ Linked user_id {user_id} to venue_id {venue_id}")

    # Step 4: Populate Venue_equipment using EQUIPMENT_LIST
    equipment_rows = db.execute("SELECT equipment_id, name FROM equipment", fetch=True)
    for eq_id, name in equipment_rows[:5]:  # Just attach 5 sample items
        db.execute(
            """
            INSERT INTO Venue_equipment (venue_id, equipment_id, quantity)
            VALUES (%s, %s, %s)
            """,
            (venue_id, eq_id, randint(1, 3))
        )
    print("✅ Sample equipment linked to venue.")

# Run it
populate_exercise_table(drop=True)
# populate_user_and_venue(user_id=100)
# generate_two_weeks_of_workouts(user_id=100)