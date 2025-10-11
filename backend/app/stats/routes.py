from collections import defaultdict
from flask import Blueprint, jsonify
from app.db import db
from datetime import datetime
from .utils import MUSCLE_COLOR_MAP, get_muscle_group

stats_bp = Blueprint("stats", __name__, url_prefix="/stats")


# ---------------- LINE CHART ROUTE ----------------
# keep your dict
band_to_intensity = {
    'extra light': 1,
    'light': 2,
    'medium': 3,
    'heavy': 4,
    'extra heavy': 5,
}

# build the SQL VALUES rows once
band_values = ",\n                        ".join(
    [f"('{k.lower()}', {v})" for k, v in band_to_intensity.items()]
)

# A workout is “completed” iff any set equals 1 in its actual_exercise_records
COMPLETED_WORKOUT_FILTER = """
EXISTS (
    SELECT 1
    FROM actual_exercise_records aer_f,
         UNNEST(COALESCE(aer_f.sets, '{}')) AS s_f
    WHERE aer_f.actual_workout_id = aw.actual_workout_id
      AND s_f = 1
)
"""


@stats_bp.route("/line/<int:user_id>/<string:group_by>", methods=["GET"])
def get_line_stats(user_id, group_by):
    group_by = group_by.lower()

    # label formats for SQL (TO_CHAR) and simple keys per bucket
    if group_by == "day":
        sql_label_fmt = "YYYY-MM-DD"   # we’ll convert to weekday on the client if you want
        sql_key_fmt   = "YYYY-MM-DD"
        bucket_expr   = "DATE(w.date)"               # date bucket
        series_start_least = f"""
            LEAST(
                (
                    SELECT COALESCE(MIN(DATE(w.date)), CURRENT_DATE)
                    FROM workouts w
                    JOIN actual_workout aw ON aw.workout_id = w.workout_id
                    WHERE w.user_id = %s AND {COMPLETED_WORKOUT_FILTER}
                ),
                CURRENT_DATE - INTERVAL '6 days'
            )
        """
        series_step   = "INTERVAL '1 day'"
        series_cast   = "::date"
    elif group_by == "month":
        sql_label_fmt = "Mon YYYY"
        sql_key_fmt   = "YYYY-MM"
        bucket_expr   = "DATE_TRUNC('month', w.date)" # month bucket
        series_start_least = f"""
            DATE_TRUNC('month',
                LEAST(
                    (
                        SELECT COALESCE(DATE_TRUNC('month', MIN(w.date)), DATE_TRUNC('month', CURRENT_DATE))
                        FROM workouts w
                        JOIN actual_workout aw ON aw.workout_id = w.workout_id
                        WHERE w.user_id = %s AND {COMPLETED_WORKOUT_FILTER}
                    ),
                    CURRENT_DATE - INTERVAL '13 months'
                )
            )
        """
        series_step   = "INTERVAL '1 month'"
        series_cast   = ""  # keep as timestamp; we’ll TO_CHAR it anyway
    elif group_by == "year":
        sql_label_fmt = "YYYY"
        sql_key_fmt   = "YYYY"
        bucket_expr   = "DATE_TRUNC('year', w.date)"  # year bucket
        series_start_least = f"""
            DATE_TRUNC('year',
                (
                    SELECT COALESCE(DATE_TRUNC('year', MIN(w.date)), DATE_TRUNC('year', CURRENT_DATE))
                    FROM workouts w
                    JOIN actual_workout aw ON aw.workout_id = w.workout_id
                    WHERE w.user_id = %s AND {COMPLETED_WORKOUT_FILTER}
                )
            )
        """
        series_step   = "INTERVAL '1 year'"
        series_cast   = ""  # keep as timestamp
    else:
        return jsonify({"error": "Invalid group_by value"}), 400

    # One SQL fits all granularities, parameterized with the snippets above
    query = f"""
        WITH
        band_map(name, val) AS (
            VALUES
                {band_values}
        ),
        buckets AS (
            SELECT generate_series(
                {series_start_least},
                DATE_TRUNC('{group_by}', CURRENT_DATE),
                {series_step}
            ){series_cast} AS bucket
        ),
        per_bucket AS (
            SELECT
                {bucket_expr} AS bucket,
                SUM(
                    CASE
                        WHEN LOWER(TRIM(ae.exercise_type)) = 'gym equipment'
                             AND COALESCE(ae.intensity[idx.i], '') ~ '^[0-9]+(\\.[0-9]+)?$'
                        THEN (ae.intensity[idx.i])::DECIMAL
                             * COALESCE(ae.reps[idx.i], 0)
                             * COALESCE(ae.sets[idx.i], 0)

                        WHEN LOWER(TRIM(ae.exercise_type)) = 'resistance band'
                        THEN COALESCE(
                               CASE
                                 WHEN COALESCE(ae.intensity[idx.i], '') ~ '^[0-9]+(\\.[0-9]+)?$'
                                   THEN (ae.intensity[idx.i])::DECIMAL
                                 ELSE (SELECT val FROM band_map WHERE name = LOWER(ae.intensity[idx.i]))::DECIMAL
                               END,
                               0
                             )
                             * COALESCE(ae.reps[idx.i], 0)
                             * COALESCE(ae.sets[idx.i], 0)

                        WHEN LOWER(TRIM(ae.exercise_type)) = 'bodyweight'
                        THEN COALESCE(ae.reps[idx.i], 0)
                             * COALESCE(ae.sets[idx.i], 0)

                        WHEN LOWER(TRIM(ae.exercise_type)) = 'timed'
                        THEN COALESCE(ae.time[idx.i], 0)
                             * COALESCE(ae.sets[idx.i], 0)

                        ELSE 0
                    END
                ) AS total_volume
            FROM workouts w
            JOIN actual_workout aw ON w.workout_id = aw.workout_id
            JOIN actual_exercise_records ae ON aw.actual_workout_id = ae.actual_workout_id
            JOIN LATERAL (
                SELECT i
                FROM generate_series(
                    1,
                    GREATEST(
                        COALESCE(array_length(ae.reps, 1), 0),
                        COALESCE(array_length(ae.sets, 1), 0),
                        COALESCE(array_length(ae.intensity, 1), 0),
                        COALESCE(array_length(ae.time, 1), 0)
                    )
                ) AS i
            ) AS idx ON TRUE
            WHERE w.user_id = %s
              AND {COMPLETED_WORKOUT_FILTER}
            GROUP BY {bucket_expr}
        )
        SELECT
            TO_CHAR(b.bucket, '{sql_label_fmt}') AS label,
            COALESCE(p.total_volume, 0) AS total_volume,
            TO_CHAR(b.bucket, '{sql_key_fmt}') AS date_key
        FROM buckets b
        LEFT JOIN per_bucket p ON p.bucket = b.bucket
        ORDER BY b.bucket;
    """

    try:
        # note: only one user_id appears in the query (twice) via {series_start_least} and in per_bucket WHERE
        # But we placed %s twice in SQL; pass user_id for both occurrences:
        result = db.execute(query, (user_id, user_id), fetch=True) or []

        # No datetime parsing needed — we already have clean strings from SQL
        if group_by == "day":
            # label is 'YYYY-MM-DD' → convert to weekday tag for display
            # date is also the bucket key string you might use elsewhere
            line_data = [
                {
                    "label": datetime.strptime(row[0], "%Y-%m-%d").strftime("%a"),
                    "value": int(row[1]),
                    "date": row[2],  # 'YYYY-MM-DD'
                }
                for row in result
            ]
        elif group_by == "month":
            # label is 'Mon YYYY'; date_key is 'YYYY-MM'
            line_data = [
                {
                    "label": row[0].split()[0],  # 'Mon'
                    "value": int(row[1]),
                    "date": row[2],             # 'YYYY-MM'
                }
                for row in result
            ]
        else:  # year
            # label is 'YYYY'; date_key is 'YYYY'
            fetched = {row[2]: int(row[1]) for row in result}  # {'2023': vol, ...}
            existing_years = sorted([int(y) for y in fetched.keys()])
            current_year = datetime.now().year
            min_year = existing_years[0] if existing_years else current_year
            desired_years = list(range(min_year - max(0, 7 - len(existing_years)), current_year + 1))
            if len(desired_years) < 7:
                while len(desired_years) < 7:
                    desired_years.insert(0, desired_years[0] - 1)

            line_data = [
                {
                    "label": str(year),
                    "value": int(fetched.get(str(year), 0)),
                    "date": str(year),
                }
                for year in desired_years
            ]

        return jsonify(line_data), 200

    except Exception as e:
        return jsonify({"error": "Line chart query failed", "details": str(e)}), 500
    

