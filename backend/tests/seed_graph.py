"""Seed the scam graph with the plan §5.4 demo ring (Delhi-NCR KYC scam).

Run:   cd backend && uv run python tests/seed_graph.py
Idempotent: re-running merges (does not duplicate) thanks to MERGE semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import IOCItem, ThreatIOCs  # noqa: E402
from app.services import scam_graph  # noqa: E402
from app.services.scam_graph import node_id  # noqa: E402

PHONES = [
    "9876543210",  # primary caller
    "9876543211",  # secondary caller
    "8765432109",  # WhatsApp contact
    "7654321098",  # backup number
    "9988776655",  # new number, 2 days old
    "8877665544",  # victim callback number
    "7766554433",  # another victim
    "6655443322",  # recent addition
]

UPIS = ["sbi-safe@ybl", "kyc-verify@paytm", "ramesh.kumar@okhdfc"]
DOMAINS = ["sbi-kyc-verify.xyz", "rbi-verification.top"]
ACCOUNTS = {"1234567890123": "SBI", "9876543210123": "HDFC"}

PHONE_UPI = [
    ("9876543210", "sbi-safe@ybl"),
    ("9876543211", "sbi-safe@ybl"),
    ("9988776655", "sbi-safe@ybl"),
    ("8765432109", "kyc-verify@paytm"),
    ("8877665544", "kyc-verify@paytm"),
    ("6655443322", "ramesh.kumar@okhdfc"),
]
PHONE_DOMAIN = [
    ("9876543210", "sbi-kyc-verify.xyz"),
    ("7766554433", "sbi-kyc-verify.xyz"),
    ("7654321098", "rbi-verification.top"),
]
UPI_ACCOUNT = [
    ("sbi-safe@ybl", "1234567890123"),
    ("ramesh.kumar@okhdfc", "9876543210123"),
]
SCAMMER_NAMES = {"Officer Kumar": ["9876543210", "9876543211"]}

REPORTS = [
    ("RPT-DEMO-0001", "9876543210", "bank_kyc"),
    ("RPT-DEMO-0002", "9876543211", "bank_kyc"),
    ("RPT-DEMO-0003", "8765432109", "upi_reversal"),
    ("RPT-DEMO-0004", "9876543210", "bank_kyc"),
    ("RPT-DEMO-0005", "7654321098", "fedex"),
    ("RPT-DEMO-0006", "9988776655", "upi_reversal"),
    ("RPT-DEMO-0007", "9876543210", "upi_reversal"),  # 3rd report -> verified
    ("RPT-DEMO-0008", "8765432109", "bank_kyc"),
]


def seed(store) -> dict:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()

    for phone in PHONES:
        store.merge_node(
            "PhoneNumber",
            phone,
            {"last_seen": ts},
            on_create={
                "country_code": "+91",
                "first_seen": ts,
                "report_count": 0,
                "is_verified_scammer": False,
            },
        )
    for upi in UPIS:
        handle, _, bank = upi.partition("@")
        store.merge_node(
            "UPI_ID",
            upi,
            {},
            on_create={"handle": handle, "bank": bank, "first_seen": ts, "report_count": 0},
        )
    for domain in DOMAINS:
        store.merge_node(
            "Domain",
            domain,
            {},
            on_create={"tld": domain.rsplit(".", 1)[-1], "first_seen": ts, "is_suspicious": True},
        )
    for account, bank in ACCOUNTS.items():
        store.merge_node(
            "BankAccount",
            account,
            {},
            on_create={"bank_name": bank, "first_seen": ts, "report_count": 0},
        )
    for name, phones in SCAMMER_NAMES.items():
        store.merge_node("ScammerName", name, {}, on_create={"aliases": [], "first_seen": ts})
        for phone in phones:
            store.merge_edge(node_id("ScammerName", name), "OWNS", node_id("PhoneNumber", phone), {"confidence": 0.8})

    for phone, upi in PHONE_UPI:
        store.merge_edge(node_id("PhoneNumber", phone), "USES_UPI", node_id("UPI_ID", upi), {"first_seen": ts})
    for phone, domain in PHONE_DOMAIN:
        store.merge_edge(node_id("PhoneNumber", phone), "LINKED_TO_DOMAIN", node_id("Domain", domain), {})
    for upi, account in UPI_ACCOUNT:
        store.merge_edge(node_id("UPI_ID", upi), "DEPOSITS_TO", node_id("BankAccount", account), {})

    for report_id, phone, scam_type in REPORTS:
        # ingest_iocs creates the ScamReport node, MERGEs the phone (bumping
        # report_count) and links report -> phone via INVOLVES.
        store.ingest_iocs(
            report_id,
            ThreatIOCs(phone_numbers=[IOCItem(value=phone, source="demo_seed")]),
            source="demo_seed",
            scam_type=scam_type,
            confidence=0.9,
        )

    return store.get_stats()


if __name__ == "__main__":
    store = scam_graph.get_store()
    stats = seed(store)
    print(f"Seeded demo ring. Stats: {stats.model_dump()}")
    print(f"Rings detected: {len(store.detect_rings(min_size=3))}")
