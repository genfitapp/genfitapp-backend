from __future__ import annotations
from typing import Optional, Tuple, Dict, Any
from collections import defaultdict
import re

#DICTIONARY OF PRESELECTED EQUIPMENT BASED ON THE 'Gym Setup' THAT THE USER
#SELECTS. (KEY: Gym Setup, VALUES: equipment(list), available_weights(nested
#dictionary))

INDEX_TO_SETUP = {
    1: "Fully equipped gym",
    2: "Moderately equipped gym",
    3: "Home gym",
    4: "Minimal equipment setup",
    5: "No setup",
}

gym_equipment = {
    "Fully equipped gym": {
        "equipment": [
            "2 Ankle strap",
            "1 Ankle strap",
            "2 Dumbbell",
            "1 Dumbbell",
            "2 Kettlebell",
            "1 Kettlebell",
            "2 Single grip handle",
            "1 Single grip handle",
            "45-degree leg press machine",
            "Adjustable pulley",
            "Assisted dip machine",
            "Assisted pull up machine",
            "Back extension station",
            "Bench",
            "Chest supported T-bar",
            "Curl bar",
            "Decline bench",
            "Dip machine",
            "EZ curl bar",
            "Fixed weight bar",
            "Flat chest press machine",
            "Functional trainer cable machine",
            "Hack squat machine",
            "Hex trap bar",
            "High pulley",
            "Horizontal leg press machine",
            "Incline bench",
            "Incline chest press machine",
            "Landmine base",
            "Lat pulldown cable machine",
            "Low pulley",
            "Lying down hamstring curl machine",
            "Mini loop band",
            "None",
            "Olympic barbell",
            "PVC pipe",
            "Parallel bars",
            "Pec deck machine",
            "Plate loaded lat pull down machine",
            "Plated row machine",
            "Platform",
            "Plyometric box",
            "Power tower",
            "Preacher bench",
            "Pull up bar",
            "Pull up station",
            "Pullover machine",
            "Quad extension machine",
            "Rope",
            "Seated abduction machine",
            "Seated adduction machine",
            "Seated cable pec fly machine",
            "Seated cable row machine",
            "Seated chest press machine",
            "Seated hamstring curl machine",
            "Seated lateral raise machine",
            "Seated overhead tricep extension machine",
            "Seated plated calf machine",
            "Seated shoulder press machine",
            "Seated tricep extension machine",
            "Smith machine",
            "Stability ball",
            "Standing lateral raise machine",
            "Standing plated calf machine",
            "Straight bar",
            "TRX",
            "Triceps V-bar",
            "Weight plates"
            ],

        "available_weights": {
            "Dumbbells":  {5:2, 7.5:2, 10:2, 12.5:2, 15:2, 17.5:2, 20:2, 25:2, 30:2, 35:2, 40:2, 45:2, 50:2,
                           55:2, 60:2, 65:2, 70:2, 75:2, 80:2, 85:2, 90:2, 95:2, 100:2, 105:2, 110:2, 115:2, 120:2},

            "Kettlebells": {5:2, 10:2, 15:2, 20:2, 25:2, 30:2, 35:2, 40:2, 45:2, 50:2},

            "Fixed weight bar": {10:1, 15:1, 20:1, 25:1, 30:1, 35:1, 40:1, 45:1, 50:1, 55:1, 60:1, 65:1, 70:1, 75:1, 80:1, 85:1, 90:1, 95:1, 100:1},

            "Mini loop band": {"Extra Light":1, "Light":1, "Medium":1, "Heavy":1, "Extra Heavy":1}

            },

    },

    "Moderately equipped gym":{
        "equipment": [
            "2 Ankle strap",
            "1 Ankle strap",
            "2 Dumbbell",
            "1 Dumbbell",
            "2 Single grip handle",
            "1 Single grip handle",
            "Bench",
            "Curl bar",
            "Decline bench",
            "EZ curl bar",
            "Fixed weight bar",
            "Functional trainer cable machine",
            "Horizontal leg press machine",
            "Incline bench",
            "Lat pulldown cable machine",
            "Lying down hamstring curl machine",
            "Mini loop band",
            "None",
            "Olympic barbell",
            "Platform",
            "Plyometric box",
            "Pull up station",
            "Quad extension machine",
            "Rope",
            "Seated cable row machine",
            "Seated chest press machine",
            "Smith machine",
            "Straight bar",
            "Triceps V-bar",
            "Weight plates"
            ],

        "available_weights": {
            "Dumbbells":  {5:2, 7.5:2, 10:2, 12.5:2, 15:2, 17.5:2, 20:2, 25:2, 30:2, 35:2, 40:2, 45:2, 50:2,
                           55:2, 60:2},

            "Fixed weight bar": {10:1, 20:1, 30:1, 40:1, 50:1, 60:1},

            "Mini loop band": {"Extra Light":1, "Light":1, "Medium":1, "Heavy":1, "Extra Heavy":1}

            }
    },

    "Home gym": {
        "equipment": [
            "2 Ankle strap",
            "1 Ankle strap",
            "2 Dumbbell",
            "1 Dumbbell",
            "2 Kettlebell",
            "1 Kettlebell",
            "2 Loop band",
            "1 Loop band",
            "2 Single grip handle",
            "1 Single grip handle",
            "Adjustable pulley",
            "Assisted dip machine",
            "Curl bar",
            "Decline bench",
            "EZ curl bar",
            "Handle band",
            "Incline bench",
            "Landmine base",
            "Mini loop band",
            "None",
            "Olympic barbell",
            "Parallel bars",
            "Platform",
            "Plyometric box",
            "Pull up bar",
            "Resistance band bar",
            "Rope",
            "Stability ball",
            "Straight bar",
            "TRX",
            "Triceps V-bar",
            "Weight plates"
            ],

        "available_weights": {
            "Dumbbells":  {5:2, 7.5:2, 10:2, 12.5:2, 15:2, 17.5:2, 20:2, 25:2, 30:2, 35:2, 40:2, 45:2, 50:2,
                           55:2, 60:2},

            "Kettlebells": {5:2, 10:2, 15:2, 20:2, 25:2, 30:2, 35:2, 40:2, 45:2, 50:2},

            "Mini loop band": {"Extra Light":1, "Light":1, "Medium":1, "Heavy":1, "Extra Heavy":1},

            "Loop band": {"Extra Light":2, "Light":2, "Medium":2, "Heavy":2, "Extra Heavy":2},

            "Handle band": {"Extra Light":1, "Light":1, "Medium":1, "Heavy":1, "Extra Heavy":1}

            }
    },

    "Minimal equipment setup": {
        "equipment": [
            "2 Ankle strap",
            "1 Ankle strap",
            "2 Dumbbell",
            "1 Dumbbell",
            "2 Loop band",
            "1 Loop band",
            "2 Single grip handle",
            "1 Single grip handle",
            "Handle band",
            "Mini loop band",
            "None",
            "Platform",
            "Resistance band bar",
            "Rope",
            "Stability ball"
            ],

        "available_weights": {
            "Dumbbells":  {5:2, 7.5:2, 10:2, 12.5:2, 15:2, 17.5:2, 20:2, 25:2, 30:2, 35:2},

            "Mini loop band": {"Extra Light":1, "Light":1, "Medium":1, "Heavy":1, "Extra Heavy":1},

            "Loop band": {"Extra Light":2, "Light":2, "Medium":2, "Heavy":2, "Extra Heavy":2},

            "Handle band": {"Extra Light":1, "Light":1, "Medium":1, "Heavy":1, "Extra Heavy":1}
        }
    },

    "No setup": {
        "equipment": ["None"],
        "available_weights": {},
    }
}


