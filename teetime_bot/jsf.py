# Snapshots every current form field so a postback can resubmit the full form verbatim,
# per the execute=@all behavior this portlet uses on every AJAX action.

from lxml import etree
from lxml import html as lhtml


def _collect_state(root) -> dict[str, str]:
    state: dict[str, str] = {}

    for el in root.xpath(".//input[@name]"):
        input_type = el.get("type", "text")
        if input_type in ("checkbox", "radio") and el.get("checked") is None:
            continue
        state[el.get("name")] = el.get("value", "")

    for el in root.xpath(".//select[@name]"):
        selected = el.xpath('.//option[@selected]')
        state[el.get("name")] = selected[0].get("value", "") if selected else ""

    for el in root.xpath(".//textarea[@name]"):
        state[el.get("name")] = (el.text or "").strip()

    return state


def parse_form_state(page_html: str, form_id: str) -> dict[str, str]:
    tree = lhtml.fromstring(page_html)
    matches = tree.xpath(f'//form[@id="{form_id}"]')
    if not matches:
        raise ValueError(f"form {form_id!r} not found in page")
    return _collect_state(matches[0])


def parse_fragment_state(fragment_html: str) -> dict[str, str]:
    return _collect_state(lhtml.fromstring(fragment_html))


def view_state(state: dict[str, str]) -> str:
    return state["javax.faces.ViewState"]


def parse_partial_response(xml_text: str) -> dict[str, str]:
    root = etree.fromstring(xml_text.encode("utf-8"))
    return {el.get("id"): (el.text or "") for el in root.iter("update")}
