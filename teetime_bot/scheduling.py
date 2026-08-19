# Release always lands on the same calendar day the cron job fires (that's why the cron
# schedule exists) — so release_datetime is always "today at 7:00 AM"; only which future
# date gets targeted, and which time preference applies, changes by mode.

from __future__ import annotations

from datetime import date, datetime, time, timedelta

RELEASE_TIME = time(7, 0)
SATURDAY_TARGET_TIME = time(9, 30)
SUNDAY_WINDOW = (time(7, 30), time(8, 30))
COURSE_PRIORITY = ["course_a", "course_b"]


def compute_run_plan(today: date, test_mode: bool = False) -> dict:
    release_datetime = datetime.combine(today, RELEASE_TIME)

    if test_mode:
        return {
            "mode": "test",
            "target_date": today + timedelta(days=14),
            "release_datetime": release_datetime,
            "target_time": None,
            "window": SUNDAY_WINDOW,
            "course_priority": COURSE_PRIORITY,
        }

    weekday = today.weekday()  # Monday=0 ... Sunday=6
    if weekday == 0:  # Monday -> Saturday
        return {
            "mode": "saturday",
            "target_date": today + timedelta(days=5),
            "release_datetime": release_datetime,
            "target_time": SATURDAY_TARGET_TIME,
            "window": None,
            "course_priority": COURSE_PRIORITY,
        }
    if weekday == 1:  # Tuesday -> Sunday
        return {
            "mode": "sunday",
            "target_date": today + timedelta(days=5),
            "release_datetime": release_datetime,
            "target_time": None,
            "window": SUNDAY_WINDOW,
            "course_priority": COURSE_PRIORITY,
        }
    raise ValueError(
        f"no scheduled run defined for weekday {weekday} (cron only runs Monday/Tuesday; use test_mode otherwise)"
    )