# ---------------- BAR CHART ROUTE ----------------
@stats_bp.route("/bar/<int:user_id>/<string:group_by>", methods=["GET"])
def get_bar_stats(user_id, group_by):
    group_by = group_by.lower()

    if group_by == "day":
        label_format = "YYYY-MM-DD"
        interval = "1 day"
        date_format_str = "%Y-%m-%d"
    elif group_by == "month":
        label_format = "Mon YYYY"
        interval = "1 month"
        date_format_str = "%Y-%m"
    elif group_by == "year":
        label_format = "YYYY"
        interval = "1 year"
        date_format_str = "YYYY"
    else:
        return jsonify({"error": "Invalid group_by value"}), 400

    try:
        if group_by == "day":
            query = f"""
                WITH date_range AS (
                    SELECT generate_series(
                        LEAST(
                            (
                                SELECT COALESCE(MIN(DATE(w.date)), CURRENT_DATE)
                                FROM workouts w
                                JOIN actual_workout aw ON aw.workout_id = w.workout_id
                                WHERE w.user_id = %s AND {COMPLETED_WORKOUT_FILTER}
                            ),
                            CURRENT_DATE - INTERVAL '6 days'
                        ),
                        CURRENT_DATE,
                        INTERVAL '{interval}'
                    )::DATE AS workout_date
                ),
                daily_counts AS (
                    SELECT DATE(w.date) AS workout_date,
                           COUNT(DISTINCT w.workout_id) AS count
                    FROM workouts w
                    JOIN actual_workout aw ON aw.workout_id = w.workout_id
                    WHERE w.user_id = %s
                      AND {COMPLETED_WORKOUT_FILTER}
                    GROUP BY workout_date
                )
                SELECT TO_CHAR(d.workout_date, '{label_format}') AS label,
                       COALESCE(dc.count, 0) AS count
                FROM date_range d
                LEFT JOIN daily_counts dc ON d.workout_date = dc.workout_date
                ORDER BY d.workout_date;
            """
            result = db.execute(query, (user_id, user_id), fetch=True)
            bar_data = [
                {
                    "label": datetime.strptime(row[0], "%Y-%m-%d").strftime("%a"),
                    "value": int(row[1]),
                    "date": row[0],
                    "frontColor": "#FF69B4"
                }
                for row in result
            ]

        elif group_by == "month":
            query = f"""
                WITH month_range AS (
                    SELECT generate_series(
                        DATE_TRUNC('month',
                            LEAST(
                                (
                                    SELECT COALESCE(DATE_TRUNC('month', MIN(w.date)), DATE_TRUNC('month', CURRENT_DATE))
                                    FROM workouts w
                                    JOIN actual_workout aw ON aw.workout_id = w.workout_id
                                    WHERE w.user_id = %s AND {COMPLETED_WORKOUT_FILTER}
                                ),
                                CURRENT_DATE - INTERVAL '13 months'
                            )
                        ),
                        DATE_TRUNC('month', CURRENT_DATE),
                        INTERVAL '1 month'
                    ) AS month_start
                ),
                monthly_counts AS (
                    SELECT DATE_TRUNC('month', w.date) AS month_start,
                           COUNT(DISTINCT w.date) AS count
                    FROM workouts w
                    JOIN actual_workout aw ON aw.workout_id = w.workout_id
                    WHERE w.user_id = %s
                      AND {COMPLETED_WORKOUT_FILTER}
                    GROUP BY month_start
                )
                SELECT TO_CHAR(m.month_start, '{label_format}') AS label,
                       COALESCE(mc.count, 0) AS count,
                       TO_CHAR(m.month_start, 'YYYY-MM') AS date
                FROM month_range m
                LEFT JOIN monthly_counts mc ON m.month_start = mc.month_start
                ORDER BY m.month_start;
            """
            result = db.execute(query, (user_id, user_id), fetch=True)
            bar_data = [
                {
                    "label": datetime.strptime(row[2], "%Y-%m").strftime("%b"),
                    "value": int(row[1]),
                    "date": row[0],
                    "frontColor": "#FF69B4"
                }
                for row in result
            ]

        elif group_by == "year":
            query = f"""
                WITH year_range AS (
                    SELECT generate_series(
                        DATE_TRUNC('year',
                            (
                                SELECT COALESCE(DATE_TRUNC('year', MIN(w.date)), DATE_TRUNC('year', CURRENT_DATE))
                                FROM workouts w
                                JOIN actual_workout aw ON aw.workout_id = w.workout_id
                                WHERE w.user_id = %s AND {COMPLETED_WORKOUT_FILTER}
                            )
                        ),
                        DATE_TRUNC('year', CURRENT_DATE),
                        INTERVAL '1 year'
                    ) AS year_start
                ),
                yearly_counts AS (
                    SELECT DATE_TRUNC('year', w.date) AS year_start,
                           COUNT(DISTINCT w.date) AS count
                    FROM workouts w
                    JOIN actual_workout aw ON aw.workout_id = w.workout_id
                    WHERE w.user_id = %s
                      AND {COMPLETED_WORKOUT_FILTER}
                    GROUP BY year_start
                )
                SELECT TO_CHAR(y.year_start, '{label_format}') AS label,
                       COALESCE(yc.count, 0) AS count,
                       EXTRACT(YEAR FROM y.year_start)::int AS year
                FROM year_range y
                LEFT JOIN yearly_counts yc ON y.year_start = yc.year_start
                ORDER BY y.year_start;
            """
            result = db.execute(query, (user_id, user_id), fetch=True)

            fetched_dict = {row[0]: int(row[1]) for row in result}
            existing_years = sorted([int(year) for year in fetched_dict.keys()])
            current_year = datetime.now().year
            min_year = existing_years[0] if existing_years else current_year

            desired_years = list(range(min_year - max(0, 7 - len(existing_years)), current_year + 1))
            while len(desired_years) < 7:
                desired_years.insert(0, desired_years[0] - 1)

            bar_data = [
                {
                    "label": str(year),
                    "value": fetched_dict.get(str(year), 0),
                    "date": str(year),
                    "frontColor": "#FF69B4"
                }
                for year in desired_years
            ]

        return jsonify(bar_data), 200

    except Exception as e:
        return jsonify({"error": "Bar chart query failed", "details": str(e)}), 500