def parse_qty_and_name(raw: str) -> Tuple[Optional[int], Optional[str]]:
    """
    '2 Dumbbell' -> (2, 'Dumbbell')
    'Bench'      -> (1, 'Bench')
    'None'       -> (None, None)  # skip
    """
    s = (raw or "").strip()
    if not s or s.lower() == "none":
        return None, None
    m = re.match(r"^\s*(\d+)\s+(.+)$", s)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return 1, s

def normalize_key(s: str) -> str:
    """Loose singular, lowercased key for matching 'Dumbbell' vs 'Dumbbells'."""
    s = (s or "").strip().lower()
    return s[:-1] if s.endswith("s") else s

# ---------- DB helpers ----------

def ensure_equipment_id(db, name: str, weight_resistance_time: Optional[str] = None) -> int:
    """
    Ensure an equipment row exists and return its id.
    Creates (name, weight_resistance_time) if missing.
    """
    if weight_resistance_time is None or str(weight_resistance_time).strip() == "":
        sel = """
            SELECT equipment_id
              FROM equipment
             WHERE name = %s
               AND (weight_resistance_time IS NULL OR weight_resistance_time = '')
             LIMIT 1;
        """
        row = db.execute(sel, (name,), fetch=True)
        if row:
            return row[0][0]
        ins = """
            INSERT INTO equipment (name, weight_resistance_time)
                 VALUES (%s, NULL)
              RETURNING equipment_id;
        """
        return db.execute(ins, (name,), fetch=True)[0][0]
    else:
        wrt = str(weight_resistance_time)
        sel = """
            SELECT equipment_id
              FROM equipment
             WHERE name = %s
               AND weight_resistance_time = %s
             LIMIT 1;
        """
        row = db.execute(sel, (name, wrt), fetch=True)
        if row:
            return row[0][0]
        ins = """
            INSERT INTO equipment (name, weight_resistance_time)
                 VALUES (%s, %s)
              RETURNING equipment_id;
        """
        return db.execute(ins, (name, wrt), fetch=True)[0][0]

