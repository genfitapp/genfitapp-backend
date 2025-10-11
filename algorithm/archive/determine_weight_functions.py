#THIS ISM MY FIRST VERSION

def determine_weight(row, user_id, user_level, records, filtered_dataset, training_phase, user_available_weights, user_equipment):
    """
    Determines weight based on user history or estimates using experience multipliers.

    Parameters:
    - row (Series): Row of the DataFrame containing exercise details.
    - user_id (str): Unique user ID.
    - user_level (str): User's experience level.
    - records (dict): Dictionary storing past lift records.
    - filtered_dataset (DataFrame): exercise dataset.
    - training_phase (str): User's current training phase.
    - user_available_weights (dictionary): Dictionary containing keys (i.e. "Dumbbells") and subkey:value pairs?

    Returns:
    - dict: {"weight": suggested_weight, "reps": suggested_reps}
    """

    #TODO: Modify the names of the attributes, so they don't look that weird
    #"Lower bound (lbs/resistance/time) to Lower bound"
    #"Equipment Type (Gym:0, Body:1, Band:2) to Equipment Type"
    exercise_name = row["Exercise"]
    min_weight = row["Lower bound (lbs/resistance/time)"]
    exercise_type = infer_equipment_type(min_weight)
    exercise_equipment = row["Equipment Type (Gym:0, Body:1, Band:2)"]
    #TODO: We don't know exactly due to which "subset" this pass the filtering. We might need to overwrite "row["Equipment Type (Gym:0, Body:1, Band:2)"]" with the specifid subset
    # OR find all the subsets that are part of the options, and determine which one the user actually has

    #MIGHT NEED TO CHANGE THE WAY WE ACCESS RECORDS. HOW ARE WE GONNA STORE THEM?

    # If user has past records, apply progressive overload
    # if user_id in records and exercise_name in records[user_id]["by_exercise"]:

    #NOTE: THE FOLLOWING LINE RETURNS BOOLEAN
    if records.get(user_id) and exercise_name in records[user_id]["by_exercise"]:
        # Filter records specific to the current training phase
        exercise_records = records[user_id]["by_exercise"][exercise_name]

        if exercise_type == "Gym Equipment":
            suggested_results = weight_algorithm(exercise_records, training_phase)
        elif exercise_type == "Resistance Band":
            suggested_results = band_algorithm(exercise_records, training_phase)
        elif exercise_type == "Bodyweight":
            return bodyweight_algorithm(exercise_records, training_phase)
        elif exercise_type == "Timed Exercise":
            return timed_algorithm(exercise_records)

        suggested_weight = suggested_results["weight"]
        suggested_reps = suggested_results["reps"]
        equipment_info = find_specific_equipment(exercise_equipment)

        if equipment_info:
            #i.e. Dumbbell, 2
            equipment_type, quantity_needed = equipment_info

            skip_validation = (
                equipment_type == "Fixed weight bar" and 
                any(e in user_equipment for e in ["Olympic barbell", "EZ curl bar"])
            )

            if not skip_validation: 
                user_has_weight = user_available_weights.get(equipment_type, {}).get(suggested_weight, 0)
                
                if user_has_weight < quantity_needed:
                    print(f"⚠️ Adjusting weight: {suggested_weight} lbs not available!")
                    ####NEED TO WORK ON THIS FUNCTION!!!
                    suggested_weight = find_closest_available_weight(suggested_weight, equipment_type, user_available_weights, quantity_needed)

        return {"weight": suggested_weight, "reps": suggested_reps}


        
    # No previous records for this exercise? Check similar exercises
    if exercise_type == "Gym Equipment":
        similar_exercise = find_similar_exercise(exercise_name, records, user_id, filtered_dataset)
        if similar_exercise:
            similar_records = records[user_id]["by_exercise"][similar_exercise]
            print("About to call muscle_algorithm()...")
            suggested_results = muscle_algorithm(similar_records) 
            suggested_weight = suggested_results["weight"]
            suggested_reps = suggested_results["reps"]

        else:
            # No record or similar exercise? Estimate starting weight
            # #if NOT similar exercise for Gym equipment
            suggested_weight = min_weight * experience_multiplier[user_level]
            suggested_weight = round_gym_weight(suggested_weight)
            suggested_reps = 10
         
        equipment_info = find_specific_equipment(exercise_equipment)
        if equipment_info:
            #i.e. Dumbbell, 2
            equipment_type, quantity_needed = equipment_info

            skip_validation = (
                equipment_type == "Fixed weight bar" and 
                any(e in user_equipment for e in ["Olympic barbell", "EZ curl bar"])
            )

            if not skip_validation: 
                user_has_weight = user_available_weights.get(equipment_type, {}).get(suggested_weight, 0)
                
                if user_has_weight < quantity_needed:
                    print(f"⚠️ Adjusting weight: {suggested_weight} lbs not available!")
                    ####NEED TO WORK ON THIS FUNCTION!!!
                    suggested_weight = find_closest_available_weight(suggested_weight, equipment_type, user_available_weights, quantity_needed)
                    
        return {"weight": suggested_weight, "reps": suggested_reps}
    
    if exercise_type == "Resistance Band":
        suggested_weight = min_weight
        suggested_reps = 10

        equipment_info = find_specific_equipment(exercise_equipment)
        if equipment_info:
            #i.e. 2 Loop Band
            equipment_type, quantity_needed = equipment_info

            skip_validation = (
                equipment_type == "Fixed weight bar" and 
                any(e in user_equipment for e in ["Olympic barbell", "EZ curl bar"])
            )

            if not skip_validation:
                user_has_weight = user_available_weights.get(equipment_type, {}).get(suggested_weight, 0)
                
                if user_has_weight < quantity_needed:
                    print(f"⚠️ Adjusting weight: {suggested_weight} lbs not available!")
                    ####NEED TO WORK ON THIS FUNCTION!!!
                    suggested_weight = find_closest_available_resistance(suggested_weight, equipment_type, user_available_weights, quantity_needed)

        return {"weight": suggested_weight, "reps": suggested_reps}

    #return min_weight  # Keep unchanged for bodyweight, and timed exercises
    #print("I am here 3")
    return {"weight": min_weight, "reps": 10}











