from itertools import combinations

# Naive implementation with minimum variables
# days_of_week: array [1-7], where 1: Monday, 2: Tuesday ...
# workout_frequency (1-7)
# time_per_workout: 30 min - 2 hours (30, 45, 60, 75, 90, 105, 120)  

#If wf == 1, Full body split 

    #If wf == 2, full body(f=2) OR Upper/lower(f=1)
        #Full body: Largest difference between days_of_week must be at least 3 for newcomers (2 rest days), can be 2 for begginers + (1 rest day)
        #Else, Upper/lower

    #If wf == 3, full body(f=3) OR Upper lower(f=1.5), PPL(f=1)
         #Upper lower: Appropiate for everyone. At least One largest difference between days_of_week must be 3 (2 days in between)
        #Full body: Largest difference between days_of_week must be 2 (1 day) twice for beginners ++
        #Else: PPL

    #If wf == 4, PHUL (f=2), upper lower(f=2), PPL(f=1.33)
        #PHUL if want 50/50 strengh and muscle AND can do a rest day after 2 workouts
        #Upper/lower if can do a rest day after 2 workout
        #else PPL

    #If wf == 5, [upper lower(f=2.5),  PHUL (f=2.5)]
    #Hybrid PPL + Upper/Lower (f=2), PPL(f=1.66), Body part split(f=1)

    #If wf == 6,  [upper lower(f=3), PHUL (f=3)]
    # PPL(f=2), but 6-day body plat split (f=1) if limited time
     
    #If wf == 7,  [upper lower(f=3), PHUL (f=3)] + active rest
    #PPL(f=2) + active rest

    #days selected MUST BE EQUAL OR LARGER than WORKOUT 

# split_dictionary = {
#     "Upper-lower"    : [["Chest","Shoulders", "Triceps", "Back", "Biceps","Trapezius", "Abs","Obliques", "Lower back"],
#                         ["Quads", "Glutes", "Hamstrings", "Abductors","Adductors","Calves"]],

#     "Push-Pull-Legs" : [["Chest","Shoulders", "Triceps"],
#                         ["Back", "Biceps","Trapezius", "Abs","Obliques"],
#                         ["Quads", "Glutes", "Hamstrings", "Abductors","Adductors","Calves","Lower back"]],

#     "PHUL"           : [["Chest","Shoulders", "Triceps", "Back", "Biceps","Trapezius", "Abs","Obliques", "Lower back"],
#                         ["Quads", "Glutes", "Hamstrings", "Abductors","Adductors","Calves"]],
    
#     "Hybrid PPL+ UL" : [["Chest","Shoulders", "Triceps"],
#                         ["Back", "Biceps","Trapezius", "Abs","Obliques"],
#                         ["Quads", "Glutes", "Hamstrings", "Abductors","Adductors","Calves","Lower back"],
#                         ["Chest","Shoulders", "Triceps", "Back", "Biceps","Trapezius", "Abs","Obliques", "Lower back"],
#                         ["Quads", "Glutes", "Hamstrings", "Abductors","Adductors","Calves"]],

#     "Body part split": [["Chest"],
#                         ["Back","Trapezius"],
#                         ["Quads", "Glutes", "Hamstrings", "Abductors","Adductors","Calves", "Lower back"],
#                         ["Shoulders","Abs","Obliques"],
#                         ["Biceps","Triceps"]],

#     "6-day body parysplit": [["Chest"],
#                         ["Back","Trapezius"],
#                         ["Quads", "Glutes", "Hamstrings", "Abductors","Adductors","Calves"],
#                         ["Abs","Obliques","Lower back"],
#                         ["Shoulders"],
#                         ["Biceps","Triceps"]]
# }


def valid_fullbody_gaps(days):
    #find combinations of three days
    for day1, day2, day3 in combinations(days, 3):
        gap1 = day2 - day1
        gap2 = day3 - day2
        gap3 = (7 - day3) + day1 

        if gap1 >= 2 and gap2 >= 2 and gap3 >= 2:
            return True
    
    return False


def has_valid_gaps(days_of_week):
    
    # Check all combinations of two days
    for day1, day2, day3, day4 in combinations(days_of_week, 4):
        gap1 = day3 - day1  # Direct difference
        gap2 = (7 - day4) + day1  # Wrap-around difference
        
        # Check if both directions respect the minimum difference
        if gap1 >= 3 and gap2 >= 3: 
            return True  # Valid pair found
    
    return False  # No valid pairs found


def has_min_gap(days_of_week, min_difference):

    n = len(days_of_week)

    # Check all combinations of two days
    for day1, day2 in combinations(days_of_week, 2):
        direct_gap = abs(day2 - day1)  # Direct difference
        wrap_around_gap = (7 - max(day1, day2)) + min(day1, day2)  # Wrap-around difference
        
        # Check if both directions respect the minimum difference
        if direct_gap >= min_difference and wrap_around_gap >= min_difference:
            return True  # Valid pair found
    
    return False  # No valid pairs found


