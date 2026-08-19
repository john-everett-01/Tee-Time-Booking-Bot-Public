from __future__ import annotations

from .client import post_ajax
from .config import TEE_SHEET_URL, TEE_TIME_AJAX_PARAMS, TEE_TIME_FORM_ID
from .jsf import parse_form_state, parse_partial_response


def create_hold(session, state: dict[str, str], reserve_button_id: str) -> tuple[dict[str, str], str]:
    payload = dict(state)
    payload["javax.faces.partial.ajax"] = "true"
    payload["javax.faces.source"] = reserve_button_id
    payload["javax.faces.partial.execute"] = "@all"
    payload["javax.faces.partial.render"] = TEE_TIME_FORM_ID
    payload[reserve_button_id] = reserve_button_id

    resp = post_ajax(session, TEE_SHEET_URL, payload, params=TEE_TIME_AJAX_PARAMS)
    updates = parse_partial_response(resp.text)
    form_html = updates[TEE_TIME_FORM_ID]
    return parse_form_state(form_html, TEE_TIME_FORM_ID), form_html
