#DICTIONARY OF PRESELECTED EQUIPMENT BASED ON THE 'VENUE' THAT THE USER SELECTS. (KEY: Venue, VALUES: equipment(list), available_weights(nested dictionary))

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
                           55:2, 60:2, 65:2, 70:2, 75:2, 80:2, 85:2, 90:2, 95:2, 100:2},

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