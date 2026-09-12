"""Demo account scaffolding definitions.

Only identities here — NO PASSWORDS. Passwords are supplied at seed time from
environment (``DEMO_SEED_PASSWORD``) or generated randomly once and printed to
stdout; only PBKDF2 hashes are stored.
"""

from __future__ import annotations

from typing import Dict, List

DEMO_USERS: List[Dict] = [
    {
        "username": "admin",
        "display_name": "Arya Verma",
        "role": "admin",
        "title": "Platform Administrator",
        "email": "arya.admin@cryptotrace.local",
    },
    {
        "username": "senior_investigator",
        "display_name": "Rohan Iyer",
        "role": "senior_investigator",
        "title": "Senior Investigator",
        "email": "rohan.senior@cryptotrace.local",
    },
    {
        "username": "investigator",
        "display_name": "Aarav Kapoor",
        "role": "investigator",
        "title": "Investigator",
        "email": "aarav.inv@cryptotrace.local",
    },
    {
        "username": "analyst",
        "display_name": "Meera Nair",
        "role": "analyst",
        "title": "Blockchain Intelligence Analyst",
        "email": "meera.analyst@cryptotrace.local",
    },
    {
        "username": "reviewer",
        "display_name": "Kabir Shah",
        "role": "reviewer",
        "title": "Case Reviewer",
        "email": "kabir.review@cryptotrace.local",
    },
]