from __future__ import annotations

import json

from lxml import html as lhtml

from .client import post_ajax
from .config import TEE_SHEET_URL, TEE_TIME_AJAX_PARAMS, TEE_TIME_NAMESPACE, VIEW_STATE_UPDATE_ID
from .jsf import parse_fragment_state, parse_partial_response

PLAYERS_TABLE_ID = f"{TEE_TIME_NAMESPACE}:teeTimeForm:reservationsTable:0:playersTable"


def player_field_id(row_index: int) -> str:
    return f"{PLAYERS_TABLE_ID}:{row_index}:player"


# Only verified for row 1 (player 2's row) — a fresh 2-player hold's row 1 starts as
# "Member" / "Registered Guest" buttons, not yet an autocomplete field. Two different
# paths reveal a search field there, and they search different pools:
#   - "Member" (j_idt611): scoped to members actually available at that date/time — adding
#     someone here books THEM as a co-member, so the system checks they aren't double-booked.
#   - "Registered Guest" -> "Registered Guest" submenu item (j_idt623): finds a person
#     regardless of their own schedule (they're joining as a guest, not making their own
#     booking), but only searches people already registered as one of *this* member's
#     recognized guests — not the whole club directory. Verified live: a primary partner's
#     name found nothing via "Member" (they had a conflict at that date/time) but found
#     them immediately via this path; conversely a real member who isn't on that guest list (e.g. one not
#     previously used as a guest) finds nothing via "Registered Guest" but shows up fine
#     via "Member" if they're actually free then.
# Which path fits a given name isn't knowable in advance, so callers should try both.
# Row indices beyond 1 would need their own capture, since JSF auto-generates these ids
# per component-tree position.
ENABLE_MEMBER_SEARCH_ID = f"{PLAYERS_TABLE_ID}:1:j_idt611"
ENABLE_REGISTERED_GUEST_SEARCH_ID = f"{PLAYERS_TABLE_ID}:1:j_idt623"


def _enable_search(session, state: dict[str, str], button_id: str, extra_render: tuple[str, ...]) -> tuple[dict[str, str], str]:
    render_targets = " ".join(
        f"{TEE_TIME_NAMESPACE}:teeTimeForm:{part}"
        for part in ("reservationsTable:0:playersTable", "bookTeeTimeAction", "updateTeeTimeAction", *extra_render)
    )
    payload = dict(state)
    payload["javax.faces.partial.ajax"] = "true"
    payload["javax.faces.source"] = button_id
    payload["javax.faces.partial.execute"] = button_id
    payload["javax.faces.partial.render"] = render_targets
    payload[button_id] = button_id

    resp = post_ajax(session, TEE_SHEET_URL, payload, params=TEE_TIME_AJAX_PARAMS)
    updates = parse_partial_response(resp.text)
    players_html = updates[PLAYERS_TABLE_ID]

    new_state = dict(state)
    new_state.update(parse_fragment_state(players_html))
    if VIEW_STATE_UPDATE_ID in updates:
        new_state["javax.faces.ViewState"] = updates[VIEW_STATE_UPDATE_ID]
    return new_state, players_html


def enable_member_search(session, state: dict[str, str]) -> tuple[dict[str, str], str]:
    return _enable_search(session, state, ENABLE_MEMBER_SEARCH_ID, extra_render=("billToPlayer",))


def enable_registered_guest_search(session, state: dict[str, str]) -> tuple[dict[str, str], str]:
    return _enable_search(session, state, ENABLE_REGISTERED_GUEST_SEARCH_ID, extra_render=())


def search_player(session, state: dict[str, str], row_index: int, query: str) -> list[dict]:
    field_id = player_field_id(row_index)
    payload = dict(state)
    payload["javax.faces.partial.ajax"] = "true"
    payload["javax.faces.source"] = field_id
    payload["javax.faces.partial.execute"] = field_id
    payload["javax.faces.partial.render"] = field_id
    payload[field_id] = field_id
    payload[f"{field_id}_query"] = query
    payload[f"{field_id}_input"] = query
    payload[f"{field_id}_hinput"] = query

    resp = post_ajax(session, TEE_SHEET_URL, payload, params=TEE_TIME_AJAX_PARAMS)
    updates = parse_partial_response(resp.text)
    dropdown_html = updates.get(field_id, "")

    tree = lhtml.fromstring(f"<div>{dropdown_html}</div>")
    candidates = []
    for li in tree.xpath("//li[@data-item-value]"):
        candidates.append(json.loads(li.get("data-item-value")))
    return candidates


def select_player(session, state: dict[str, str], row_index: int, candidate: dict) -> tuple[dict[str, str], str]:
    field_id = player_field_id(row_index)
    candidate_json = json.dumps(candidate, separators=(",", ":"))
    render_targets = " ".join(
        f"{TEE_TIME_NAMESPACE}:teeTimeForm:{part}"
        for part in ("reservationsTable:0:playersTable", "picturesTable", "reciprocalPopup", "buddyWizard", "billToPlayer")
    )

    payload = dict(state)
    payload["javax.faces.partial.ajax"] = "true"
    payload["javax.faces.source"] = field_id
    payload["javax.faces.partial.execute"] = field_id
    payload["javax.faces.partial.render"] = render_targets
    payload["javax.faces.behavior.event"] = "itemSelect"
    payload["javax.faces.partial.event"] = "itemSelect"
    payload[f"{field_id}_itemSelect"] = candidate_json
    payload[f"{field_id}_input"] = candidate["displayName"]
    payload[f"{field_id}_hinput"] = candidate_json

    resp = post_ajax(session, TEE_SHEET_URL, payload, params=TEE_TIME_AJAX_PARAMS)
    updates = parse_partial_response(resp.text)
    players_html = updates[PLAYERS_TABLE_ID]

    new_state = dict(state)
    new_state.update(parse_fragment_state(players_html))
    if VIEW_STATE_UPDATE_ID in updates:
        new_state["javax.faces.ViewState"] = updates[VIEW_STATE_UPDATE_ID]
    return new_state, players_html