def upsert_venue_equipment(db, venue_id: int, equipment_id: int, quantity: int) -> None:
    """
    Insert or update quantity for a (venue, equipment) pair.
    """
    sel = """
        SELECT venue_equipment_id
          FROM Venue_equipment
         WHERE venue_id = %s
           AND equipment_id = %s
         LIMIT 1;
    """
    row = db.execute(sel, (venue_id, equipment_id), fetch=True)
    if row:
        upd = "UPDATE Venue_equipment SET quantity = %s WHERE venue_equipment_id = %s;"
        db.execute(upd, (int(quantity), row[0][0]))
    else:
        ins = "INSERT INTO Venue_equipment (venue_id, equipment_id, quantity) VALUES (%s, %s, %s);"
        db.execute(ins, (venue_id, equipment_id, int(quantity)))

# ---------- Public API used by routes ----------

def set_gym_setup(db, venue_id: int, setup_index: int) -> None:
    """
    Just updates Venues.gym_setup. Validation should be done in the route.
    """
    db.execute("UPDATE Venues SET gym_setup = %s WHERE venue_id = %s;", (setup_index, venue_id))

def seed_venue_equipment_from_setup(
    db,
    *,
    venue_id: int,
    setup_index: int,
    index_to_setup: Dict[int, str],
    gym_equipment: Dict[str, Dict[str, Any]],
    replace: bool = False,
) -> Dict[str, int]:
    """
    Populate Venue_equipment for a venue using the provided setup dictionaries.

    - If replace=True, clears existing venue equipment first.
    - Skips generic items that have weighted variants (e.g., skip 'Dumbbell' if 'Dumbbells' in available_weights).
    - Consolidates duplicate base items by taking the MAX quantity seen.

    Returns a small summary dict.
    """
    setup_name = index_to_setup.get(setup_index)
    if not setup_name:
        raise ValueError(f"Unknown setup index: {setup_index}")

    cfg = gym_equipment.get(setup_name, {})
    base_list = cfg.get("equipment") or []
    weighted = cfg.get("available_weights") or {}

    if replace:
        db.execute("DELETE FROM Venue_equipment WHERE venue_id = %s;", (venue_id,))

    # Skip base items that are covered by weighted keys (e.g., 'Dumbbells')
    weighted_keys_norm = {normalize_key(k) for k in weighted.keys()}
    base_counts: Dict[str, int] = defaultdict(int)
    print("base")
    for raw in base_list:
        qty, name = parse_qty_and_name(raw)
        if not name or qty is None:
            continue
        if normalize_key(name) in weighted_keys_norm:
            continue
        # Keep max of duplicates (e.g., '1 Ankle strap' and '2 Ankle strap')
        base_counts[name] = max(base_counts[name], int(qty))

    inserts = 0
    print('t')
    # Insert/Update base items (no weight_resistance_time)
    for name, qty in base_counts.items():
        print("1 -> ", name, qty)
        eq_id = ensure_equipment_id(db, name, None)
        upsert_venue_equipment(db, venue_id, eq_id, qty)
        inserts += 1

    print('n')
    # Insert/Update weighted variants (e.g., Dumbbells 5..100, bands 'Light'..)
    for name, variants in weighted.items():
        for wrt, qty in (variants or {}).items():
            print(f"name: {name} wrt: {wrt} qty: {qty}")
            eq_id = ensure_equipment_id(db, name, str(wrt))
            upsert_venue_equipment(db, venue_id, eq_id, int(qty))
            inserts += 1

    return {
        "base_items": len(base_counts),
        "weighted_items": sum(len(variants or {}) for variants in weighted.values()),
        "total_upserts": inserts,
    }