def recommend_split (days_of_week, workout_frequency, time_per_workout, level, goals):

    if workout_frequency == 1:
        return 'Full-Body'
    
    if workout_frequency == 2:
        
        if has_min_gap(days_of_week,3) and level == 0:
            return 'Full-Body'
        if has_min_gap(days_of_week,2) and level >= 1:
            return 'Full-Body'
        else:
            return 'Upper-Lower'
        
    if workout_frequency == 3:
  
        if has_min_gap(days_of_week,3) and time_per_workout > 45:
            return 'Upper-Lower'
        if valid_fullbody_gaps(days_of_week) and level >= 1 and time_per_workout <= 45:
            return 'Full-Body'
        else:
            return 'Push-Pull-Legs'
        
    if workout_frequency == 4:
        valid = has_valid_gaps(days_of_week)
        if any(goal in ['Powerlifting', 'Get stronger'] for goal in goals) and any(goal in ['Bodybuilding', "Build Muscles", "Get Lean"] for goal in goals) and valid:
            return 'PHUL'
        if valid:
            return 'Upper-Lower'
        else:
            return 'Push-Pull-Legs'
        
    if workout_frequency == 5: 
        valid = has_valid_gaps(days_of_week)
        if any(goal in ['Powerlifting', 'Get stronger'] for goal in goals) and any(goal in ['Bodybuilding', "Build Muscles", "Get Lean"] for goal in goals):
            return 'Hybrid PPL + Upper/Lower'
        if time_per_workout < 45:
            return 'Body part split'
        else: return 'Push-Pull-Legs'

    if workout_frequency == 6:
        if time_per_workout <= 30:
            return '6-day body pary split'
        return 'Push-Pull-Legs'
    
    
    if workout_frequency == 7:
        return 'Push-Pull-Legs + active rest' 
    
    
# #Case 1: wf:1, full body
# print("1: ", recommend_split(
# days_of_week=[1,2,3,4,5],
# workout_frequency=1,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# # Case 2: wf:2, full body newcomer
# print("2: ", recommend_split(
# days_of_week=[2,6],
# workout_frequency=2,
# time_per_workout=60,
# level=0,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))
    
# # Case 3: wf:2, full body beginner
# print("3: ", recommend_split(
# days_of_week=[1,3],
# workout_frequency=2,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# # Case 4: wf:2, upper-lower
# print("4: ", recommend_split(
# days_of_week=[1,7],
# workout_frequency=2,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# #Case 5: wf:3, upper-lower
# print("5: ", recommend_split(
# days_of_week=[1,2,6,7],
# workout_frequency=3,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# #Case 6: wf:3, Full-body
# print("6: ", recommend_split(
# days_of_week=[1,3,5],
# workout_frequency=3,
# time_per_workout=45,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# #Case 7: wf:3, push-pull-legs
# print("7: ", recommend_split(
# days_of_week=[1,2,3],
# workout_frequency=3,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# #Case 8: wf:4, PHUL
# print("8: ", recommend_split(
# days_of_week=[1,2,4,5],
# workout_frequency=4,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# #Case 9: wf:4, Upper-Lower
# print("9: ", recommend_split(
# days_of_week=[1,2,4,5],
# workout_frequency=4,
# time_per_workout=60,
# level=1,
# goals=[ 'Bodybuilding']
# ))

# #Case 10: wf:4, PPL
# print("10: ", recommend_split(
# days_of_week=[1,2,3,4],
# workout_frequency=4,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# #Case 11: wf:5, hybrid
# print("11: ", recommend_split(
# days_of_week=[1,2,3,5,6],
# workout_frequency=5,
# time_per_workout=60,
# level=1,
# goals=['Powerlifting', 'Get stronger', 'Bodybuilding']
# ))

# #Case 12: wf:5, body pary split
# print("12: ", recommend_split(
# days_of_week=[1,2,3,4,5],
# workout_frequency=5,
# time_per_workout=40,
# level=1,
# goals=['Bodybuilding']
# ))

# #Case 13: wf:5, PPL
# print("13: ", recommend_split(
# days_of_week=[1,2,3,4,5],
# workout_frequency=5,
# time_per_workout=90,
# level=1,
# goals=['Bodybuilding']
# ))


# #Case 14: wf:6, PPL
# print("14: ", recommend_split(
# days_of_week=[1,2,3,4,5,6],
# workout_frequency=6,
# time_per_workout=90,
# level=1,
# goals=['Bodybuilding']
# ))

# #Case 15: wf:7, PPL
# print("15: ", recommend_split(
# days_of_week=[1,2,3,4,5,6],
# workout_frequency=7,
# time_per_workout=90,
# level=1,
# goals=['Bodybuilding']
# ))


#Case 15: wf:7, PPL

# split =recommend_split(
#     days_of_week=[1,2,3,4,5,6],
#     workout_frequency=6,
#     time_per_workout=90,
#     level=1,
#     goals=['Bodybuilding']
#     )

# print(split)
# print(split_dictionary[split])
