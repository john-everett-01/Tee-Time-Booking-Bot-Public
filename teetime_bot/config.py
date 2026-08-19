import os

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.example-club.com"
LOGIN_URL = f"{BASE_URL}/web/pages/login"
TEE_SHEET_URL = f"{BASE_URL}/group/pages/book-a-tee-time"

TEE_TIME_NAMESPACE = "_teeTimePortlet_WAR_northstarportlet_"
TEE_TIME_FORM_ID = f"{TEE_TIME_NAMESPACE}:teeTimeForm"
VIEW_STATE_UPDATE_ID = f"{TEE_TIME_NAMESPACE}:javax.faces.ViewState:0"

TEE_TIME_AJAX_PARAMS = {
    "p_p_id": "teeTimePortlet_WAR_northstarportlet",
    "p_p_lifecycle": "2",
    "p_p_state": "normal",
    "p_p_mode": "view",
    "p_p_cacheability": "cacheLevelPage",
    "p_p_col_id": "column-2",
    "p_p_col_count": "1",
    f"{TEE_TIME_NAMESPACE}_jsfBridgeAjax": "true",
    f"{TEE_TIME_NAMESPACE}_facesViewIdResource": "/WEB-INF/views/sports/teetime/teesheet/TeeTime.xhtml",
}

MEMBER_NUMBER = os.environ["CLUB_MEMBER_NUMBER"]
PASSWORD = os.environ["CLUB_PASSWORD"]

# Primary partner candidates, tried in round-robin order up to a max of 5 attempts total
# (e.g. two names -> A,B,A,B,A). A partner is mandatory — this club's
# system doesn't accept solo bookings (confirmed live) — so if all attempts fail, the bot
# falls through to the last-resort strategy below rather than booking solo.
PRIMARY_PARTNERS = [n.strip() for n in os.environ.get("PRIMARY_PARTNERS", "").split(",") if n.strip()]
PRIMARY_PARTNER_MAX_ATTEMPTS = 5

# Last resort if no primary partner is found: a fixed time, a specific partner, Course A then Course B.
LAST_RESORT_PARTNER = os.environ.get("LAST_RESORT_PARTNER", "")
LAST_RESORT_TIME_STR = os.environ.get("LAST_RESORT_TIME", "13:00")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFY_EMAIL_FROM = os.environ.get("NOTIFY_EMAIL_FROM", SMTP_USER)
NOTIFY_EMAIL_TO = os.environ.get("NOTIFY_EMAIL_TO", "")
