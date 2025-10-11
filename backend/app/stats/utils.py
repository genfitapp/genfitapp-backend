MUSCLE_COLOR_MAP = {
    "Chest": {"color": "#FF6347", "gradientCenterColor": "#FF4500"},
    "Shoulders": {"color": "#1E90FF", "gradientCenterColor": "#104E8B"},
    "Arms": {"color": "#32CD32", "gradientCenterColor": "#228B22"},
    "Legs": {"color": "#FFD700", "gradientCenterColor": "#FFA500"},
    "Back": {"color": "#BA55D3", "gradientCenterColor": "#9932CC"},
    "Core": {"color": "#FF69B4", "gradientCenterColor": "#FF1493"},
    "Other": {"color": "#888", "gradientCenterColor": "#444"},
}

MUSCLE_GROUP_MAP = {
    "Legs": {
        "quads", "quadriceps", "glutes", "hamstrings", "calves", 
        "adductors", "abductors", "legs"
    },
    "Arms": {
        "biceps", "triceps", "forearms", "arms"
    },
    "Back": {
        "lats", "traps", "trapezius", "lower back", "back", 
        'lower-back', 'upper-back'
    },
    "Chest": {
        "pectorals", "pecs", "chest"
    },
    "Shoulders": {
        "delts", "deltoids", "rear delts", "shoulders", "front delts", "side delts"
    },
    "Core": {
        "abs", "abdominals", "obliques", "core"
    },
}

def get_muscle_group(muscle: str) -> str:
    if not muscle:
        return "Other"
    m = muscle.strip().lower()
    for group, aliases in MUSCLE_GROUP_MAP.items():
        if m in aliases:
            return group
    return "Other"
