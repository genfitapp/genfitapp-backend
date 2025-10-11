DATABASE_INIT_COMMANDS = [
    # Create Users table
    '''
    CREATE TABLE IF NOT EXISTS Users (
        user_id SERIAL PRIMARY KEY,
        name VARCHAR(255),
        password TEXT,
        current_venue_id INT,
        birthday DATE,
        gender VARCHAR(10),
        level INT,
        email VARCHAR(255),
        picture VARCHAR(255),
        workout_number INT,
        agreed BOOLEAN DEFAULT FALSE  -- tracks if user agreed to terms/privacy
    );
    ''',
    # Create Venues table
    '''
    CREATE TABLE IF NOT EXISTS Venues (
        venue_id SERIAL PRIMARY KEY,
        name VARCHAR(255),
        user_id INT REFERENCES Users(user_id),
        gym_setup INT,
        goals TEXT[],
        priority_muscles TEXT[],
        pain_points TEXT[],
        split VARCHAR(100),
        days_of_week TEXT[],
        workout_frequency INT,
        time_per_workout INT,
        rest_time_between_set INT
    );
    ''',
    # Create workouts table (for actual workouts)
    '''
    CREATE TABLE IF NOT EXISTS workouts (
        workout_id SERIAL PRIMARY KEY,
        user_id INT REFERENCES Users(user_id),
        date DATE,
        phase VARCHAR(50),
        split_group VARCHAR(50)
    );
    ''',
    # Create suggested_workouts table
    '''
    CREATE TABLE IF NOT EXISTS suggested_workouts (
        suggested_workout_id SERIAL PRIMARY KEY,
        workout_id INT REFERENCES workouts(workout_id),
        duration_predicted INT
    );
    ''',
    # Create Exercises table
    '''
    CREATE TABLE IF NOT EXISTS Exercises (
        exercise_id SERIAL PRIMARY KEY,
        name VARCHAR(255),
        main_muscles TEXT[],
        secondary_muscles TEXT[],
        animation TEXT,
        written_instructions TEXT,
        movement VARCHAR(255),
        lower_bound TEXT,
        level TEXT[],
        difficulty INT,
        equipment_type INT,
        equipment TEXT[],
        prerequisite_exercise TEXT[],
        variations TEXT[],
        regression TEXT[],
        progression TEXT[],
        loading_type INT,
        risk_level INT,
        exercise_purpose TEXT[],
        force_type TEXT[],
        pain_exclusions TEXT[]
    );
    ''',
    # Create suggested_exercise_records table
    '''
    CREATE TABLE IF NOT EXISTS suggested_exercise_records (
        suggested_record_id SERIAL PRIMARY KEY,
        suggested_workout_id INT REFERENCES suggested_workouts(suggested_workout_id),
        exercise_id INT REFERENCES Exercises(exercise_id),
        exercise_type VARCHAR(50),
        intensity TEXT[],
        reps INT[],
        sets INT[],
        time INT[],
        order_index INT
    );
    ''',
    # Create equipment table - deleted:         weight_resistance_time VARCHAR(50)
    '''
    CREATE TABLE IF NOT EXISTS equipment (
        equipment_id SERIAL PRIMARY KEY,
        name VARCHAR(255),
        weight_resistance_time VARCHAR(50)
    );
    ''',
    # Create Venue_equipment table
    '''
    CREATE TABLE IF NOT EXISTS Venue_equipment (
        venue_equipment_id SERIAL PRIMARY KEY,
        venue_id INT REFERENCES Venues(venue_id),
        equipment_id INT REFERENCES equipment(equipment_id),
        quantity INT
    );
    ''',
    # Create exercise_preferences
    '''
    CREATE TABLE IF NOT EXISTS exercise_preferences (
        preference_id SERIAL PRIMARY KEY,
        user_id INT REFERENCES Users(user_id),
        exercise_id INT REFERENCES Exercises(exercise_id),
        preference INT CHECK (preference IN (1, 2, 3)),
        UNIQUE(user_id, exercise_id)
    );
    ''',
    # Create actual_workout table
    '''
    CREATE TABLE IF NOT EXISTS actual_workout (
        actual_workout_id SERIAL PRIMARY KEY,
        workout_id INT REFERENCES workouts(workout_id),
        duration_actual INT
    );
    ''',
    # Create actual_exercise_records table
    # CREATE TABLE IF NOT EXISTS actual_exercise_records (
    #     actual_record_id SERIAL PRIMARY KEY,
    #     actual_workout_id INT REFERENCES actual_workout(actual_workout_id),
    #     exercise_id INT REFERENCES Exercises(exercise_id),
    #     weight DECIMAL[],
    #     reps INT[],
    #     sets INT[],
    #     time INT[],
    #     order_index INT
    # );
    '''
    CREATE TABLE IF NOT EXISTS actual_exercise_records (
        actual_record_id SERIAL PRIMARY KEY,
        actual_workout_id INT REFERENCES actual_workout(actual_workout_id),
        exercise_id INT REFERENCES Exercises(exercise_id),
        exercise_type VARCHAR(50),
        intensity TEXT[],
        reps INT[],
        sets INT[],
        time INT[],
        order_index INT
    );
    ''',
    # Create Milestones table
    '''
    CREATE TABLE IF NOT EXISTS Milestones (
        milestone_id SERIAL PRIMARY KEY,
        user_id INT REFERENCES Users(user_id),
        milestone_type VARCHAR(50),
        description TEXT,
        exercise_id INT REFERENCES Exercises(exercise_id),
        target_value DECIMAL,
        unit VARCHAR(50),
        achieved_date DATE,
        status VARCHAR(50)
    );
    ''',
    # This is for resetting password when user forgot their passwords
    # This was added recently
    '''
    CREATE TABLE IF NOT EXISTS password_resets (
        reset_id SERIAL PRIMARY KEY,
        user_id INT REFERENCES Users(user_id),
        token_hash TEXT NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,   -- aware UTC instant
        used_at TIMESTAMPTZ,               -- when token was consumed
        created_ip VARCHAR(64),
        UNIQUE (token_hash)
    );
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_providers (
        user_provider_id SERIAL PRIMARY KEY,
        user_id INT REFERENCES Users(user_id) ON DELETE CASCADE,
        provider VARCHAR(20) NOT NULL,          -- 'google', 'apple', etc.
        provider_user_id VARCHAR(128) NOT NULL, -- Google's 'sub', Apple's 'sub'
        UNIQUE (provider, provider_user_id)
    );
    ''',


]