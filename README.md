# Automated Reservation Bot

A Python system for winning a race condition: booking a highly contested reservation slot
the instant it becomes available on a legacy, server-stateful web portal — reliably,
unattended, on a schedule, against a real production system with anti-bot protection in
front of it.

This README documents the architecture and the engineering decisions behind it, not the
specific service it targets (deliberately omitted, along with all credentials and
personal data).

## The problem

The target portal releases new reservation slots at a precise, known time. Slots are
claimed on a first-come basis, so anything that isn't sitting there ready to fire the
instant release happens will lose the race. Three things make this harder than a typical
scrape-and-submit script:

1. **The site sits behind Cloudflare's bot-detection layer.** A plain HTTP client can't
   get past it — the JS challenge and the TLS handshake fingerprint both need to look
   like a real browser.
2. **The booking flow is a stateful, server-rendered JSF/PrimeFaces application**, not a
   REST API. Every interaction is a partial-page AJAX postback that depends on a
   server-side "ViewState" token and requires the entire current form state to be
   replayed on each request — there's no clean, documented endpoint to just POST a
   booking to.
3. **Correctness has to be perfect on the first try.** There's no room for a failed
   request, a stale token, or an off-by-one in a dynamically generated field name — the
   slot will be gone in seconds regardless.

## Architecture: hybrid browser automation + raw HTTP

The system splits work across two different HTTP layers, chosen deliberately for what
each step actually needs:

| Step | Tool | Why |
|---|---|---|
| Login (clearing Cloudflare's challenge, authenticating) | **Playwright**, real Chrome | Not time-critical, but genuinely needs a real browser — Cloudflare's JS challenge only clears in an actual browser context |
| Slot search, hold creation, form submission | **`curl_cffi`** (TLS-fingerprint-impersonating HTTP client) | These *are* time-critical — a headless browser is too slow for a race condition, but a plain HTTP client's TLS handshake doesn't match what Cloudflare issued clearance for, so it gets re-challenged |

Playwright authenticates once per run, then hands its full cookie jar off to a
`curl_cffi` session (`impersonate="chrome"`) that does everything else via direct HTTP
POST. This is the core design insight: **Cloudflare clearance is bound to a TLS
fingerprint, not just a cookie value** — swapping a browser-accurate TLS client in for
the raw-request phase is what makes "authenticate with a browser, transact with HTTP"
actually work end to end instead of getting silently re-challenged.

## Reverse-engineering a stateful JSF application

The booking portal is built on JSF/PrimeFaces with **server-side state saving** — every
page interaction is an AJAX partial postback carrying a `javax.faces.ViewState` token
that points at server-held state, not a value the client computes. Building a client for
this required working out several non-obvious mechanics purely from captured
request/response pairs (Chrome DevTools → replay via raw HTTP → verify), since none of it
is documented anywhere public:

- **ViewState must be chained, never reused.** Every response returns a fresh token that
  has to be parsed out and carried into the *next* request. A stale token silently fails.
- **`execute=@all` postbacks require the entire current form state resubmitted
  verbatim**, not just the field that changed — so the client snapshots every
  input/select/textarea on each response and replays it on the next request, changing
  only what's intentionally different.
- **Plain command buttons need a self-referential "clicked" marker field** in the
  payload (`{button_id: button_id}`) that real browser JS adds automatically — omit it
  and the server just silently re-renders the same state with no error at all. This
  class of bug (silent no-op, no exception, no error message) turned out to be the
  hardest failure mode to debug in the whole project, and shows up more than once.
- **Dynamically generated field/element IDs encode structural position, not identity** —
  e.g. a slot's "reserve" button ID embeds its index in that day's rendered grid, which
  shifts depending on the day. Nothing can be hardcoded; the client parses the live page
  to find the right element by its actual displayed value each time.
- **Different UI actions that look similar can hit completely different server-side data
  pools** — two visually similar "add a person" buttons turned out to query different
  scopes (one filtered by real-time availability, one not), a distinction invisible from
  the UI alone and only discoverable by testing both live and comparing results.

## Precision timing

Winning the release-moment race means the process has to be correct to within a second
or two, unattended, on a schedule set days in advance:

- **NTP-corrected clock**, not bare system time — the scheduler queries a public time
  server for a live offset each run rather than trusting local clock drift.
- **Two-phase sleep**: coarse sleep down to a few seconds before the target, then a tight
  polling loop for the final approach, to land the actual request as close to the release
  instant as practical.
- **Everything about the target date is computed at runtime** from the current date and
  the service's own release-timing rules — nothing is ever hardcoded, since the same
  code runs unattended on a recurring schedule against a moving target date.

## Retry and fallback logic

A single hardcoded "try this one thing" approach isn't resilient enough for a real
unattended run, so the booking flow layers several independent strategies:

1. **A distance-based nearest-slot search**, not a fixed-offset one — real slot spacing
   on the live system turned out not to match the nominal grid spacing assumed at design
   time, so the search matches against the *actual* rendered slot list rather than
   generating synthetic candidate times and hoping they align.
2. **A prioritized fallback across two resources** (e.g., two possible courses/venues),
   trying the preferred one exhaustively before falling back to the secondary.
3. **A round-robin retry across a short list of acceptable co-reservation participants**,
   since the target system requires a complete party and doesn't accept solo bookings —
   discovered only by testing, since it fails with no error message rather than a clear
   rejection.
4. **A distinct last-resort strategy** (different time window, different fallback
   participant) that only engages once the primary strategy is fully exhausted, so the
   system always attempts *something* rather than giving up the moment the ideal outcome
   isn't available.
5. **Clean, typed failure states** (`no_booking_possible`, `partner_not_found`, etc.)
   instead of exceptions or silent failures, so a failed run is diagnosable from its
   output alone.

## Reliability and observability

- Every run either produces a real, verified booking or a clean, typed failure result —
  there is no ambiguous "probably worked" state.
- Failure notifications are sent by email only on genuine failure (a scheduled run that
  succeeds needs no extra signal, since the target system already confirms bookings
  through its own channel) — success is logged locally, not over-notified.
- A crash anywhere in the pipeline is caught, logged with a full traceback, and still
  triggers a notification, so an unattended run never fails silently.

## Running it

```bash
pip install -r requirements.txt
playwright install chrome    # first run only

cp .env.example .env         # then fill in credentials/config — gitignored, never committed
```

Two modes:

```bash
# Test mode — targets a real weekday slot 14 days out and runs immediately,
# exercising the full pipeline (including a real booking) without waiting
# for an actual release window. Used throughout development to validate
# each piece against the live site.
python3 -m teetime_bot.run --test

# Production mode — computes today's correct release day/target date from
# the service's own timing rules, syncs to NTP time, sleeps until the exact
# release moment, then executes. This is what cron invokes unattended.
python3 -m teetime_bot.run
```

`--headed` runs the login browser visibly instead of headless, useful for
debugging the Cloudflare-clearance/auth step by watching it happen.

In production, this is invoked by cron at the appropriate times for each
target release day, with output redirected to a log file for
post-run diagnosis:

```
<release-day-1 schedule> cd /path/to/project && python3 -m teetime_bot.run >> teetime_bot.log 2>&1
<release-day-2 schedule> cd /path/to/project && python3 -m teetime_bot.run >> teetime_bot.log 2>&1
```

## Stack

`Playwright` (Cloudflare-gated auth) · `curl_cffi` (TLS-impersonating HTTP client) ·
`lxml` (HTML/XML parsing of AJAX response fragments) · `ntplib` (time-source correction)
· `python-dotenv` (config/secrets) · stdlib `smtplib` (notifications) — no paid
third-party APIs anywhere in the pipeline.

## What's intentionally not in this repo

Real credentials, the target site's identity, member/participant names, and any
personally identifying configuration — all of that lives in a local, gitignored `.env`
and is never committed. This README describes the system's engineering, not the specific
service it automates.
