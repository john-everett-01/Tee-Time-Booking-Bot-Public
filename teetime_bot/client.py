from curl_cffi import requests

from .config import BASE_URL, TEE_SHEET_URL

AJAX_HEADERS = {
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Referer": TEE_SHEET_URL,
}


def make_session(cookies: dict[str, str]) -> requests.Session:
    session = requests.Session(impersonate="chrome")
    session.cookies.update(cookies)
    return session


def post_ajax(session, url, payload, params=None):
    resp = session.post(url, params=params, data=payload, headers=AJAX_HEADERS)
    resp.raise_for_status()
    return resp
