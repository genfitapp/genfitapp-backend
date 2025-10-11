import math
import random
import pandas as pd
from itertools import combinations


# ---------------------------------------------------------------------
# Day-combination validators
#
# Notes:
# - days_of_week is a list of integers 1–7 (days of the week).
# - Functions below check whether a schedule supports certain splits.
# ---------------------------------------------------------------------

def valid_two_day_fullbody_days(days_of_week, min_difference):
    """
    Determine if the user's schedule supports a 2-day full-body split.

    Parameters:
    - days_of_week (list[int]): Available days, 1–7.
    - min_difference (int): Minimum gap between sessions.

    Returns:
    - list[list[int]]: Valid two-day combinations.
    """
    valid_combinations = []
    # (min_difference - 1) indicates minimum days between workouts.

    for day1, day2 in combinations(days_of_week, 2):
        direct_gap = abs(day2 - day1)
        wrap_around_gap = (7 - max(day1, day2)) + min(day1, day2)

        if direct_gap >= min_difference and wrap_around_gap >= min_difference:
            valid_combinations.append([day1, day2])

    return valid_combinations


def valid_three_day_upper_lower_days(days_of_week):
    """
    Determine if the schedule supports a 3-day upper/lower split.

    Parameters:
    - days_of_week (list[int]): Available days, 1–7.

    Returns:
    - list[list[int]]: Valid three-day combinations.
    """
    valid_combinations = []
    min_difference = 3

    for day1, day2, day3 in combinations(days_of_week, 3):
        direct_gap = abs(day3 - day1)
        wrap_around_gap = (7 - max(day1, day3)) + min(day1, day3)

        if direct_gap >= min_difference and wrap_around_gap >= min_difference:
            valid_combinations.append([day1, day2, day3])

    return valid_combinations


def valid_three_day_fullbody_days(days):
    """
    Determine if the schedule supports a 3-day full-body split.

    Parameters:
    - days (list[int]): Available days, 1–7.

    Returns:
    - list[list[int]]: Valid three-day combinations.
    """
    valid_combinations = []

    for day1, day2, day3 in combinations(days, 3):
        gap1 = day2 - day1
        gap2 = day3 - day2
        gap3 = (7 - day3) + day1

        if gap1 >= 2 and gap2 >= 2 and gap3 >= 2:
            valid_combinations.append([day1, day2, day3])

    return valid_combinations


def valid_four_day_upper_lower_days(days_of_week):
    """
    Determine if the schedule supports a 4-day upper/lower or PHUL split.

    Parameters:
    - days_of_week (list[int]): Available days, 1–7.

    Returns:
    - list[list[int]]: Valid four-day combinations.
    """
    valid_combinations = []

    for day1, day2, day3, day4 in combinations(days_of_week, 4):
        gap1 = day3 - day1
        gap2 = day4 - day1

        if gap1 >= 3 and gap2 >= 3:
            valid_combinations.append([day1, day2, day3, day4])

    return valid_combinations


# ---------------------------------------------------------------------
# Split recommendation
# ---------------------------------------------------------------------

def recommend_split(days_of_week, workout_frequency, time_per_workout,
                    level, goals):
    """
    Recommend a workout split based on schedule, frequency, time,
    experience level, and goals.

    Parameters:
    - days_of_week (list[int])
    - workout_frequency (int)
    - time_per_workout (int)
    - level (int/str)
    - goals (list[str])

    Returns:
    - str: Name of the recommended split.
    """
    level = int(level)

    if workout_frequency == 1:
        return 'Full-Body'

    if workout_frequency == 2:
        if valid_two_day_fullbody_days(days_of_week, 3) and level == 0:
            return 'Full-Body'
        if valid_two_day_fullbody_days(days_of_week, 2) and level >= 1:
            return 'Full-Body'
        return 'Upper-Lower'

    if workout_frequency == 3:
        if (valid_three_day_upper_lower_days(days_of_week) and
                time_per_workout > 45):
            return 'Upper-Lower'
        if (valid_three_day_fullbody_days(days_of_week) and
                level >= 1 and time_per_workout <= 45):
            return 'Full-Body'
        return 'Push-Pull-Legs'

    if workout_frequency == 4:
        valid = valid_four_day_upper_lower_days(days_of_week)
        if (any(g in ['Powerlifting', 'Get stronger'] for g in goals) and
            any(g in ['Bodybuilding', 'Build Muscles', 'Get Lean']
                for g in goals) and valid):
            # In this scenario, prioritize strength a bit more.
            return 'PHUL'
        if valid:
            return 'Upper-Lower'
        return 'Push-Pull-Legs'

    if workout_frequency == 5:
        # Potential change: hybrid PPL + Upper/Lower logic.
        if (any(g in ['Powerlifting', 'Get stronger'] for g in goals) and
            any(g in ['Bodybuilding', 'Build Muscles', 'Get Lean']
                for g in goals)):
            return 'Hybrid PPL + Upper-Lower'
        if time_per_workout < 45:
            return 'Body part split'
        return 'Push-Pull-Legs'

    if workout_frequency == 6:
        if time_per_workout <= 30:
            return '6-day body part split'
        return 'Push-Pull-Legs'

    if workout_frequency == 7:
        return 'Push-Pull-Legs + active rest'


goal_to_modality_further_simplified = {
    "Get stronger": ['H'],
    "Bodybuilding": ['H'],
    "Build muscles": ['H'],
    "Aesthetics": ['H'],
    # Optionally add 'C' (cardio) where marked.
    "Losing weight": ['H', 'C'],
    "Get lean": ['H', 'C'],
    # Optionally include 'AE' (aerobic endurance).
    "Increase endurance": ['H', 'AE']
}


goal_to_training_phase = {
    "Get stronger": "Strength",
    "Bodybuilding": "Hypertrophy",
    "Build muscles": "Hypertrophy",
    "Aesthetics": "Hypertrophy",
    "Losing weight": "Hypertrophy",
    "Get lean": "Hypertrophy",
    "Increase endurance": "Endurance"
}


