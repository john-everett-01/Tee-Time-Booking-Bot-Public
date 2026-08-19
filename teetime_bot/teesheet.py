from __future__ import annotations

from datetime import date

from lxml import html as lhtml

from .client import post_ajax
from .config import (
    TEE_SHEET_URL,
    TEE_TIME_AJAX_PARAMS,
    TEE_TIME_FORM_ID,
    TEE_TIME_NAMESPACE,
    VIEW_STATE_UPDATE_ID,
)
from .jsf import parse_form_state, parse_partial_response

DATE_FIELD_ID = f"{TEE_TIME_NAMESPACE}:teeTimeForm:j_idt104"
COURSE_FIELD_ID = f"{TEE_TIME_NAMESPACE}:teeTimeForm:j_idt101"
COURSE_VALUES = {"course_a": "1", "course_b": "2"}
COURSE_COURSES_ID = f"{TEE_TIME_NAMESPACE}:teeTimeForm:tee-sheet-courses"
COURSE_MESSAGE_ID = f"{TEE_TIME_NAMESPACE}:teeTimeForm:tee-sheet-message"


def fetch_tee_sheet(session) -> tuple[dict[str, str], str]:
    resp = session.get(TEE_SHEET_URL)
    resp.raise_for_status()
    return parse_form_state(resp.text, TEE_TIME_FORM_ID), resp.text


def select_date(session, state: dict[str, str], target: date) -> tuple[dict[str, str], str]:
    payload = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": DATE_FIELD_ID,
        "javax.faces.partial.execute": DATE_FIELD_ID,
        "javax.faces.partial.render": TEE_TIME_FORM_ID,
        "javax.faces.behavior.event": "dateSelect",
        "javax.faces.partial.event": "dateSelect",
        f"{DATE_FIELD_ID}_input": target.strftime("%m/%d/%Y"),
        f"{TEE_TIME_NAMESPACE}:teeTimeForm": TEE_TIME_FORM_ID,
        "javax.faces.encodedURL": state["javax.faces.encodedURL"],
        "javax.faces.ViewState": state["javax.faces.ViewState"],
    }
    resp = post_ajax(session, TEE_SHEET_URL, payload, params=TEE_TIME_AJAX_PARAMS)
    updates = parse_partial_response(resp.text)
    form_html = updates[TEE_TIME_FORM_ID]
    return parse_form_state(form_html, TEE_TIME_FORM_ID), form_html


def select_course(session, state: dict[str, str], course: str) -> tuple[dict[str, str], str]:
    payload = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": COURSE_FIELD_ID,
        "javax.faces.partial.execute": COURSE_FIELD_ID,
        "javax.faces.partial.render": f"{COURSE_COURSES_ID} {COURSE_MESSAGE_ID}",
        "javax.faces.behavior.event": "change",
        "javax.faces.partial.event": "change",
        COURSE_FIELD_ID: COURSE_VALUES[course],
        f"{TEE_TIME_NAMESPACE}:teeTimeForm": TEE_TIME_FORM_ID,
        "javax.faces.encodedURL": state["javax.faces.encodedURL"],
        "javax.faces.ViewState": state["javax.faces.ViewState"],
    }
    resp = post_ajax(session, TEE_SHEET_URL, payload, params=TEE_TIME_AJAX_PARAMS)
    updates = parse_partial_response(resp.text)
    new_state = dict(state)
    new_state["javax.faces.ViewState"] = updates[VIEW_STATE_UPDATE_ID]
    new_state[COURSE_FIELD_ID] = COURSE_VALUES[course]
    return new_state, updates[COURSE_COURSES_ID]


def list_slots(courses_html: str, course_index: int = 0) -> list[dict]:
    """All slots for a course in document order: [{"time": "09:30 AM", "status": "Empty"|"Reserved"|"ui-state-disabled", "reserve_button": id or None}]"""
    tree = lhtml.fromstring(courses_html)
    prefix = f"{TEE_TIME_FORM_ID}:teeTimeCourses:{course_index}:teeTimeSlots:"
    divs = tree.xpath(
        f'//div[starts-with(@id, "{prefix}") and '
        f'substring(@id, string-length(@id) - 10) = ":slotTeeDIV"]'
    )
    slots = []
    for div in divs:
        labels = div.xpath('.//label[@class="custom-time-label"]/text()')
        if not labels:
            continue
        status = div.get("class", "").strip()
        reserve_button = div.get("id")[: -len(":slotTeeDIV")] + ":reserve_button" if status == "Empty" else None
        slots.append({"time": labels[0].strip(), "status": status, "reserve_button": reserve_button})
    return slots


def find_slot(courses_html: str, target_time: str, course_index: int = 0) -> str | None:
    """target_time like '05:10 PM'. Returns the reserve_button field id, or None if not open."""
    for slot in list_slots(courses_html, course_index):
        if slot["time"] == target_time:
            return slot["reserve_button"]
    return None
