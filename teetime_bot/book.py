from __future__ import annotations

from lxml import html as lhtml

from .client import post_ajax
from .config import TEE_SHEET_URL, TEE_TIME_AJAX_PARAMS, TEE_TIME_FORM_ID
from .jsf import parse_form_state, parse_partial_response

BOOK_NOW_ID = f"{TEE_TIME_FORM_ID}:bookTeeTimeAction"
SUCCESS_MARKER = "reservation-confirm-div"


def book_now(session, state: dict[str, str]) -> tuple[bool, dict[str, str], str]:
    payload = dict(state)
    payload["javax.faces.partial.ajax"] = "true"
    payload["javax.faces.source"] = BOOK_NOW_ID
    payload["javax.faces.partial.execute"] = "@all"
    payload["javax.faces.partial.render"] = TEE_TIME_FORM_ID
    payload[BOOK_NOW_ID] = BOOK_NOW_ID

    resp = post_ajax(session, TEE_SHEET_URL, payload, params=TEE_TIME_AJAX_PARAMS)
    updates = parse_partial_response(resp.text)
    form_html = updates[TEE_TIME_FORM_ID]
    new_state = parse_form_state(form_html, TEE_TIME_FORM_ID)

    success = SUCCESS_MARKER in form_html
    return success, new_state, form_html


def _class_text(tree, class_name: str) -> str | None:
    els = tree.xpath(
        f'//*[contains(concat(" ", normalize-space(@class), " "), " {class_name} ")]'
    )
    return els[0].text_content().strip() if els else None


def parse_confirmation(form_html: str) -> dict:
    tree = lhtml.fromstring(form_html)

    course = tree.xpath('//span[@class="reservation-confirm-heading"]//label/text()')
    date_text = _class_text(tree, "tee-time-confirm-date")
    time_text = _class_text(tree, "tee-time-confirm-time")
    tee_off_text = _class_text(tree, "tee-time-confirm-tee-off")
    players = [
        el.text_content().strip()
        for el in tree.xpath(
            '//*[contains(concat(" ", normalize-space(@class), " "), " tee-time-confirm-player-name ")]'
        )
    ]

    return {
        "course": course[0].strip() if course else None,
        "date": date_text.replace("Date: ", "").strip() if date_text else None,
        "time": time_text.replace("Time: ", "").strip() if time_text else None,
        "tee_off": tee_off_text.replace("Tee Off: ", "").strip() if tee_off_text else None,
        "players": players,
    }