#THIS IS THE FIRST CHATGPT CREATED VERSION

def new_determine_weight(row, user_id, user_level, records, filtered_dataset, training_phase, user_available_weights, user_equipment):
    """
    Determines weight based on user history, equipment availability, or estimates.

    Returns:
    - dict: {"weight": suggested_weight, "reps": suggested_reps}
    """

    exercise_name = row["Exercise"]
    min_weight = row["Lower bound (lbs/resistance/time)"]
    exercise_type = infer_equipment_type(min_weight)
    exercise_equipment = row["Equipment Type (Gym:0, Body:1, Band:2)"]

    suggested_weight = None
    suggested_reps = None

    # Check if user has records for this exercise
    #NOTE: THE FOLLOWING LINE SAVES THE VALUES 
    exercise_records = records.get(user_id, {}).get("by_exercise", {}).get(exercise_name)

    # === 🧠 Use algorithm based on type ===
    if exercise_records:
        if exercise_type == "Gym Equipment":
            suggested_results = weight_algorithm(exercise_records, training_phase)
        elif exercise_type == "Resistance Band":
            suggested_results = band_algorithm(exercise_records, training_phase)
        elif exercise_type == "Bodyweight":
            return bodyweight_algorithm(exercise_records, training_phase)
        elif exercise_type == "Timed Exercise":
            return timed_algorithm(exercise_records)
        suggested_weight = suggested_results["weight"]
        suggested_reps = suggested_results["reps"]

    # === 🧠 If no records, try similar exercise ===
    elif exercise_type == "Gym Equipment":
        similar_exercise = find_similar_exercise(exercise_name, records, user_id, filtered_dataset)
        if similar_exercise:
            similar_records = records[user_id]["by_exercise"][similar_exercise]
            suggested_results = muscle_algorithm(similar_records)
            suggested_weight = suggested_results["weight"]
            suggested_reps = suggested_results["reps"]
        else:
            suggested_weight = round_gym_weight(min_weight * experience_multiplier[user_level])
            suggested_reps = 10

    # === 🧠 If Resistance Band with no history ===
    elif exercise_type == "Resistance Band":
        suggested_weight = min_weight
        suggested_reps = 10

    # === ✅ Equipment availability check (if needed) ===
    if exercise_type in ["Gym Equipment", "Resistance Band"]:
        equipment_info = find_specific_equipment(exercise_equipment)
        if equipment_info:
            equipment_type, quantity_needed = equipment_info

            skip_validation = (
                equipment_type == "Fixed weight bar" and 
                any(e in user_equipment for e in ["Olympic barbell", "EZ curl bar"])
            )

            if not skip_validation: 
                user_has_weight = user_available_weights.get(equipment_type, {}).get(suggested_weight, 0)

                if user_has_weight < quantity_needed:
                    print(f"⚠️ Adjusting weight: {suggested_weight} not available!")
                    if exercise_type == "Resistance Band":
                        suggested_weight = find_closest_available_resistance(
                            suggested_weight, equipment_type, user_available_weights, quantity_needed
                        )
                    else:
                        suggested_weight = find_closest_available_weight(
                            suggested_weight, equipment_type, user_available_weights, quantity_needed
                        )

    # === 🧠 If still no match (e.g., Timed/Bodyweight or fallback) ===
    if suggested_weight is None or suggested_reps is None:
        suggested_weight = min_weight
        suggested_reps = 10

    return {"weight": suggested_weight, "reps": suggested_reps}