# ---------------------------------------------------------------------
# Split muscle-group structures with ranges and probabilities
# ---------------------------------------------------------------------

split_dictionary_complex = {
    # Full-body: groups are prioritized in the listed order.
    "Full-Body": {
        "groups": [
            ["Chest", "Back", "Shoulders", "Quads", "Hamstrings", "Triceps",
             "Biceps", "Trapezius", "Lower back", "Obliques", "Abs",
             "Glutes", "Abductors", "Adductors", "Calves"]
        ],
        "focus_distribution_ranges": [
            [(0.2, 0.3), (0.2, 0.3), (0.1, 0.2), (0.2, 0.3), (0.2, 0.3),
             (0, 0.1), (0, 0.1), (0, 0.1), (0, 0.1), (0, 0.1), (0, 0.1),
             (0.1, 0.2), (0, 0.1), (0, 0.1), (0, 0.1)]
        ],
        "probabilities": [
            [0.19, 0.19, 0.05, 0.19, 0.09, 0.03, 0.03, 0.03, 0.02, 0.02,
             0.02, 0.03, 0.03, 0.03, 0.02],
        ]
    },

    "Upper-Lower": {
        "groups": [
            ["Chest", "Shoulders", "Triceps", "Back", "Biceps", "Trapezius",
             "Lower back", "Obliques", "Abs"],
            ["Quads", "Glutes", "Hamstrings", "Abductors", "Adductors",
             "Calves"]
        ],
        "focus_distribution_ranges": [
            [(0.2, 0.35), (0.1, 0.2), (0, 0.15), (0.2, 0.35), (0, 0.15),
             (0, 0.1), (0, 0.1), (0, 0.1), (0, 0.1)],
            [(0.3, 0.4), (0.2, 0.3), (0.2, 0.3), (0.05, 0.1), (0.05, 0.1),
             (0.1, 0.15)]
        ],
        "probabilities": [
            [0.25, 0.14, 0.08, 0.25, 0.08, 0.05, 0.03, 0.03, 0.09],
            [0.3, 0.2, 0.3, 0.05, 0.05, 0.1]
        ]
    },

    "Push-Pull-Legs": {
        "groups": [
            ["Chest", "Shoulders", "Triceps"],
            ["Back", "Biceps", "Trapezius", "Abs", "Obliques"],
            ["Quads", "Glutes", "Hamstrings", "Abductors", "Adductors",
             "Calves", "Lower back"]
        ],
        "focus_distribution_ranges": [
            [(0.4, 0.6), (0.2, 0.4), (0.2, 0.4)],
            [(0.4, 0.6), (0.1, 0.3), (0.1, 0.2), (0.1, 0.3), (0.05, 0.1)],
            [(0.3, 0.4), (0.2, 0.3), (0.2, 0.3), (0.05, 0.1), (0.05, 0.1),
             (0.1, 0.15), (0.05, 0.1)]
        ],
        "probabilities": [
            [0.5, 0.3, 0.2],
            [0.5, 0.2, 0.13, 0.12, 0.05],
            [0.24, 0.2, 0.24, 0.08, 0.08, 0.1, 0.06]
        ]
    },

    "PHUL": {
        "groups": [
            ["Chest", "Shoulders", "Triceps", "Back", "Biceps", "Trapezius",
             "Lower back", "Obliques", "Abs"],
            ["Quads", "Glutes", "Hamstrings", "Abductors", "Adductors",
             "Calves"]
        ],
        "focus_distribution_ranges": [
            [(0.2, 0.3), (0.1, 0.2), (0.1, 0.15), (0.2, 0.3), (0.1, 0.15),
             (0.1, 0.15), (0.05, 0.1), (0.05, 0.1), (0.05, 0.1)],
            [(0.3, 0.4), (0.2, 0.3), (0.2, 0.3), (0.05, 0.1), (0.05, 0.1),
             (0.1, 0.15)]
        ],
        "probabilities": [
            [0.24, 0.16, 0.08, 0.24, 0.08, 0.05, 0.03, 0.03, 0.09],
            [0.3, 0.2, 0.3, 0.05, 0.05, 0.1]
        ]
    },

    "Hybrid PPL + Upper-Lower": {
        "groups": [
            ["Chest", "Shoulders", "Triceps"],
            ["Back", "Biceps", "Trapezius", "Abs", "Obliques"],
            ["Quads", "Glutes", "Hamstrings", "Abductors", "Adductors",
             "Calves", "Lower back"],
            ["Chest", "Shoulders", "Triceps", "Back", "Biceps", "Trapezius",
             "Lower back", "Obliques", "Abs"],
            ["Quads", "Glutes", "Hamstrings", "Abductors", "Adductors",
             "Calves"]
        ],
        "focus_distribution_ranges": [
            [(0.4, 0.6), (0.2, 0.4), (0.2, 0.4)],
            [(0.4, 0.6), (0.1, 0.3), (0.1, 0.2), (0.1, 0.3), (0.05, 0.1)],
            [(0.3, 0.4), (0.2, 0.3), (0.2, 0.3), (0.05, 0.1), (0.05, 0.1),
             (0.1, 0.15), (0.05, 0.1)],
            [(0.2, 0.3), (0.1, 0.2), (0.1, 0.15), (0.2, 0.3), (0.1, 0.15),
             (0.1, 0.15), (0.05, 0.1), (0.05, 0.1), (0.05, 0.1)],
            [(0.3, 0.4), (0.2, 0.3), (0.2, 0.3), (0.05, 0.1), (0.05, 0.1),
             (0.1, 0.15)]
        ],
        "probablities": [
            [0.5, 0.3, 0.2],
            [0.5, 0.2, 0.13, 0.12, 0.05],
            [0.24, 0.2, 0.24, 0.08, 0.08, 0.1, 0.06],
            [0.24, 0.16, 0.08, 0.24, 0.08, 0.05, 0.03, 0.03, 0.09],
            [0.3, 0.2, 0.3, 0.05, 0.05, 0.1]
        ]
    },

    "Body part split": {
        "groups": [
            ["Chest"],
            ["Back", "Trapezius"],
            ["Quads", "Glutes", "Hamstrings", "Abductors", "Adductors",
             "Calves", "Lower back"],
            ["Shoulders", "Abs", "Obliques"],
            ["Biceps", "Triceps"]
        ],
        "focus_distribution_ranges": [
            [(0.8, 1.0)],
            [(0.7, 0.9), (0.3, 0.1)],
            [(0.3, 0.4), (0.2, 0.3), (0.2, 0.3), (0.05, 0.1), (0.05, 0.1),
             (0.1, 0.15), (0.05, 0.1)],
            [(0.6, 0.8), (0.4, 0.2), (0.2, 0.05)],
            [(0.4, 0.6), (0.4, 0.6)]
        ],
        "probabilities": [
            [1],
            [0.8, 0.2],
            [0.24, 0.2, 0.24, 0.08, 0.08, 0.1, 0.06],
            [0.7, 0.2, 0.1],
            [0.5, 0.5]
        ]
    },

    "6-day body part split": {
        "groups": [
            ["Chest"],
            ["Back", "Trapezius"],
            ["Quads", "Glutes", "Hamstrings", "Abductors", "Adductors",
             "Calves"],
            ["Abs", "Obliques", "Lower back"],
            ["Shoulders"],
            ["Biceps", "Triceps"]
        ],
        "focus_distribution_ranges": [
            [(0.8, 1.0)],
            [(0.7, 0.9), (0.3, 0.1)],
            [(0.3, 0.4), (0.2, 0.3), (0.2, 0.3), (0.05, 0.1), (0.05, 0.1),
             (0.1, 0.15)],
            [(0.6, 0.7), (0.2, 0.3), (0.2, 0.3)],
            [(0.8, 1.0)],
            [(0.4, 0.6), (0.4, 0.6)]
        ],
        "probabilities": [
            [1],
            [0.8, 0.2],
            [0.24, 0.2, 0.24, 0.08, 0.08, 0.1, 0.06],
            [0.7, 0.2, 0.1],
            [1],
            [0.5, 0.5]
        ]
    }
}


