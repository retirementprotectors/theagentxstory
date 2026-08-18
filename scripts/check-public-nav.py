#!/usr/bin/env python3
"""
KGM-AGX-NAV-PIN-001 — the public site's front-door nav is PINNED, so a change to it
cannot ride inside an unrelated commit.

⛔ WHY THIS EXISTS. On 2026-08-15 a link to /FiveBusinessDays/ — the acquisition
narrative — was added to the public site's cross-nav. It went in inside `9591aa8`,
whose subject is "correct the counts that went stale since April". **Publishing the
page was a decision; putting it in the front-door nav rode along inside a mechanical
freshness pass, so nobody reviewed it as a publication choice.** JDM found it on the
live site and it came off in `fcd3f91` (SHINOB1).

The defect is not the sweep and not the author. It is the shape: **a wide mechanical
edit carrying one non-mechanical change, under a subject line that describes only the
mechanical part.** A reviewer reading the subject has no reason to look.

⭐ WHY A PIN RATHER THAN A SUBJECT-LINE RULE. Keying on "is this a freshness commit"
would be a STRING standing in for a CONCEPT — it fires on wording, misses a rename,
and cannot see a change that arrives with no subject at all. **A pin does not care
what the commit says.** Any change to the set of public entry points turns this red
until a human updates the pinned list, which is exactly the moment the change stops
being invisible. It condemns its own author: the next freshness sweep this lane runs
will trip it.

⚠ WHAT IT DOES NOT DO. It pins the front-door NAV, not the site. A page can still be
published, linked from body copy, or shared directly — all of which are legitimate and
none of which this sees. It is scoped to the one surface that makes a page reachable
from the public root without anyone choosing to link it.

USAGE
    python3 scripts/check-public-nav.py              verify against the pin
    python3 scripts/check-public-nav.py --selftest   prove the check can go RED
    python3 scripts/check-public-nav.py --update     rewrite the pin (deliberate act)

EXIT
    0  the nav matches the pin
    1  the nav DRIFTED from the pin
    2  INCONCLUSIVE — could not parse or could not read. Never a pass.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PIN = ROOT / "public-nav.pinned"

NAV_RE = re.compile(r'<div class="cross-nav"[^>]*>(.*?)</div>', re.S)
HREF_RE = re.compile(r'<a\s[^>]*href="([^"]+)"')


def nav_of(path: Path):
    """Return the ordered href list for a page, or None if it carries no cross-nav."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise RuntimeError(f"cannot read {path.name}: {e}")
    m = NAV_RE.search(src)
    if not m:
        return None
    return HREF_RE.findall(m.group(1))


def observed():
    """Every top-level page that HAS a cross-nav, in sorted order."""
    out = {}
    pages = sorted(p for p in ROOT.glob("*.html"))
    if not pages:
        raise RuntimeError("no *.html at the repo root — the scan found nothing to check")
    for p in pages:
        nav = nav_of(p)
        if nav is not None:
            out[p.name] = nav
    if not out:
        raise RuntimeError("no page carries a cross-nav — the extractor is broken, not the site")
    return out


def render(nav: dict) -> str:
    return "".join(f"{page}: {','.join(hrefs)}\n" for page, hrefs in sorted(nav.items()))


def parse(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        page, _, rest = line.partition(":")
        out[page.strip()] = [h.strip() for h in rest.split(",") if h.strip()]
    return out


def check() -> int:
    try:
        obs = observed()
    except RuntimeError as e:
        print(f"INCONCLUSIVE — {e}")
        return 2
    if not PIN.exists():
        print(f"INCONCLUSIVE — no pin at {PIN.name}. Run --update to create it deliberately.")
        return 2
    pinned = parse(PIN.read_text(encoding="utf-8"))

    drift = []
    for page in sorted(set(obs) | set(pinned)):
        a, b = pinned.get(page), obs.get(page)
        if a is None:
            drift.append(f"  NEW PAGE with a nav, not in the pin: {page} -> {b}")
        elif b is None:
            drift.append(f"  page lost its nav (or was deleted): {page}, pinned {a}")
        elif a != b:
            added = [h for h in b if h not in a]
            gone = [h for h in a if h not in b]
            drift.append(f"  {page}")
            if added:
                drift.append(f"      ADDED entry point(s):   {added}   <- a publication decision")
            if gone:
                drift.append(f"      REMOVED entry point(s): {gone}")
            if not added and not gone:
                drift.append(f"      REORDERED: pinned {a} -> now {b}")

    if drift:
        print("PUBLIC NAV DRIFTED FROM THE PIN\n")
        print("\n".join(drift))
        print(
            "\nThis is not a lint failure. The set of ways into the public site changed.\n"
            "If that was the intent, say so in its OWN commit and run:\n"
            "    python3 scripts/check-public-nav.py --update\n"
            "If it was not, you have just found a change riding inside an unrelated one."
        )
        return 1

    pages = ", ".join(sorted(obs))
    print(f"public nav matches the pin — {len(obs)} page(s): {pages}")
    return 0


def selftest() -> int:
    """⛔ A pin nobody has watched go red is worth nothing. Both directions, both arms."""
    failures = 0

    def arm(name, got, want):
        nonlocal failures
        ok = got == want
        if not ok:
            failures += 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}   got={got} want={want}")

    try:
        base = observed()
    except RuntimeError as e:
        print(f"INCONCLUSIVE — {e}")
        return 2

    pinned = parse(PIN.read_text(encoding="utf-8")) if PIN.exists() else {}
    arm("GREEN — the live nav matches the pin", base == pinned, True)

    page = sorted(base)[0]

    mutated = {k: list(v) for k, v in base.items()}
    mutated[page] = mutated[page] + ["FiveBusinessDays/"]
    arm("RED — an ADDED entry point differs from the pin", mutated == pinned, False)

    mutated2 = {k: list(v) for k, v in base.items()}
    mutated2[page] = mutated2[page][:-1]
    arm("RED — a REMOVED entry point differs from the pin", mutated2 == pinned, False)

    mutated3 = {k: list(v) for k, v in base.items()}
    mutated3[page] = list(reversed(mutated3[page]))
    arm("RED — a REORDERED nav differs from the pin", mutated3 == pinned, False)

    # ⛔ The control that keeps the three REDs honest: an UNCHANGED copy must still
    # compare equal. Without it, a comparison that always reports "different" would
    # pass all three red arms and prove nothing.
    arm("CONTROL — an untouched copy still matches", {k: list(v) for k, v in base.items()} == pinned, True)

    print(f"\nselftest: {5 - failures} passed, {failures} failed")
    return 1 if failures else 0


def update() -> int:
    try:
        obs = observed()
    except RuntimeError as e:
        print(f"INCONCLUSIVE — {e}")
        return 2
    PIN.write_text(
        "# KGM-AGX-NAV-PIN-001 — the public site's front-door nav.\n"
        "# Changing this file is a PUBLICATION DECISION. Land it in its own commit,\n"
        "# never inside a freshness or content sweep. See scripts/check-public-nav.py.\n"
        + render(obs),
        encoding="utf-8",
    )
    print(f"pin updated — {len(obs)} page(s)")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit(selftest() if arg == "--selftest" else update() if arg == "--update" else check())