#THIS IS MY CURRENT WORKING VERSION BEFORE REFACTOR

def determine_weight(row, user_id, user_level, records, filtered_dataset, training_phase, user_available_weights, user_equipment):
    """
    Determines weight based on user history or estimates using experience multipliers.

    Parameters:
    - row (Series): Row of the DataFrame containing exercise details.
    - user_id (str): Unique user ID.
    - user_level (str): User's experience level.
    - records (dict): Dictionary storing past lift records.
    - filtered_dataset (DataFrame): exercise dataset.
    - training_phase (str): User's current training phase.
    - user_available_weights (dictionary): Dictionary containing keys (i.e. "Dumbbells") and subkey:value pairs?

    Returns:
    - dict: {"weight": suggested_weight, "reps": suggested_reps}
    """

    #TODO: Modify the names of the attributes, so they don't look that weird
    #"Lower bound (lbs/resistance/time) to Lower bound"
    #"Equipment Type (Gym:0, Body:1, Band:2) to Equipment Type"
    exercise_name = row["Exercise"]
    min_weight = row["Lower bound (lbs/resistance/time)"]
    exercise_type = infer_equipment_type(min_weight)
    exercise_equipment = row["Equipment"]
    print("printing equipment", row["Equipment"])
    #TODO: We don't know exactly due to which "subset" this pass the filtering. We might need to overwrite "row["Equipment Type (Gym:0, Body:1, Band:2)"]" with the specifid subset
    # OR find all the subsets that are part of the options, and determine which one the user actually has

    #MIGHT NEED TO CHANGE THE WAY WE ACCESS RECORDS. HOW ARE WE GONNA STORE THEM?

    # If user has past records, apply progressive overload
    # if user_id in records and exercise_name in records[user_id]["by_exercise"]:

    #NOTE: THE FOLLOWING LINE RETURNS BOOLEAN
    if records.get(user_id) and exercise_name in records[user_id]["by_exercise"]:
        # Filter records specific to the current training phase (done in weight_algorithm, etc)
        exercise_records = records[user_id]["by_exercise"][exercise_name]

        if exercise_type == "Gym Equipment":
            #NOTE: Weight_algorithm calls Brzycki and Epley formulas, which expect TOTAL values
            #Exercise_records should be saved as total weights
            suggested_results = weight_algorithm(exercise_records, training_phase)
            print("Calling weight algorithm with records")
        elif exercise_type == "Resistance Band":
            suggested_results = band_algorithm(exercise_records, training_phase)
            print("Calling band algorithm with records")
        elif exercise_type == "Bodyweight":
            print("Calling bodyweight algorithm with records")
            return bodyweight_algorithm(exercise_records, training_phase)
        elif exercise_type == "Timed Exercise":
            print("Calling timed algorithm with records")
            return timed_algorithm(exercise_records)

        suggested_weight = suggested_results["weight"]
        suggested_reps = suggested_results["reps"]
        equipment_info = find_specific_equipment(exercise_equipment)
        print("printing equipment info: ", equipment_info)

        if equipment_info:
            #i.e. Dumbbell, 2
            print("inside equipment_info statement")
            equipment_type, quantity_needed = equipment_info

            skip_validation = (
                equipment_type == "Fixed weight bar" and 
                any(e in user_equipment for e in ["Olympic barbell", "EZ curl bar"])
            )

            if not skip_validation: 
                single_weight = suggested_weight
                if equipment_type in ["Dumbbells", "Kettlebells"] and quantity_needed == 2:
                    single_weight = suggested_weight / 2
                    user_has_weight = user_available_weights.get(equipment_type, {}).get(single_weight, 0)
                else:
                    user_has_weight = user_available_weights.get(equipment_type, {}).get(suggested_weight, 0)

                if user_has_weight < quantity_needed:
                    print(f"⚠️ Adjusting weight: {single_weight} not available!")
                    ####NEED TO WORK ON THIS FUNCTION!!!
                    if exercise_type == "Gym Equipment":
                        suggested_weight = find_closest_available_weight(suggested_weight, equipment_type, user_available_weights, quantity_needed)
                    elif exercise_type == "Resistance Band":
                        suggested_weight = find_closest_available_resistance(suggested_weight, equipment_type, user_available_weights, quantity_needed)

        return {"weight": suggested_weight, "reps": suggested_reps}


    # No previous records for this exercise? Check similar exercises
    if exercise_type == "Gym Equipment":
        equipment_info = find_specific_equipment(exercise_equipment)
        quantity_needed = 1
        if equipment_info:
                #i.e. Dumbbell, 2
                print("Special case: equipment info")
                equipment_type, quantity_needed = equipment_info
        
        similar_exercise = find_similar_exercise(exercise_name, records, user_id, filtered_dataset)
        if similar_exercise:
            similar_records = records[user_id]["by_exercise"][similar_exercise]
            print("About to call muscle_algorithm()...")
                
            suggested_results = muscle_algorithm(similar_records, quantity_needed) 
            suggested_weight = suggested_results["weight"]
            suggested_reps = suggested_results["reps"]

        else:
            # No similar exercise? Estimate starting weight
            # #if NOT similar exercise for Gym equipment
            print("Estimating starting weight based on experience multiplier...")
            #TODO:Here, min_weight is for a SINGLE DUMBBELL
            suggested_weight = min_weight * quantity_needed * experience_multiplier[user_level]
            suggested_weight = round_gym_weight(suggested_weight, quantity_needed > 1)
            suggested_reps = 10
         

        skip_validation = (
            equipment_type == "Fixed weight bar" and 
            any(e in user_equipment for e in ["Olympic barbell", "EZ curl bar"])
        )
        
        if not skip_validation: 
            single_weight = suggested_weight
            if equipment_type in ["Dumbbells", "Kettlebells"] and quantity_needed == 2:
                single_weight = suggested_weight / 2
                user_has_weight = user_available_weights.get(equipment_type, {}).get(single_weight, 0)
            else:
                user_has_weight = user_available_weights.get(equipment_type, {}).get(suggested_weight, 0)

            if user_has_weight < quantity_needed:
                print(f"⚠️ Adjusting weight: {single_weight} lbs not available!")
                suggested_weight = find_closest_available_weight(suggested_weight, equipment_type, user_available_weights, quantity_needed)


        return {"weight": suggested_weight, "reps": suggested_reps}
    
    if exercise_type == "Resistance Band":
        suggested_weight = min_weight
        suggested_reps = 10

        equipment_info = find_specific_equipment(exercise_equipment)
        if equipment_info:
            #i.e. 2 Loop Band
            equipment_type, quantity_needed = equipment_info

            # skip_validation = (
            #     equipment_type == "Fixed weight bar" and 
            #     any(e in user_equipment for e in ["Olympic barbell", "EZ curl bar"])
            # )

            # if not skip_validation:
            user_has_weight = user_available_weights.get(equipment_type, {}).get(suggested_weight, 0)
                
            if user_has_weight < quantity_needed:
                print(f"⚠️ Adjusting resistance: {suggested_weight} not available!")
                ####NEED TO WORK ON THIS FUNCTION!!!
                suggested_weight = find_closest_available_resistance(suggested_weight, equipment_type, user_available_weights, quantity_needed)

        return {"weight": suggested_weight, "reps": suggested_reps}
    
    if exercise_type == "Timed Exercise":
        print("No record timed exercise...")
        return {"weight": None, "reps": None, "time": min_weight}
    
    #return min_weight, keep unchanged for bodyweight
    print("no record bodyweight exerxise")
    return {"weight": min_weight, "reps": 10, "time": None}

