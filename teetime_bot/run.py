from __future__ import annotations

import argparse
import traceback
from datetime import datetime, timedelta

from . import auth, book, hold, players, teesheet, timesync, waterfall
from .client import make_session
from .config import (
    LAST_RESORT_PARTNER,
    LAST_RESORT_TIME_STR,
    PRIMARY_PARTNER_MAX_ATTEMPTS,
    PRIMARY_PARTNERS,
)
from .notify import send_notification
from .scheduling import compute_run_plan

LAST_RESORT_TIME = datetime.strptime(LAST_RESORT_TIME_STR, "%H:%M").time()
LAST_RESORT_COURSE_PRIORITY = ["course_a", "course_b"]


def _partner_attempts(names: list[str], max_attempts: int) -> list[str]:
    if not names:
        return []
    return [names[i % len(names)] for i in range(max_attempts)]


def _find_slot(session, target_date, target_time, window, course_priority):
    state, form_html = teesheet.fetch_tee_sheet(session)
    state, form_html = teesheet.select_date(session, state, target_date)
    for course in course_priority:
        courses_html = form_html if course == "course_a" else None
        if courses_html is None:
            state, courses_html = teesheet.select_course(session, state, course)
        slots = teesheet.list_slots(courses_html)
        best = waterfall.find_best_slot(slots, target_date, target_time=target_time, window=window)
        if best is not None:
            return state, course, best
    return None, None, None


def _try_partners(session, hold_state: dict[str, str], names: list[str], mode: str):
    # Registered-guest vs. member searches hit different pools (confirmed live), but
    # switching modes on one hold doesn't cleanly reset — even re-clicking reserve on the
    # same slot leaves row 1 stuck in whichever mode was touched first. So each hold uses
    # exactly one mode for its whole partner search; the two modes get separate fresh holds
    # (primary strategy uses "guest" mode for the primary partner names, last resort uses
    # "member" mode for the last-resort partner name, on its own hold — never both on the
    # same one).
    enable = players.enable_registered_guest_search if mode == "guest" else players.enable_member_search
    search_state, _ = enable(session, hold_state)
    for name in names:
        candidates = players.search_player(session, search_state, 1, name)
        if candidates:
            new_state, _ = players.select_player(session, search_state, 1, candidates[0])
            return new_state, name
    return None, None


def execute_booking(session, plan: dict) -> dict:
    state, course, chosen_slot = _find_slot(
        session, plan["target_date"], plan["target_time"], plan["window"], plan["course_priority"]
    )

    if chosen_slot is not None:
        hold_state, _ = hold.create_hold(session, state, chosen_slot["reserve_button"])
        attempts = _partner_attempts(PRIMARY_PARTNERS, PRIMARY_PARTNER_MAX_ATTEMPTS)
        booked_state, partner = _try_partners(session, hold_state, attempts, mode="guest")
        if booked_state is not None:
            success, _, book_html = book.book_now(session, booked_state)
            if success:
                return {
                    "success": True,
                    "strategy": "primary",
                    "mode": plan["mode"],
                    "course": course,
                    "slot_time": chosen_slot["time"],
                    "partner": partner,
                    "confirmation": book.parse_confirmation(book_html),
                }

    # Primary strategy exhausted (no slot, or no primary partner found for that slot) —
    # solo booking isn't accepted by this club's system, so fall through to last resort
    # rather than ever attempting to book without a partner.
    state, course, chosen_slot = _find_slot(
        session, plan["target_date"], LAST_RESORT_TIME, None, LAST_RESORT_COURSE_PRIORITY
    )
    if chosen_slot is not None:
        hold_state, _ = hold.create_hold(session, state, chosen_slot["reserve_button"])
        booked_state, partner = _try_partners(session, hold_state, [LAST_RESORT_PARTNER], mode="member")
        if booked_state is not None:
            success, _, book_html = book.book_now(session, booked_state)
            if success:
                return {
                    "success": True,
                    "strategy": "last_resort",
                    "mode": plan["mode"],
                    "course": course,
                    "slot_time": chosen_slot["time"],
                    "partner": partner,
                    "confirmation": book.parse_confirmation(book_html),
                }

    return {
        "success": False,
        "reason": "no_booking_possible",
        "mode": plan["mode"],
        "target_date": plan["target_date"],
    }


def run(test_mode: bool = False, headless: bool = True) -> dict:
    offset = timesync.ntp_offset_seconds()
    now = timesync.make_now(offset)

    plan = compute_run_plan(now().date(), test_mode=test_mode)

    if not test_mode:
        timesync.sleep_until(plan["release_datetime"] - timedelta(minutes=2), now)

    cookies = auth.login(headless=headless)
    session = make_session(cookies)

    if not test_mode:
        timesync.sleep_until(plan["release_datetime"], now)

    return execute_booking(session, plan)


def _format_failure_notification(result: dict) -> tuple[str, str]:
    reason = result.get("reason", "unknown_failure")
    subject = f"Tee time booking FAILED ({reason})"
    body = f"Mode: {result.get('mode')}\nReason: {reason}\nDetails: {result}\n"
    return subject, body


def _format_success_log(result: dict) -> tuple[str, str]:
    c = result["confirmation"] or {}
    subject = f"Tee time booked: {c.get('course')} {c.get('date')} {c.get('time')}"
    body = (
        f"Strategy: {result.get('strategy')}\n"
        f"Course: {c.get('course')}\n"
        f"Date: {c.get('date')}\n"
        f"Time: {c.get('time')}\n"
        f"Tee off hole: {c.get('tee_off')}\n"
        f"Players: {', '.join(c.get('players', []))}\n"
    )
    return subject, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="test mode: target = today+14 days, runs immediately")
    parser.add_argument("--headed", action="store_true", help="run login browser headed (for debugging)")
    args = parser.parse_args()

    try:
        result = run(test_mode=args.test, headless=not args.headed)
    except Exception as exc:
        subject = "Tee time bot CRASHED"
        body = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        try:
            send_notification(subject, body)
        except Exception:
            pass
        raise

    # The club already emails on a successful booking, so this bot only notifies on
    # failure — a crash or "no slot possible" has no other signal, since nothing happened
    # on the club's end for them to send an email about.
    if result["success"]:
        subject, body = _format_success_log(result)
    else:
        subject, body = _format_failure_notification(result)
        try:
            send_notification(subject, body)
        except Exception as exc:
            print(f"WARNING: booking failed AND notification failed: {exc}")
    print(subject)
    print(body)


if __name__ == "__main__":
    main()
