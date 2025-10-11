from datetime import date, timedelta, datetime
from collections import defaultdict

def group_workouts_by_week(workout_dates):
    """
    Groups a list of workout dates by ISO week. Returns a dict:
    {(year, week_number): count}
    """
    week_counts = defaultdict(int)
    for date in workout_dates:
        year, week_num, _ = date.isocalendar()  # (year, week, weekday)
        week_counts[(year, week_num)] += 1
    return week_counts

def _wk_add(year_week, delta_weeks):
    y, w = year_week
    d = date.fromisocalendar(y, w, 1) + timedelta(weeks=delta_weeks)
    iy, iw, _ = d.isocalendar()
    return (iy, iw)

def get_consecutive_streaks(week_counts, required_frequency):
    """
    Returns (current_streak, record_streak) where a 'hit' week means
    count >= required_frequency *for that ISO week*.

    Current streak:
      - If the *current ISO week* already meets the goal, count consecutive
        hit weeks ending at the current week.
      - Else (mid-week or not yet on pace), count consecutive hit weeks
        ending at the *previous* ISO week.
      - If the previous week didn't hit, current_streak = 0.

    Record streak:
      - Longest run of consecutive hit weeks anywhere in history.
    """
    if not week_counts:
        return 0, 0

    # Weeks that "hit" the goal
    hit_weeks = {wk for wk, c in week_counts.items() if c >= required_frequency}

    if not hit_weeks:
        return 0, 0

    # ----- Record streak: longest run of consecutive hit weeks -----
    # Sort hit weeks by actual calendar order and scan for consecutive runs.
    hit_weeks_sorted = sorted(
        hit_weeks,
        key=lambda yw: date.fromisocalendar(yw[0], yw[1], 1)
    )
    record_streak = 0
    run = 0
    prev = None
    for wk in hit_weeks_sorted:
        if prev is None or wk != _wk_add(prev, +1):
            run = 1
        else:
            run += 1
        record_streak = max(record_streak, run)
        prev = wk

    # ----- Current streak: trailing up to this week if hit, else last week -----
    today = datetime.today()
    current_week = today.isocalendar()[:2]         # (year, week)
    anchor = current_week if current_week in hit_weeks else _wk_add(current_week, -1)

    current_streak = 0
    wk = anchor
    while wk in hit_weeks:
        current_streak += 1
        wk = _wk_add(wk, -1)

    return current_streak, record_streak