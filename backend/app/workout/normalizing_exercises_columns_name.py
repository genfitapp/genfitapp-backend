import json
import re
from collections import defaultdict
from pathlib import Path

# --- File paths ---
# SRC_FILE = "exercises_unprocessed.json"     # your raw source
# CANON_FILE = "exercises_1.0.json"           # canonical schema to mirror
# OUT_FILE = "exercises.json"                 # normalized output

SRC_FILE = "dataset_7.filtered.json"        # your raw source
CANON_FILE = "exercises_original.json"      # canonical schema to mirror
OUT_FILE = "exercises.json"                 # normalized output

# --- Load data ---
with open(SRC_FILE, "r", encoding="utf-8") as f:
    src_data = json.load(f)

with open(CANON_FILE, "r", encoding="utf-8") as f:
    canon_data = json.load(f)

# --- Derive canonical key set from exercises_1.0.json ---
canonical_keys = set()
for entry in canon_data:
    canonical_keys.update(entry.keys())

# Keep these extra fields too (even though they aren't in 1.0)
EXTRA_KEYS = {"type", "audio_script"}
canonical_plus_extras = canonical_keys | EXTRA_KEYS

def base_normalize_key(key: str) -> str:
    """
    1) lowercase
    2) remove parentheses and their contents (e.g., 'Lower bound(...)' -> 'Lower bound')
    3) replace spaces and dashes with underscores
    4) strip leading/trailing underscores
    """
    k = key.lower()
    k = re.sub(r"\(.*?\)", "", k)
    k = re.sub(r"[\s\-]+", "_", k)
    k = k.strip("_")
    return k

# Map variants/typos to canonical keys (left -> right)
ALIASES_TO_CANON = {
    # naming mismatches
    "exercise": "name",
    "title": "name",
    "main_muscle": "main_muscles",
    "primary_muscle": "main_muscles",
    "primary_muscles": "main_muscles",
    "movement_pattern": "movement",
    "prerequesite_exercise": "prerequisite_exercise",   # typo fix
    "prerequisite_exercises": "prerequisite_exercise",  # singular in canon
    "equipment_types": "equipment_type",
    "force_types": "force_type",
    "exercise_purposes": "exercise_purpose",
    "pain_exclusion": "pain_exclusions",
    "risk": "risk_level",
    "load_type": "loading_type",
    "lb": "lower_bound",
    "lowerbound": "lower_bound",

    # content re-maps
    "exercise_description": "written_instructions",
    "description": "written_instructions",

    # keep these as-is when already canonical
    "name": "name",
    "main_muscles": "main_muscles",
    "secondary_muscles": "secondary_muscles",
    "movement": "movement",
    "lower_bound": "lower_bound",
    "level": "level",
    "difficulty": "difficulty",
    "equipment_type": "equipment_type",
    "equipment": "equipment",
    "prerequisite_exercise": "prerequisite_exercise",
    "variations": "variations",
    "regression": "regression",
    "progression": "progression",
    "loading_type": "loading_type",
    "risk_level": "risk_level",
    "exercise_purpose": "exercise_purpose",
    "force_type": "force_type",
    "pain_exclusions": "pain_exclusions",
    "Animation name": "animation",
    "written_instructions": "written_instructions",

    # keep extras
    "Type": "type",
    "type": "type",
    "Audio Script": "audio_script",
    "audio_script": "audio_script",
}

# If you still want to drop other admin/meta keys, list them here.
DROP_KEYS = set()

def to_canonical_key(raw_key: str) -> str | None:
    """
    Normalize a raw key, then map to canonical using alias table.
    Return None if the key should be dropped or not in canonical+extras.
    """
    k = base_normalize_key(raw_key)
    if k in DROP_KEYS:
        return None
    mapped = ALIASES_TO_CANON.get(k, k)
    return mapped if mapped in canonical_plus_extras else None

def normalize_value(v):
    if isinstance(v, dict):
        return {nk: normalize_value(nv)
                for k, nv in v.items()
                for nk in ([to_canonical_key(k)] if to_canonical_key(k) else [])}
    elif isinstance(v, list):
        return [normalize_value(i) for i in v]
    else:
        return v

def normalize_entry(entry: dict) -> dict:
    out = {}
    for k, v in entry.items():
        ck = to_canonical_key(k)
        if ck is None:
            continue
        out[ck] = normalize_value(v)

    # Optional: ensure *all* keys exist across records (including extras).
    # Uncomment if you want strict presence for every key:
    # for ck in canonical_plus_extras:
    #     if ck not in out:
    #         # Use [] for plural-ish fields, None otherwise (tweak as needed)
    #         out[ck] = [] if ck.endswith("s") else None
    return out

# --- Normalize all entries ---
dropped_key_counts = defaultdict(int)
seen_noncanon = set()

normalized = []
for e in src_data:
    out = {}
    for k, v in e.items():
        ck = to_canonical_key(k)
        if ck is None:
            basek = base_normalize_key(k)
            dropped_key_counts[basek] += 1
            seen_noncanon.add(basek)
            continue
        out[ck] = normalize_value(v)
    normalized.append(out)

# --- (Optional) quick report in console ---
if seen_noncanon:
    print("Dropped non-canonical keys (count):")
    for k in sorted(seen_noncanon):
        print(f"  {k}: {dropped_key_counts[k]}")

# --- Save result ---
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(normalized, f, indent=4, ensure_ascii=False)

# --- Sanity check: confirm exact key set equals canonical + extras (union across entries) ---
final_keys = set()
for e in normalized:
    final_keys.update(e.keys())

print("Extra (not in canonical+extras):", final_keys - canonical_plus_extras)
print("Missing (in canonical+extras but not produced):", canonical_plus_extras - final_keys)