# ---------------------------------------------------------------------
# Phase and group selection
# ---------------------------------------------------------------------

def get_training_phase_and_group_for_day(user_goals, user_split, current_day):
    """
    Determine the training phase and split-group index for a session.

    Parameters:
    - user_goals (list[str]): Ordered list of goals.
    - user_split (str): Recommended split (e.g., 'Push-Pull-Legs').
    - current_day (int): Workout day count (0-indexed).

    Returns:
    - tuple[str, int]: (training_phase, split_muscle_group_index)
    """
    unique_phases = list({goal_to_training_phase[g] for g in user_goals})

    split_length = len(split_dictionary_complex[user_split]["groups"])
    # print(split_length)

    # Index of current split day (0: push, 1: pull, etc.).
    split_muscle_group_index = current_day % split_length

    # Phase (e.g., Strength: low reps, high rest; Hypertrophy: medium reps).
    training_phase = unique_phases[
        (current_day // split_length) % len(unique_phases)
    ]
    # print(training_phase)

    return training_phase, split_muscle_group_index


# ---------------------------------------------------------------------
# Dataset filtering and utility helpers
# ---------------------------------------------------------------------

def filter_data(df, user_level, user_equipment, training_modalities, age, pain_points):
    """
    Filter exercises by level, equipment, training modalities, pains, age.

    Parameters:
    - df (pd.DataFrame)
    - user_level (str|int)
    - user_equipment (list[str])
    - training_modalities (list[str])
    - pain_points (list[str])
    - age (int)

    Returns:
    - pd.DataFrame: Filtered dataset.
    """
    user_equipment_set = set(user_equipment)

    """ TODO: Make sure that the keys used to extract """

    filtered_df = df[
        (df['level'].apply(lambda x: user_level in x)) &
        (df['equipment'].apply(
            lambda subsets: any(
                set(subset).issubset(user_equipment_set) for subset in subsets
                if subset
            )
        )) &
        (df['exercise_purpose'].apply(
            lambda x: any(m in x for m in training_modalities)
        )) &
        (~df['pain_exclusions'].apply(
            lambda x: any(p in x for p in pain_points)
        )) &
        ((age <= 50) | (df['risk_level'] <= 2))
    ]

    # import itertools
    # unique_main_muscles = set(itertools.chain.from_iterable(filtered_df['main_muscles']))
    # print(f"{training_modalities} -> 1 -> ", unique_main_muscles)
    return filtered_df


def get_reps_and_rest_time(training_phase):
    """
    Map training phase to rep range and rest time.

    Parameters:
    - training_phase (str)

    Returns:
    - dict: {'reps': (min, max), 'rest_time': minutes} or None.
    """
    phase_to_reps_and_time = {
        "Strength": {"reps": (5, 7), "rest_time": 3},
        "Hypertrophy": {"reps": (8, 12), "rest_time": 2},
        "Endurance": {"reps": (13, 16), "rest_time": 2}
    }
    return phase_to_reps_and_time.get(training_phase)


def filter_muscles(df, muscles):
    """
    Filter exercises to those that train at least one target muscle.

    Parameters:
    - df (pd.DataFrame)
    - muscles (list[str])

    Returns:
    - pd.DataFrame
    """
    """ TODO: Make sure that you are using the right key name """
    filtered_df = df[
        df['main_muscles'].apply(
            lambda x: any(muscle in x for muscle in muscles)
        )
    ]
    return filtered_df


def generate_biased_distribution_chatgpt(ranges, priority_muscles, muscles,
                                         bias_factor=0.1, round_digits=2):
    """
    Sample a distribution within per-muscle ranges, bias priority muscles,
    clamp to [min, max], then renormalize to sum to 1 (no negatives).
    """
    assert len(ranges) == len(muscles), "ranges and muscles length mismatch"

    # 1) Sample raw values within each (min, max).
    raw = []
    for (lo, hi) in ranges:
        lo = max(0.0, lo)
        hi = max(lo, hi)
        raw.append(random.uniform(lo, hi))

    # 2) Apply multiplicative bias to priority muscles.
    biased = []
    for val, m in zip(raw, muscles):
        if m in priority_muscles:
            biased.append(val * (1.0 + bias_factor))
        else:
            biased.append(val)

    # 3) Clamp to [min, max] again (bias might exceed upper bound).
    clamped = []
    for (lo, hi), val in zip(ranges, biased):
        lo = max(0.0, lo)
        hi = max(lo, hi)
        clamped.append(min(max(val, lo), hi))

    # 4) Normalize to sum to 1.
    clamped = [max(0.0, x) for x in clamped]
    s = sum(clamped)
    if s == 0:
        normalized = [1.0 / len(clamped)] * len(clamped)
    else:
        normalized = [x / s for x in clamped]

    # 5) Optional rounding at the end (for display).
    if round_digits is not None:
        normalized = [round(x, round_digits) for x in normalized]
        s2 = sum(normalized)
        if s2 > 0:
            normalized = [round(x / s2, round_digits) for x in normalized]

    return normalized


def calculate_total_exercises(time_for_lifting, avg_time_per_set,
                              sets_per_exercise, rest_time_per_set):
    """
    Compute total count of exercises that fit the available time.
    """
    time_per_exercise = (avg_time_per_set + rest_time_per_set) \
        * sets_per_exercise
    total_exercises = time_for_lifting // time_per_exercise
    return total_exercises


def calculate_exercises_per_muscle(total_exercises, muscle_groups,
                                   focus_distribution):
    """
    Allocate exercise counts to each muscle based on focus distribution.

    Parameters:
    - total_exercises (int)
    - muscle_groups (list[str])
    - focus_distribution (list[float])

    Returns:
    - dict[str, int]
    """
    # print(focus_distribution)
    num_muscle_groups = len(muscle_groups)

    if len(focus_distribution) != num_muscle_groups:
        raise ValueError("Focus distribution must match group count.")

    exercises_per_muscle = {
        muscle: round(total_exercises * focus)
        for muscle, focus in zip(muscle_groups, focus_distribution)
    }

    # print(exercises_per_muscle)
    return exercises_per_muscle


# ---------------------------------------------------------------------
# Exercise selection with user preferences (not yet wired)
# ---------------------------------------------------------------------

def select_exercises_with_user_preferences(filtered_df, exercises_per_muscle,
                                           user_favorites=None,
                                           suggest_less=None,
                                           dont_show_again=None):
    """
    Select exercises per muscle group based on user preferences.

    Parameters:
    - filtered_df (pd.DataFrame)
    - exercises_per_muscle (dict[str, int])
    - user_favorites (set[str])
    - suggest_less (set[str])
    - dont_show_again (set[str])

    Returns:
    - dict[str, pd.DataFrame]: Selected rows per muscle group.
    
    TODO: Make sure that the key names matches that from the database.
    
    """
    FAVORITE_WEIGHT = 2
    SUGGEST_LESS_WEIGHT = 0.25

    user_favorites = user_favorites or set()
    suggest_less = suggest_less or set()
    dont_show_again = dont_show_again or set()

    selected_exercises = {}

    # print('bet!')
    # import itertools
    # unique_main_muscles = set(itertools.chain.from_iterable(filtered_df['main_muscles']))
    # print(unique_main_muscles)

    for muscle, num_exercises in exercises_per_muscle.items():
        # First, filter exercises for the muscle group. 
        muscle_exercises = filtered_df[
            filtered_df["main_muscles"].apply(lambda x: muscle in x)
        ]

        # print(muscle)

        # Remove "Don't show again" entries.
        muscle_exercises = muscle_exercises[
            ~muscle_exercises["name"].isin(dont_show_again)
        ]

        # Assign sampling weights.
        exercise_weights = muscle_exercises["name"].apply(
            lambda x: (FAVORITE_WEIGHT if x in user_favorites else
                       SUGGEST_LESS_WEIGHT if x in suggest_less else
                       1)
        )

        # Sample exercises.
        if num_exercises > len(muscle_exercises):
            # print(f"Warning: Not enough exercises for {muscle}.")
            sampled = muscle_exercises
        else:
            sampled = muscle_exercises.sample(
                n=num_exercises, weights=exercise_weights, replace=False
            )

        # Sort by difficulty (descending).
        sampled = sampled.sort_values(by="difficulty", ascending=False)
        selected_exercises[muscle] = sampled

    return selected_exercises


# ---------------------------------------------------------------------
# Equipment helpers
# ---------------------------------------------------------------------

band_progression = ["Extra Light", "Light", "Medium", "Heavy", "Extra Heavy"]


def infer_equipment_type(min_weight):
    """
    Infer equipment modality from the "lower bound" field.

    Returns:
    - "Gym Equipment" | "Timed Exercise" | "Resistance Band" | "Bodyweight"
    """
    if isinstance(min_weight, (int, float)) and min_weight > 0:
        return "Gym Equipment"
    elif isinstance(min_weight, str):
        if "seconds" in min_weight:
            return "Timed Exercise"
        elif min_weight in band_progression:
            return "Resistance Band"
    return "Bodyweight"


def bodyweight_algorithm(exercise_records, phase):
    """
    Suggest reps for bodyweight exercises based on recent history.

    Returns:
    - dict: {"weight": None, "reps": int}
    """
    phase_settings = {
        "Strength": {"target_reps": (5, 8)},
        "Hypertrophy": {"target_reps": (9, 12)},
        "Endurance": {"target_reps": (13, 16)}
    }

    settings = phase_settings[phase]
    target_reps = settings["target_reps"]

    phase_records = [rec for rec in exercise_records if rec["phase"] == phase]

    if not phase_records:
        return {"weight": None, "reps": target_reps[0]}

    last_record = phase_records[-1]
    last_reps = last_record["reps"]

    min_reps = min(last_reps)

    if min_reps < target_reps[1]:
        return {"weight": None, "reps": min_reps + 1}
    else:
        return {"weight": None, "reps": target_reps[1]}


def estimate_weight_Brzycki(actual_weight, actual_reps, target_reps):
    """
    Estimate target weight for a given rep goal (Brzycki formula).

    Notes:
    - Most accurate for reps <= 10.
    """
    if actual_reps > 10 or target_reps > 10:
        raise ValueError("Brzycki works best for reps <= 10.")

    one_rep_max = actual_weight / (1.0278 - (0.0278 * actual_reps))
    target_weight = one_rep_max * (1.0278 - (0.0278 * target_reps))
    target_weight = round(target_weight / 5) * 5
    return target_weight


def estimate_weight_epley(actual_weight, actual_reps, target_reps):
    """
    Estimate target weight for a given rep goal (Epley formula).
    """
    one_rep_max = actual_weight * (1 + 0.0333 * actual_reps)
    target_weight = one_rep_max / (1 + 0.0333 * target_reps)
    target_weight = round(target_weight / 5) * 5
    return target_weight


def weight_algorithm(user_exercise_records, phase):
    """
    Suggest weight and reps based on user history and phase.

    Parameters:
    - user_exercise_records (list[dict])
    - phase (str)

    Returns:
    - dict: {"weight": number, "reps": int}
    """
    phase_settings = {
        "Strength": {"target_reps": (5, 8), "increment": 10},
        "Hypertrophy": {"target_reps": (9, 12), "increment": 10},
        "Endurance": {"target_reps": (13, 16), "increment": 10}
    }

    settings = phase_settings[phase]
    target_reps = settings["target_reps"]
    increment = settings["increment"]

    phase_records = [rec for rec in user_exercise_records
                     if rec["phase"] == phase]
    history = {(rec["weight"], tuple(rec["reps"])) for rec in phase_records}

    def has_better_performance(weight, suggested_reps):
        for rec_weight, rec_reps in history:
            if (rec_weight == weight and
                math.floor(sum(rec_reps)) >= suggested_reps * len(rec_reps)):
                return True
        return False

    if not phase_records:
        last_record = user_exercise_records[-1]
        last_weight = last_record["weight"]
        last_reps = last_record["reps"]
        avg_reps = round(sum(last_reps) / len(last_reps))

        if target_reps[0] <= 10:
            estimated_weight = estimate_weight_Brzycki(
                last_weight, avg_reps, target_reps[0]
            )
        else:
            estimated_weight = estimate_weight_epley(
                last_weight, avg_reps, target_reps[0]
            )
        return {"weight": estimated_weight, "reps": target_reps[0]}

    last_record = phase_records[-1]
    last_weight = last_record["weight"]
    last_reps = last_record["reps"]
    avg_reps = round(sum(last_reps) / len(last_reps))

    # 1) Try decreasing weight and increasing reps (+2) if possible.
    if avg_reps + 2 <= target_reps[1]:
        decreased_weight = last_weight - increment
        new_combo = (decreased_weight, avg_reps + 2)
        if (new_combo not in history and
                not has_better_performance(new_combo[0], new_combo[1])):
            return {"weight": decreased_weight, "reps": avg_reps + 2}

    # 2) Otherwise increase weight; attempt small rep reductions.
    increased_weight = last_weight + increment

    if target_reps[0] <= avg_reps - 2 <= target_reps[1]:
        new_combo = (increased_weight, avg_reps - 2)
        if (new_combo not in history and
                not has_better_performance(new_combo[0], new_combo[1])):
            return {"weight": increased_weight, "reps": avg_reps - 2}
        new_combo = (increased_weight, avg_reps - 1)
        if (new_combo not in history and
                not has_better_performance(new_combo[0], new_combo[1])):
            return {"weight": increased_weight, "reps": avg_reps - 1}

    # 3) Fallback: keep weight, try +1 rep (if within range).
    if avg_reps + 1 <= target_reps[1]:
        new_combo = (last_weight, avg_reps + 1)
        if (new_combo not in history and
                not has_better_performance(new_combo[0], new_combo[1])):
            return {"weight": last_weight, "reps": avg_reps + 1}

    # Last fallback: new heavier weight at lower bound of range.
    return {"weight": increased_weight, "reps": target_reps[0]}


def band_algorithm(exercise_records, phase):
    """
    Suggest next resistance band level based on performance.

    Parameters:
    - exercise_records (list[dict])
    - phase (str)

    Returns:
    - dict: {"weight": level, "reps": int}
    """
    band_levels = ["Light", "Medium", "Heavy", "Extra Heavy"]

    phase_settings = {
        "Strength": {"target_reps": (5, 8)},
        "Hypertrophy": {"target_reps": (9, 12)},
        "Endurance": {"target_reps": (13, 16)}
    }

    settings = phase_settings[phase]
    target_reps = settings["target_reps"]

    # If no records: historically, would start with lightest band.
    # if not exercise_records:
    #     return band_levels[0]

    last_record = exercise_records[-1]
    last_band = last_record["weight"]  # level as string
    last_reps = last_record["reps"]
    avg_reps = sum(last_reps) // len(last_reps)

    if last_band not in band_levels:
        last_band_index = 1
    else:
        last_band_index = band_levels.index(last_band)

    # 1) At/above upper bound → move to next level, reset reps.
    if avg_reps >= target_reps[1] and last_band_index < len(band_levels) - 1:
        return {"weight": band_levels[last_band_index + 1],
                "reps": target_reps[0]}

    # 2) Within target → maintain level, increase reps.
    if target_reps[0] <= avg_reps < target_reps[1]:
        return {"weight": last_band, "reps": avg_reps + 1}

    # 3) Below target → reduce resistance if possible.
    if avg_reps < target_reps[0] and last_band_index > 0:
        return {"weight": band_levels[last_band_index - 1],
                "reps": avg_reps + 1}

    return {"weight": last_band, "reps": avg_reps}


def timed_algorithm(exercise_records):
    """
    Suggest time for timed exercises (planks, wall sits, etc.).

    Returns:
    - dict: {"weight": None, "reps": None, "time": seconds}
    """
    max_time = 180  # Cap at 3 minutes.
    increment = 5   # Add 5 seconds on success.

    # If no records: historically start from a base time.
    # if not exercise_records:
    #     return 30

    last_record = exercise_records[-1]
    last_times = last_record["time"]
    avg_time = sum(last_times) // len(last_times)

    if avg_time < max_time:
        new_time = avg_time + increment
        return {"weight": None, "reps": None, "time": min(new_time, max_time)}
    else:
        return {"weight": None, "reps": None, "time": max_time}


def find_specific_equipment(exercise_equipment):
    """
    Infer a specific equipment type and quantity from equipment combos.

    Parameters:
    - exercise_equipment (list[list[str]])

    Returns:
    - tuple[str, int] | None: (equipment_type, quantity)
    """
    equipment_type_map = {
        "1 Dumbbell":       ("Dumbbells", 1),
        "2 Dumbbell":       ("Dumbbells", 2),
        "1 Kettlebell":     ("Kettlebells", 1),
        "2 Kettlebell":     ("Kettlebells", 2),
        "Fixed weight bar": ("Fixed weight bar", 1),
        "Mini loop band":   ("Mini loop band", 1),
        "1 Loop band":      ("Loop band", 1),
        "2 Loop band":      ("Loop band", 2),
        "Handle band":      ("Handle band", 1)
    }

    for combo in exercise_equipment:
        # print("printing combo", combo)
        for item in combo:
            # print("printing item", item)
            if item in equipment_type_map:
                return equipment_type_map[item]

    return None


def find_closest_available_weight(suggested_weight, equipment_type,
                                  user_available_weights,
                                  required_quantity=1):
    """
    Find the closest available weight the user owns for a type, honoring
    quantity. In a tie, choose the lower weight.

    Returns:
    - float | None
    """
    if required_quantity == 2:
        suggested_weight = suggested_weight / 2

    available = user_available_weights.get(equipment_type, {})
    valid_weights = [w for w, qty in available.items() if qty >=
                     required_quantity]

    if not valid_weights:
        return None

    valid_weights.sort(key=lambda w: (abs(int(w) - suggested_weight), w))

    if required_quantity == 2:
        return valid_weights[0] * 2
    else:
        return valid_weights[0]


def find_closest_available_resistance(suggested_level, equipment_type,
                                      user_available_weights,
                                      required_quantity=1):
    """
    Find the closest available band level from user inventory.

    Returns:
    - str | None
    """
    RESISTANCE_BAND_LEVELS = ["Extra Light", "Light", "Medium", "Heavy",
                              "Extra Heavy"]

    if equipment_type not in user_available_weights:
        return None

    available_bands = user_available_weights[equipment_type]

    if suggested_level not in RESISTANCE_BAND_LEVELS:
        return None

    target_index = RESISTANCE_BAND_LEVELS.index(suggested_level)

    for offset in range(len(RESISTANCE_BAND_LEVELS)):
        lower_index = target_index - offset
        if lower_index >= 0:
            level = RESISTANCE_BAND_LEVELS[lower_index]
            if available_bands.get(level, 0) >= required_quantity:
                return level

        upper_index = target_index + offset
        if upper_index < len(RESISTANCE_BAND_LEVELS):
            level = RESISTANCE_BAND_LEVELS[upper_index]
            if available_bands.get(level, 0) >= required_quantity:
                return level

    return None


def find_similar_exercise(exercise_name, records, user_id, filtered_dataset):
    """
    Find a similar exercise using the dataset's "Variations" column.

    Parameters:
    - exercise_name (str)
    - records (dict)
    - user_id (str)
    - filtered_dataset (pd.DataFrame)

    TODO: Fix the filtered data frame key names

    Returns:
    - str | None: Name of a similar exercise if found.
    """
    exercise_row = filtered_dataset[filtered_dataset["name"] == exercise_name]

    if exercise_row.empty:
        return None

    variations = exercise_row.iloc[0].get("Variations", [])

    if isinstance(variations, list):
        for variation in variations:
            if user_id in records and variation in records[user_id][
                    "by_exercise"]:
                return variation
                # Optional improvement: return the records directly.

    return None


def round_gym_weight(weight, is_pair=False):
    """
    Round weight to typical gym increments. If is_pair=True (DB/KB),
    returns the total combined weight.
    """
    common_weights = [
        5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 30, 35, 40, 45, 50, 55, 60,
        65, 70, 75, 80, 85, 90, 95, 100
    ]

    if is_pair:
        per_piece = weight / 2
        closest = min(common_weights, key=lambda x: abs(x - per_piece))
        return closest * 2
        # Note: could return per-piece weight, but this returns total.

    return round(weight / 5) * 5


def muscle_algorithm(similar_exercise_records, quantity):
    """
    Estimate a starting weight using records from a similar exercise.

    Parameters:
    - similar_exercise_records (list[dict])
    - quantity (int): 1 for singles, 2 for pairs (DB/KB).

    Returns:
    - dict: {"weight": number, "reps": int}
    """
    SCALING_FACTOR = 0.8

    latest_record = similar_exercise_records[-1]
    last_weight = latest_record["weight"]
    last_reps = latest_record["reps"]
    avg_reps = sum(last_reps) // len(last_reps)

    estimated_weight = round_gym_weight(last_weight * SCALING_FACTOR,
                                        quantity > 1)

    return {"weight": estimated_weight, "reps": avg_reps}


experience_multiplier = {
    '1': 1,        # Cautious start
    '2': 1.25,     # Standard suggestion
    '3': 1.50,     # More load with progress
    '4': 2.0       # Aggressive for experienced lifters
}


def determine_weight(row, user_id, user_level, records, filtered_dataset,
                     training_phase, user_available_weights, user_equipment):
    """
    Determine weight/reps using history or experience multipliers.

    Parameters:
    - row (pd.Series)
    - user_id (str)
    - user_level (str)
    - records (dict)
    - filtered_dataset (pd.DataFrame)
    - training_phase (str)
    - user_available_weights (dict)
    - user_equipment (list[str])

    TODO: Fix rows to use keys from database exercise table

    Returns:
    - dict: {"weight": number|str|None, "reps": int|None, "time": int|None}
    """
    exercise_name = row["name"]
    min_weight = row["lower_bound"]
    exercise_type = infer_equipment_type(min_weight)
    exercise_equipment = row["equipment"]
    # print("printing equipment", row["Equipment"])

    # If the user has past records for this exercise, use them.
    if records.get(user_id) and exercise_name in records[user_id][
            "by_exercise"]:
        exercise_records = records[user_id]["by_exercise"][exercise_name]
        # Weight algorithm calls Brzycki/Epley and expects total values.

        if exercise_type == "Gym Equipment":
            suggested_results = weight_algorithm(exercise_records, training_phase)
            # print("Calling weight algorithm with records")
        elif exercise_type == "Resistance Band":
            suggested_results = band_algorithm(exercise_records, training_phase)
            # print("Calling band algorithm with records")
        elif exercise_type == "Bodyweight":
            # print("Calling bodyweight algorithm with records")
            return bodyweight_algorithm(exercise_records, training_phase)
        elif exercise_type == "Timed Exercise":
            # print("Calling timed algorithm with records")
            return timed_algorithm(exercise_records)

        suggested_weight = suggested_results["weight"]
        suggested_reps = suggested_results["reps"]
        equipment_info = find_specific_equipment(exercise_equipment)
        # print("printing equipment info: ", equipment_info)

        if equipment_info:
            # Example: ("Dumbbells", 2)
            # print("inside equipment_info statement")
            equipment_type, quantity_needed = equipment_info

            skip_validation = (
                equipment_type == "Fixed weight bar" and
                any(e in user_equipment for e in
                    ["Olympic barbell", "EZ curl bar"])
            )

            if not skip_validation:
                single_weight = suggested_weight
                if (equipment_type in ["Dumbbells", "Kettlebells"] and
                        quantity_needed == 2):
                    single_weight = suggested_weight / 2
                    user_has_weight = user_available_weights.get(
                        equipment_type, {}
                    ).get(single_weight, 0)
                else:
                    user_has_weight = user_available_weights.get(
                        equipment_type, {}
                    ).get(suggested_weight, 0)

                if user_has_weight < quantity_needed:
                    # print(f"Adjusting weight: {single_weight} not available!")
                    if exercise_type == "Gym Equipment":
                        suggested_weight = find_closest_available_weight(
                            suggested_weight, equipment_type,
                            user_available_weights, quantity_needed
                        )
                    elif exercise_type == "Resistance Band":
                        suggested_weight = find_closest_available_resistance(
                            suggested_weight, equipment_type,
                            user_available_weights, quantity_needed
                        )

        return {"weight": suggested_weight, "reps": suggested_reps}

    # No prior records: use similar exercise or experience multiplier.
    if exercise_type == "Gym Equipment":
        equipment_type, quantity_needed = (
            find_specific_equipment(exercise_equipment) or (None, 1)
        )

        similar_exercise = find_similar_exercise(
            exercise_name, records, user_id, filtered_dataset
        )

        if similar_exercise:
            similar_records = records[user_id]["by_exercise"][similar_exercise]
            # print("About to call muscle_algorithm()...")
            suggested_results = muscle_algorithm(similar_records,
                                                 quantity_needed)
            suggested_weight = suggested_results["weight"]
            suggested_reps = suggested_results["reps"]
        else:
            # print("Estimating starting weight based on experience "
            #       "multiplier...")
            suggested_weight = (min_weight * quantity_needed *
                                experience_multiplier[user_level])
            suggested_weight = round_gym_weight(suggested_weight,
                                                quantity_needed > 1)
            suggested_reps = 10

        skip_validation = (
            equipment_type == "Fixed weight bar" and
            any(e in user_equipment for e in
                ["Olympic barbell", "EZ curl bar"])
        )

        if not skip_validation and equipment_type:
            single_weight = suggested_weight
            if (equipment_type in ["Dumbbells", "Kettlebells"] and
                    quantity_needed == 2):
                single_weight = suggested_weight / 2
                user_has_weight = user_available_weights.get(
                    equipment_type, {}
                ).get(single_weight, 0)
            else:
                user_has_weight = user_available_weights.get(
                    equipment_type, {}
                ).get(suggested_weight, 0)

            if user_has_weight < quantity_needed:
                # print(f"Adjusting weight 2: {single_weight} lbs "
                #       f"not available!")
                suggested_weight = find_closest_available_weight(
                    suggested_weight, equipment_type, user_available_weights,
                    quantity_needed
                )

        return {"weight": suggested_weight, "reps": suggested_reps}

    # Resistance band without records: start from min level and adjust.
    if exercise_type == "Resistance Band":
        suggested_weight = min_weight
        suggested_reps = 10

        equipment_type, quantity_needed = (
            find_specific_equipment(exercise_equipment) or (None, 1)
        )
        if equipment_type:
            user_has_weight = user_available_weights.get(
                equipment_type, {}
            ).get(suggested_weight, 0)

            if user_has_weight < quantity_needed:
                # print(f"Adjusting resistance: {suggested_weight} "
                #       f"not available!")
                suggested_weight = find_closest_available_resistance(
                    suggested_weight, equipment_type, user_available_weights,
                    quantity_needed
                )

        return {"weight": suggested_weight, "reps": suggested_reps}

    # Timed exercise without records: use lower bound time.
    if exercise_type == "Timed Exercise":
        # print("No record timed exercise...")
        return {"weight": None, "reps": None, "time": min_weight}

    # Bodyweight default: use min_weight as-is and reps=10.
    # print("no record bodyweight exercise")
    return {"weight": min_weight, "reps": 10, "time": None}


# ---------------------------------------------------------------------
# Workout generation
# ---------------------------------------------------------------------

def workout_generator(
        user_id,                # User Id  -> int
        age,                    # age of user -> int
        user_workout_count,     # total workout count for user
        # user_split,             # User's workout split
        user_records,           # User records -> exercise record for user should be by_exercises -> List
        days_of_week,           # Week day availability of the user -> [1, 3, 5] -> Mon - Wed. - Fri
        workout_frequency,      # How many times a week the user wants to workout -> int
        time_per_workout,       # Session time in minutes
        level,                  # User's fitness level - str("1")
        user_goals,             # User's goals -> List [""] must be in key items of goal_to_modality_further_simplified
        pain_points,            # List of user's potential pain points -> "Elbow Pain", "Knee Pain", etc...
        equipment,              # Should be in the form of equipment list look at example from notebook
        user_available_weights, # available weights for dumbbels and kettle bells dumbells, kettle bells, 
                                # Fixed weight bar, Mini loop band, etc... Should be dictionary of weight to pairs
        priority_muscles,       # List of muscles
        user_favorites,         # List of favorite exercise names chosen by user must be a type(set)
        suggest_less,           # List of exercise names chosen to suggest less to the user must be a type(set)
        dont_show_again         # List of exercise names not to show to the user must be a type(set)
    ):      
    """
    Generate a workout given user info, goals, schedule, and equipment.
    """
    path = r'app\workout\exercises.json'
    # path = r'backend\app\workout\exercises.json'
    df = pd.read_json(path)

    # Constants
    avg_time_per_set = 1     # minutes per set
    sets_per_exercise = 4    # sets per exercise

    # Determine split (e.g., PPL).
    user_split = recommend_split(
        days_of_week,
        workout_frequency, 
        time_per_workout, 
        level, 
        user_goals
    )

    # Collect all modalities; pick first to proceed (e.g., 'H').
    modalities = list(dict.fromkeys(
        m for goal in user_goals
        for m in goal_to_modality_further_simplified.get(goal, [])
    ))
    modality = modalities[0]

    training_phase, muscle_group_index = get_training_phase_and_group_for_day(
        user_goals, user_split, user_workout_count
    )
    
    rest_time_per_set = get_reps_and_rest_time(training_phase)["rest_time"]

    print(user_split, muscle_group_index)
    
    muscle_group = split_dictionary_complex[user_split]["groups"][
        muscle_group_index
    ]
    
    range_focus_distribution = split_dictionary_complex[user_split][
        "focus_distribution_ranges"
    ][muscle_group_index]

    # Primary filtering (level/equipment/modalities/pains/age).
    primary_filter = filter_data(df, level, equipment, modality, age, pain_points)
    # print(f"Total after primary: {primary_filter.shape[0]}")

    # Secondary filtering: only muscles for this split-day.
    secondary_filter = filter_muscles(primary_filter, muscle_group)

    # Sample a biased distribution across muscles for this session.
    randomized_focus_distribution = generate_biased_distribution_chatgpt(
        range_focus_distribution, priority_muscles, muscle_group
    )

    total_exercises = calculate_total_exercises(
        time_per_workout, avg_time_per_set, sets_per_exercise,
        rest_time_per_set
    )
    
    exercises_with_focus = calculate_exercises_per_muscle(
        total_exercises, muscle_group, randomized_focus_distribution
    )
    # print("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
    exercises = select_exercises_with_user_preferences(
        secondary_filter, exercises_with_focus, user_favorites,
        suggest_less, dont_show_again
    )
    # print("qwwwqwqwqwqweeeeeeeeeetttttttttttttttttttt")

    generated_exercises = []

    for muscle_group, df_sel in exercises.items():
        for _, exercise in df_sel.iterrows():
            # print(type(exercise))
            result = determine_weight(
                row=exercise,
                user_id=user_id,
                user_level=level,
                records=user_records,
                filtered_dataset=secondary_filter,
                training_phase=training_phase,
                user_available_weights=user_available_weights,
                user_equipment=equipment
            )

            """ 
                Check if the result has key time, if yes that is a time
                exercise.
            """
            
            generated_exercises.append({
                'exercise': exercise['name'],
                'suggested_intensity': result
            })

    # for g in generated_exercises:
    #     print(f"{g}\n")
    return generated_exercises


# from .temp import gym_equipment

# current_day = 0
# user_records = {  
#     "user123": {
#          "by_exercise": {    
#          }   
#     }
# }

# #From onboarding 

# age = 28
# days_of_week = [1,2,3,4,5,6,7]
# workout_frequency = 1
# time_per_workout = 120
# level = '4' # Must be passed as a string in order for the filtering data to work

# user_goals = ['Bodybuilding', 'Build muscles', 'Aesthetics', 'Get stronger']
# pain_points = []
# equipment = gym_equipment["Fully equipped gym"]["equipment"]
# user_available_weights = gym_equipment["Fully equipped gym"]["available_weights"]

# priority_muscles = ["Shoulders"]

# user_favorites = {"Barbell Bench Press"}
# suggest_less = {}
# dont_show_again = {"Incline Dumbbell Press"}



# generate_workout('user123', age, current_day, user_records, days_of_week, workout_frequency, time_per_workout, level, user_goals, pain_points,
#                  equipment, user_available_weights, priority_muscles, user_favorites, suggest_less, dont_show_again)