# ---------------- PIE CHART ROUTE ----------------
@stats_bp.route("/pie/<int:user_id>", methods=["GET"])
def get_pie_stats(user_id):
    try:
        # Per-set volume with robust indexing + all exercise types.
        # Then unnest muscles and APPORTION the set volume equally across them.
        query = f"""
            WITH
            band_map(name, val) AS (
                VALUES
                    {band_values}
            ),
            per_set AS (
                SELECT
                    e.exercise_id,
                    /* robust index 1..maxlen across arrays */
                    idx.i AS i,
                    /* compute volume per set i by type */
                    CASE
                        WHEN LOWER(TRIM(ae.exercise_type)) = 'gym equipment'
                             AND COALESCE(ae.intensity[idx.i], '') ~ '^[0-9]+(\\.[0-9]+)?$'
                          THEN (ae.intensity[idx.i])::DECIMAL
                               * COALESCE(ae.reps[idx.i], 0)
                               * COALESCE(ae.sets[idx.i], 0)

                        WHEN LOWER(TRIM(ae.exercise_type)) = 'resistance band'
                          THEN COALESCE(
                                 CASE
                                   WHEN COALESCE(ae.intensity[idx.i], '') ~ '^[0-9]+(\\.[0-9]+)?$'
                                     THEN (ae.intensity[idx.i])::DECIMAL
                                   ELSE (SELECT val FROM band_map WHERE name = LOWER(ae.intensity[idx.i]))::DECIMAL
                                 END,
                                 0
                               )
                               * COALESCE(ae.reps[idx.i], 0)
                               * COALESCE(ae.sets[idx.i], 0)

                        WHEN LOWER(TRIM(ae.exercise_type)) = 'bodyweight'
                          THEN COALESCE(ae.reps[idx.i], 0)
                               * COALESCE(ae.sets[idx.i], 0)

                        WHEN LOWER(TRIM(ae.exercise_type)) = 'timed'
                          THEN COALESCE(ae.time[idx.i], 0)
                               * COALESCE(ae.sets[idx.i], 0)

                        ELSE 0
                    END AS set_volume,
                    /* combined muscles array and its length for apportioning */
                    (e.main_muscles || e.secondary_muscles) AS muscles,
                    GREATEST(
                        COALESCE(array_length(e.main_muscles, 1), 0)
                      + COALESCE(array_length(e.secondary_muscles, 1), 0),
                        1
                    ) AS n_muscles
                FROM workouts w
                JOIN actual_workout aw ON w.workout_id = aw.workout_id
                JOIN actual_exercise_records ae ON aw.actual_workout_id = ae.actual_workout_id
                JOIN Exercises e ON ae.exercise_id = e.exercise_id
                /* robust index across per-set arrays */
                JOIN LATERAL (
                    SELECT i
                    FROM generate_series(
                        1,
                        GREATEST(
                            COALESCE(array_length(ae.reps, 1), 0),
                            COALESCE(array_length(ae.sets, 1), 0),
                            COALESCE(array_length(ae.intensity, 1), 0),
                            COALESCE(array_length(ae.time, 1), 0)
                        )
                    ) AS i
                ) AS idx ON TRUE
                WHERE w.user_id = %s
                  AND EXISTS (
                      SELECT 1
                      FROM actual_exercise_records aer2,
                           UNNEST(COALESCE(aer2.sets, '{{}}')) AS s2
                      WHERE aer2.actual_workout_id = aw.actual_workout_id
                        AND s2 = 1
                  )
            ),
            per_set_muscle AS (
                /* Apportion: split the set's volume equally across its listed muscles */
                SELECT
                    LOWER(TRIM(unnest_muscle)) AS muscle,
                    (set_volume / NULLIF(n_muscles, 0)) AS apportioned_volume
                FROM per_set
                /* UNNEST after volume calc so we can apportion */
                LEFT JOIN LATERAL UNNEST(muscles) AS u(unnest_muscle) ON TRUE
            )
            SELECT muscle, SUM(apportioned_volume) AS volume
            FROM per_set_muscle
            WHERE muscle IS NOT NULL AND muscle <> ''
            GROUP BY muscle
            HAVING SUM(apportioned_volume) <> 0;
        """

        results = db.execute(query, (user_id,), fetch=True)

        group_volumes = defaultdict(float)
        for muscle, volume in (results or []):
            group = get_muscle_group(muscle)
            group_volumes[group] += float(volume or 0.0)

        total_volume = sum(group_volumes.values()) or 1.0

        pie_data = [
            {
                "label": group,
                "value": round((volume / total_volume) * 100),
                "color": MUSCLE_COLOR_MAP.get(group, {}).get("color", "#888"),
                "gradientCenterColor": MUSCLE_COLOR_MAP.get(group, {}).get("gradientCenterColor", "#444")
            }
            for group, volume in sorted(group_volumes.items(), key=lambda item: item[1], reverse=True)[:6]
        ]

        return jsonify({"pieData": pie_data, "pieDataVolume": total_volume}), 200

    except Exception as e:
        return jsonify({"error": "Pie chart query failed", "details": str(e)}), 500