"""Seed the scam graph with the plan §5.4 demo ring (Delhi-NCR KYC scam).

Idempotent: re-running merges (does not duplicate) thanks to MERGE semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import IOCItem, ThreatIOCs
from app.services.scam_graph import node_id

PHONES = [
    "9876543210",
    "9876543211",
    "8765432109",
    "7654321098",
    "9988776655",
    "8877665544",
    "7766554433",
    "6655443322",
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
    ("RPT-DEMO-0007", "9876543210", "upi_reversal"),
    ("RPT-DEMO-0008", "8765432109", "bank_kyc"),
]


def seed(store) -> object:
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
            store.merge_edge(
                node_id("ScammerName", name),
                "OWNS",
                node_id("PhoneNumber", phone),
                {"confidence": 0.8},
            )

    for phone, upi in PHONE_UPI:
        store.merge_edge(
            node_id("PhoneNumber", phone),
            "USES_UPI",
            node_id("UPI_ID", upi),
            {"first_seen": ts},
        )
    for phone, domain in PHONE_DOMAIN:
        store.merge_edge(
            node_id("PhoneNumber", phone),
            "LINKED_TO_DOMAIN",
            node_id("Domain", domain),
            {},
        )
    for upi, account in UPI_ACCOUNT:
        store.merge_edge(node_id("UPI_ID", upi), "DEPOSITS_TO", node_id("BankAccount", account), {})

    for report_id, phone, scam_type in REPORTS:
        store.ingest_iocs(
            report_id,
            ThreatIOCs(phone_numbers=[IOCItem(value=phone, source="demo_seed")]),
            source="demo_seed",
            scam_type=scam_type,
            confidence=0.9,
        )

    return store.get_stats()

# ---------------------------------------------------------------------------
# Phase 7.3 demo dataset — the full hackathon-demo graph.

# Plan 7.3: 15 phones, 8 UPI IDs, 6 domains, 4 bank accounts, 30+ edges,
# 12 scam reports. Superset of the 5.4 ring above (seed_full calls seed
# first, then layers the rest on). Idempotent via MERGE semantics.

PHONES_73 = [
    "9876543212",   # tertiary, same KYC ring as 9876543210/11
    "5544332211",   # job offer, Bangalore
    "4433221100",   # lottery, Chennai
    "3322110099",   # impersonation, Delhi
    "2211009988",   # investment, Hyderabad
    "1100998877",   # electricity, Pune
    "9998877665",   # romance, Jaipur
]

UPIS_73 = [
    "refund-process@ybl",    # UPI reversal ring
    "customs-fee@paytm",     # FedEx ring
    "job-reg@okicici",       # job offer ring
    "prize-claim@ybl",       # lottery ring
    "rbi-secure@paytm",      # impersonation ring
]

DOMAINS_73 = [
    "fedex-india-customs.top",
    "amazon-job-apply.click",
    "kbc-prize-claim.xyz",
    "delhi-police-verify.xyz",
]

ACCOUNTS_73 = {
    "4567890123456": "ICICI",
    "7890123456789": "Axis",
}

# (phone, upi) — 9876543210 already -> sbi-safe@ybl in seed(); 4 phones
# share sbi-safe@ybl per the plan's mule-account talking point.
PHONE_UPI_73 = [
    ("9876543212", "sbi-safe@ybl"),
    ("8765432109", "kyc-verify@paytm"),   # from 5.4 seed, kept for clarity
    ("8877665544", "refund-process@ybl"),
    ("7766554433", "refund-process@ybl"),
    ("6655443322", "customs-fee@paytm"),
    ("5544332211", "job-reg@okicici"),
    ("4433221100", "prize-claim@ybl"),
    ("3322110099", "rbi-secure@paytm"),
    ("2211009988", "ramesh.kumar@okhdfc"),  # mule reuse across rings
]

PHONE_DOMAIN_73 = [
    ("9876543212", "sbi-kyc-verify.xyz"),
    ("6655443322", "fedex-india-customs.top"),
    ("5544332211", "amazon-job-apply.click"),
    ("4433221100", "kbc-prize-claim.xyz"),
    ("3322110099", "delhi-police-verify.xyz"),
    ("3322110099", "rbi-verification.top"),
]

UPI_ACCOUNT_73 = [
    ("customs-fee@paytm", "7890123456789"),
    ("refund-process@ybl", "4567890123456"),
    ("ramesh.kumar@okhdfc", "9876543210123"),  # already in 5.4, idempotent
]

REPORTS_73 = [
    ("RPT-DEMO-0009", "9876543210", "bank_kyc", "telegram", 0.92),
    ("RPT-DEMO-0010", "8877665544", "upi_reversal", "web", 0.85),
    ("RPT-DEMO-0011", "6655443322", "fedex", "telegram", 0.88),
    ("RPT-DEMO-0012", "5544332211", "job_offer", "web", 0.78),
    ("RPT-DEMO-0013", "4433221100", "lottery", "telegram", 0.95),
    ("RPT-DEMO-0014", "3322110099", "impersonation", "guardian", 0.97),
    ("RPT-DEMO-0015", "2211009988", "investment", "telegram", 0.82),
    ("RPT-DEMO-0016", "1100998877", "electricity", "web", 0.75),
    ("RPT-DEMO-0017", "9988776655", "qr_code", "telegram", 0.90),
    ("RPT-DEMO-0018", "9998877665", "relative_distress", "guardian", 0.88),
    ("RPT-DEMO-0019", "9876543211", "bank_kyc", "telegram", 0.91),
    ("RPT-DEMO-0020", "9998877665", "romance", "web", 0.65),
]


def seed_full(store) -> object:
    """Seed the complete 7.3 demo dataset on top of the 5.4 ring.

    Returns store stats. Idempotent — safe to re-run before a demo.
    """
    ts = datetime.now(timezone.utc).isoformat()
    seed(store)  # 5.4 ring first (verified by the Phase 5 tests)

    for phone in PHONES_73:
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
    for upi in UPIS_73:
        handle, _, bank = upi.partition("@")
        store.merge_node(
            "UPI_ID",
            upi,
            {},
            on_create={"handle": handle, "bank": bank, "first_seen": ts, "report_count": 0},
        )
    for domain in DOMAINS_73:
        store.merge_node(
            "Domain",
            domain,
            {},
            on_create={"tld": domain.rsplit(".", 1)[-1], "first_seen": ts, "is_suspicious": True},
        )
    for account, bank in ACCOUNTS_73.items():
        store.merge_node(
            "BankAccount",
            account,
            {},
            on_create={"bank_name": bank, "first_seen": ts, "report_count": 0},
        )

    for phone, upi in PHONE_UPI_73:
        store.merge_edge(
            node_id("PhoneNumber", phone),
            "USES_UPI",
            node_id("UPI_ID", upi),
            {"first_seen": ts},
        )
    for phone, domain in PHONE_DOMAIN_73:
        store.merge_edge(
            node_id("PhoneNumber", phone),
            "LINKED_TO_DOMAIN",
            node_id("Domain", domain),
            {},
        )
    for upi, account in UPI_ACCOUNT_73:
        store.merge_edge(
            node_id("UPI_ID", upi),
            "DEPOSITS_TO",
            node_id("BankAccount", account),
            {},
        )

    for report_id, phone, scam_type, source, confidence in REPORTS_73:
        store.ingest_iocs(
            report_id,
            ThreatIOCs(phone_numbers=[IOCItem(value=phone, source="demo_seed")]),
            source=source,
            scam_type=scam_type,
            confidence=confidence,
        )

    return store.get_stats()
