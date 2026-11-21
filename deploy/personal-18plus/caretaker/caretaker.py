#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Caretaker: small maintenance bots for a personal, adults-only Fluxer instance.

Uses only the Python standard library, so it runs on a fresh Debian/Ubuntu
server with no pip installs. Settings come from /etc/fluxer-caretaker.env
(see caretaker.env.example). Subcommands:

  apply-settings  Push the 18+ instance settings through the Admin API.
  age-gate        Review people waiting for approval and enforce the minimum age.
  reports         Notify the owner about new reports (child-safety ones flagged urgent).
  health          Check rexctl status, the public URL and free disk space.
  badges-setup    Upload the Porchlite badge images as user badges (safe to re-run).
  badges          Hand out and take back badges automatically (see BADGE_* settings).
  test-notify     Send a test notification.
  alert           Send a custom notification.

Every bot only talks to your own instance and to the notification address you
configure. Nothing here bans people for what they post; that stays a human call.
"""

from __future__ import annotations

import argparse
import base64
import re
import datetime as dt
import json
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(os.environ.get("CARETAKER_ENV", "/etc/fluxer-caretaker.env"))
STATE_DIR = Path(os.environ.get("CARETAKER_STATE", "/var/lib/fluxer-caretaker"))
USER_AGENT = "fluxer-caretaker/1.0"


# --------------------------------------------------------------------------- config


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    # Real environment variables win over the file.
    env.update(os.environ)
    return env


CFG = load_env()


def cfg(key: str, default: str | None = None) -> str:
    value = CFG.get(key, default)
    if value is None or value == "":
        sys.exit(f"caretaker: {key} is not set in {ENV_FILE}")
    return value


def base_url() -> str:
    return cfg("FLUXER_URL").rstrip("/")


# --------------------------------------------------------------------------- state


def load_state(name: str) -> dict:
    path = STATE_DIR / f"{name}.json"
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(name: str, data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_DIR / f"{name}.json.tmp"
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(STATE_DIR / f"{name}.json")


# --------------------------------------------------------------------------- http


def http(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: int = 20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", USER_AGENT)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
        if not raw:
            return resp.status, None
        if "json" in (resp.headers.get("Content-Type") or ""):
            return resp.status, json.loads(raw)
        return resp.status, raw.decode(errors="replace")


def admin(method: str, path: str, body: dict | None = None, reason: str | None = None):
    headers = {"Authorization": f"Admin {cfg('FLUXER_ADMIN_API_KEY')}"}
    if reason:
        headers["X-Audit-Log-Reason"] = reason[:500]
    try:
        _, payload = http(method, f"{base_url()}/api/v1/admin{path}", body, headers)
        return payload
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:500]
        raise SystemExit(f"caretaker: {method} {path} failed with {err.code}: {detail}") from err


# --------------------------------------------------------------------------- notify


def notify(title: str, message: str, urgent: bool = False) -> None:
    """Post to ntfy, a Discord/Slack webhook, Gotify or Apprise. Prints if unset."""
    url = CFG.get("NOTIFY_URL", "")
    line = f"[{title}] {message}"
    print(line)
    if not url:
        return
    try:
        if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
            http("POST", url, {"content": f"**{title}**\n{message}"})
        elif "hooks.slack.com" in url:
            http("POST", url, {"text": f"*{title}*\n{message}"})
        elif "ntfy" in url and "/message" not in url:
            req = urllib.request.Request(url, data=message.encode(), method="POST")
            req.add_header("Title", title)
            req.add_header("User-Agent", USER_AGENT)
            if urgent:
                req.add_header("Priority", "urgent")
                req.add_header("Tags", "rotating_light")
            urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()).read()
        else:  # Gotify, Apprise API and generic JSON receivers
            http("POST", url, {"title": title, "message": message, "body": message,
                               "priority": 8 if urgent else 5})
    except Exception as err:  # never let a notification failure crash a bot
        print(f"caretaker: notification failed: {err}", file=sys.stderr)


# --------------------------------------------------------------------------- age


def age_on(dob: str, today: dt.date) -> int | None:
    try:
        born = dt.date.fromisoformat(dob)
    except (TypeError, ValueError):
        return None
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    if years < 0 or years > 120:
        return None
    return years


# --------------------------------------------------------------------------- commands


def cmd_apply_settings(_: argparse.Namespace) -> None:
    """Turn on the adults-only defaults. Safe to run again at any time."""
    product = CFG.get("INSTANCE_NAME", "")
    legal_base = CFG.get("LEGAL_BASE_URL", "").rstrip("/")
    patch: dict = {
        # Everyone must give a date of birth; accounts without one can't do much.
        "accounts": {"date_of_birth": "require_all", "interaction_tier": "enforced"},
        # Anyone can ask to join, but an admin (or the age-gate bot) approves first.
        "registration": {"mode": CFG.get("REGISTRATION_MODE", "approval")},
        # Only admins can create communities, so the space stays yours.
        "policy": {"guild_create_access": False},
        "app_public": {"registration": {"collect_date_of_birth": True}},
        "notice": {
            "message": CFG.get(
                "NOTICE_MESSAGE",
                "18+ only. By using this server you confirm you are an adult and accept the rules.",
            ),
            "url": f"{legal_base}/RULES.md" if legal_base else None,
        },
    }
    branding: dict = {}
    if product:
        branding["product_name"] = product
    if CFG.get("BRAND_COLOR"):
        branding["theme_color"] = CFG["BRAND_COLOR"]
    if branding:
        patch["app_public"]["branding"] = branding
    if legal_base:
        patch["app_public"]["legal"] = {
            "terms_url": f"{legal_base}/TERMS.md",
            "privacy_url": f"{legal_base}/PRIVACY.md",
            "guidelines_url": f"{legal_base}/RULES.md",
        }
    if not patch["notice"]["url"]:
        patch["notice"].pop("url")
    result = admin("PATCH", "/instance/config", patch, reason="caretaker: apply adults-only settings")
    for warning in (result or {}).get("warnings", []):
        print(f"warning: {warning}")
    print("Adults-only settings applied.")


def cmd_age_gate(_: argparse.Namespace) -> None:
    min_age = int(CFG.get("MIN_AGE", "18"))
    auto_approve = CFG.get("AGE_GATE_AUTO_APPROVE", "false").lower() == "true"
    state = load_state("age-gate")
    seen: dict = state.setdefault("notified", {})
    today = dt.date.today()

    pending = (admin("GET", "/instance/pending-registrations") or {}).get("pending_registrations", [])
    for person in pending:
        uid = str(person["user_id"])
        tag = f"{person.get('username')}#{person.get('discriminator')}"
        users = (admin("GET", f"/users?user_id={uid}") or {}).get("users", [])
        dob = users[0].get("date_of_birth") if users else None
        age = age_on(dob, today) if dob else None

        if age is not None and age < min_age:
            admin("PATCH", f"/instance/pending-registrations/{uid}", {"status": "rejected"},
                  reason=f"caretaker: under {min_age}")
            notify("Sign-up rejected", f"{tag} gave an age under {min_age} and was turned away.")
            seen.pop(uid, None)
        elif age is not None and auto_approve:
            admin("PATCH", f"/instance/pending-registrations/{uid}", {"status": "approved"},
                  reason=f"caretaker: stated age {min_age}+")
            notify("Sign-up approved", f"{tag} (stated age {age}) was approved automatically.")
            seen.pop(uid, None)
        elif uid not in seen:
            why = f"stated age {age}" if age is not None else "no date of birth given yet"
            notify("Sign-up waiting", f"{tag} wants to join ({why}). Approve or deny in {base_url()}/admin "
                   f"or with: rexctl registration approve {uid}")
            seen[uid] = today.isoformat()

    still_pending = {str(p["user_id"]) for p in pending}
    state["notified"] = {k: v for k, v in seen.items() if k in still_pending}
    save_state("age-gate", state)


URGENT_WORDS = ("child", "minor", "csam", "underage", "exploitation")


def cmd_reports(_: argparse.Namespace) -> None:
    state = load_state("reports")
    known = set(state.get("seen", []))
    data = admin("GET", "/reports?status=pending&limit=100") or {}
    fresh = [r for r in data.get("reports", []) if str(r["report_id"]) not in known]
    for r in fresh:
        label = r.get("reason_label") or r.get("category") or "report"
        who = r.get("reported_user_tag") or r.get("reported_guild_name") or "something"
        text = f"{label}: {who}. Review it at {base_url()}/admin"
        hay = f"{label} {r.get('reason') or ''} {r.get('category') or ''}".lower()
        urgent = bool(r.get("reason_highest_priority")) or any(w in hay for w in URGENT_WORDS)
        notify("URGENT report" if urgent else "New report", text, urgent=urgent)
        known.add(str(r["report_id"]))
    # Keep the list bounded to what is still pending plus recent history.
    save_state("reports", {"seen": sorted(known)[-2000:]})


def cmd_health(_: argparse.Namespace) -> None:
    problems: list[str] = []
    rexctl = CFG.get("REXCTL", "rexctl")
    instance_dir = CFG.get("FLUXER_DIR", "/opt/fluxer")

    try:
        out = subprocess.run([rexctl, "status", "--json", "--dir", instance_dir],
                             capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            problems.append(f"rexctl status failed: {(out.stderr or out.stdout).strip()[:300]}")
    except (OSError, subprocess.TimeoutExpired) as err:
        problems.append(f"could not run rexctl status: {err}")

    try:
        status, _ = http("GET", f"{base_url()}/", timeout=20)
        if status >= 400:
            problems.append(f"{base_url()} answered {status}")
    except Exception as err:
        problems.append(f"{base_url()} is not reachable: {err}")

    min_free = float(CFG.get("MIN_FREE_DISK_GB", "10"))
    for path in {"/", "/var/lib/docker", instance_dir}:
        if os.path.exists(path):
            free_gb = shutil.disk_usage(path).free / 1e9
            if free_gb < min_free:
                problems.append(f"only {free_gb:.1f} GB free on {path}")

    state = load_state("health")
    was_failing = state.get("failing", False)
    if problems:
        if not was_failing or state.get("last") != problems:
            notify("Server problem", "; ".join(problems), urgent=True)
        save_state("health", {"failing": True, "last": problems})
        sys.exit(1)
    if was_failing:
        notify("Server recovered", f"{base_url()} looks healthy again.")
    save_state("health", {"failing": False})
    print("healthy")


# --------------------------------------------------------------------------- badges

BADGE_DIR = Path(os.environ.get("CARETAKER_BADGES", "/opt/fluxer-caretaker/badges"))

# slug (image file name), badge name, hover text, extra role names that also earn it
BADGES = [
    ("peach-fuzz", "Peach Fuzz", "New member, fresh and fuzzy", []),
    ("thirst-trap", "Thirst Trap Certified", "Officially too hot to handle", ["Thirst Trap"]),
    ("professional-yapper", "Professional Yapper", "Has never sent a short message", ["Yapper"]),
    ("after-dark", "After Dark", "Most active after midnight", []),
    ("menace", "Menace", "Chaos with a smile", []),
    ("brat-energy", "Brat Energy", "Make me (politely)", ["Brat"]),
    ("soft-dom", "Soft Dom(me)", "In charge, but make it cuddly", ["Soft Dom", "Soft Domme"]),
    ("switch-witch", "Switch Witch", "Goes both ways on who's in charge", ["Switch"]),
    ("innocent-allegedly", "Innocent (Allegedly)", "Halo slightly crooked", ["Innocent"]),
    ("flirt-licensed", "Flirt Licensed", "Certified smooth talker", ["Flirt"]),
    ("consent-royalty", "Consent Queen / King", "Asks first, every time",
     ["Consent Queen", "Consent King", "Consent Royalty"]),
    ("hype-fairy", "Hype Fairy", "Your biggest cheerleader", []),
    ("snack", "Snack", "Looking delicious today", []),
    ("og-z", "OG Z", "Here since day one", []),
]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def list_user_badges() -> dict[str, str]:
    """Return {badge name: badge id} for every user badge on the instance."""
    found: dict[str, str] = {}
    after = None
    while True:
        query = "/badges?type=user&limit=200" + (f"&after={after}" if after else "")
        page = admin("GET", query) or {}
        for badge in page.get("badges", []):
            if badge.get("type", "user") == "user":
                found[badge["name"]] = str(badge["id"])
        after = page.get("next")
        if not after:
            return found


def cmd_badges_setup(_: argparse.Namespace) -> None:
    existing = list_user_badges()
    for slug, name, description, _aliases in BADGES:
        image = BADGE_DIR / f"{slug}.png"
        if name in existing:
            print(f"{name}: already there")
            continue
        if not image.exists():
            print(f"{name}: skipped, {image} is missing")
            continue
        data_url = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
        made = admin("POST", "/badges", {"type": "user", "name": name, "href": None, "image": data_url},
                     reason="caretaker: badges-setup")
        admin("PATCH", f"/badges/{made['id']}", {"name": name, "description": description, "href": None},
              reason="caretaker: badges-setup")
        print(f"{name}: created")


def _get_user(uid: str) -> dict:
    payload = admin("GET", f"/users/{uid}") or {}
    if "users" in payload:
        return (payload["users"] or [{}])[0]
    return payload.get("user", payload)


def _guild_members(guild_id: str) -> list[dict]:
    members: list[dict] = []
    offset = 0
    while True:
        page = (admin("GET", f"/guilds/{guild_id}/members?limit=200&offset={offset}") or {}).get("members", [])
        members.extend(page)
        if len(page) < 200:
            return members
        offset += 200


def cmd_badges(_: argparse.Namespace) -> None:
    """Keep badges in step with the rules:

    - Peach Fuzz while someone joined the server less than BADGE_PEACH_FUZZ_DAYS ago.
    - OG Z for everyone who joined before BADGE_OG_BEFORE (kept for good).
    - Any other badge while the member has a server role with the same name
      (for example a "Brat Energy" role, from a role picker or given by a mod).

    Badges you hand out yourself in the admin panel are never taken away; the bot
    only removes a badge it gave out.
    """
    guild_id = cfg("BADGE_GUILD_ID")
    fuzz_days = int(CFG.get("BADGE_PEACH_FUZZ_DAYS", "14") or 0)
    og_before = CFG.get("BADGE_OG_BEFORE", "").strip()
    og_cutoff = dt.date.fromisoformat(og_before) if og_before else None
    today = dt.datetime.now(dt.timezone.utc)

    ids = list_user_badges()
    missing = [name for _, name, _, _ in BADGES if name not in ids]
    if missing:
        print("Not created yet (run badges-setup): " + ", ".join(missing))

    guild = (admin("GET", f"/guilds/{guild_id}") or {}).get("guild") or {}
    role_names = {str(r["id"]): _norm(r.get("name", "")) for r in guild.get("roles", [])}
    by_role: dict[str, str] = {}
    for _, name, _, aliases in BADGES:
        if name in ("Peach Fuzz", "OG Z") or name not in ids:
            continue
        for label in [name, *aliases]:
            by_role[_norm(label)] = ids[name]

    state = load_state("badges")
    given: dict[str, list[str]] = state.setdefault("given", {})
    changes = 0
    for member in _guild_members(guild_id):
        user = member.get("user") or {}
        uid = str(user.get("id", ""))
        if not uid or user.get("bot"):
            continue
        joined = dt.datetime.fromisoformat(member["joined_at"].replace("Z", "+00:00"))
        want: set[str] = set()
        if "Peach Fuzz" in ids and fuzz_days and (today - joined).days < fuzz_days:
            want.add(ids["Peach Fuzz"])
        if "OG Z" in ids and og_cutoff and joined.date() < og_cutoff:
            want.add(ids["OG Z"])
        for role_id in member.get("roles", []):
            badge_id = by_role.get(role_names.get(str(role_id), ""))
            if badge_id:
                want.add(badge_id)

        mine = set(given.get(uid, []))
        keep_og = {ids["OG Z"]} & mine if "OG Z" in ids else set()
        current = set(str(b) for b in (_get_user(uid).get("badge_ids") or []))
        add = want - current
        drop = (mine - want - keep_og) & current
        if not add and not drop:
            given[uid] = sorted(mine & current)
            continue
        new = sorted((current | add) - drop)
        admin("PATCH", f"/users/{uid}/badges", {"badge_ids": new}, reason="caretaker: badge rules")
        given[uid] = sorted((mine - drop) | add)
        changes += 1
        tag = user.get("global_name") or user.get("username") or uid
        print(f"{tag}: +{len(add)} -{len(drop)} badges")
    state["given"] = {k: v for k, v in given.items() if v}
    save_state("badges", state)
    print(f"Badges checked, {changes} member(s) updated.")


def cmd_test_notify(_: argparse.Namespace) -> None:
    notify("Caretaker test", f"Notifications from {CFG.get('FLUXER_URL', 'your server')} work.")


def cmd_alert(args: argparse.Namespace) -> None:
    notify(args.title, args.message, urgent=args.urgent)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    alert = sub.add_parser("alert", help="Send a custom notification (used by shell scripts).")
    alert.add_argument("title")
    alert.add_argument("message")
    alert.add_argument("--urgent", action="store_true")
    alert.set_defaults(func=cmd_alert)
    for name, fn in {
        "apply-settings": cmd_apply_settings,
        "age-gate": cmd_age_gate,
        "reports": cmd_reports,
        "health": cmd_health,
        "badges-setup": cmd_badges_setup,
        "badges": cmd_badges,
        "test-notify": cmd_test_notify,
    }.items():
        sub.add_parser(name).set_defaults(func=fn)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
