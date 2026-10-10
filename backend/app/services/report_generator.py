"""Cybercrime report generator — Phase 5.6.

Fills the plan's cybercrime.gov.in template + 1930 helpline script from
structured incident data. Narrative is LLM-generated when available, with a
deterministic template narrative as fallback so the demo never stalls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.schemas import ReportRequest, ReportResponse, ThreatIOCs

logger = logging.getLogger("mirage.report")

NA = "[Not available]"

SCAM_TYPE_READABLE = {
    "bank_kyc": "Bank KYC Fraud",
    "upi_reversal": "UPI Reversal Scam",
    "fedex": "Fake Parcel / FedEx Scam",
    "job_offer": "Fake Job Offer Scam",
    "lottery": "Lottery / Prize Scam",
    "relative_distress": "Relative in Distress Scam",
    "otp_phishing": "OTP Phishing",
    "investment": "Investment Scam",
    "romance": "Romance Scam",
    "electricity": "Electricity Bill Scam",
    "impersonation": "Impersonation Scam",
    "qr_code": "QR Code Scam",
    "unknown": "Cyber Fraud",
}

_SCAM_GOAL = {
    "bank_kyc": "complete my KYC or my account would be blocked",
    "upi_reversal": "reverse a fake UPI transaction",
    "fedex": "pay a customs/parcel clearance fee",
    "job_offer": "pay a registration or uniform fee for a fake job",
    "lottery": "claim a fake prize",
    "relative_distress": "send money for an emergency",
    "otp_phishing": "share my OTP",
    "investment": "invest in a fraudulent scheme",
    "romance": "send money to someone I met online",
    "electricity": "pay a fake electricity bill",
    "impersonation": "send money to someone impersonating an official",
    "qr_code": "scan a QR code",
    "unknown": "transfer money",
}


def _fallback_narrative(data: ReportRequest, iocs: ThreatIOCs) -> str:
    """Deterministic narrative built from the structured data (no LLM needed)."""
    parts: list[str] = []
    when = " ".join(filter(None, [data.incident_date, data.incident_time])) or "an earlier date"
    parts.append(f"On {when}, I was contacted by a scammer")
    if iocs.phone_numbers:
        parts.append(f"on phone number {iocs.phone_numbers[0].value}")
    parts.append(".")

    readable = SCAM_TYPE_READABLE.get(data.scam_type or "unknown", "Cyber Fraud")
    goal = _SCAM_GOAL.get(data.scam_type or "unknown", "transfer money")
    parts.append(
        f" The caller pretended to be an official and tried to get me to {goal}. "
        f"This appears to be a case of {readable}."
    )

    if iocs.scammer_names:
        parts.append(f' The scammer identified themselves as "{iocs.scammer_names[0]}".')
    if iocs.urls and iocs.urls[0].context:
        parts.append(f" They directed me to the fraudulent website {iocs.urls[0].value}.")
    elif iocs.domains:
        parts.append(f" They shared a fraudulent link ({iocs.domains[0].value}).")
    if iocs.upi_ids:
        parts.append(f" The UPI ID used for collection was {iocs.upi_ids[0].value}.")
    if iocs.bank_accounts:
        parts.append(
            f" They provided bank account number {iocs.bank_accounts[0].value}"
            + (f" (IFSC: {iocs.ifsc_codes[0].value})" if iocs.ifsc_codes else "")
            + "."
        )
    if iocs.reference_numbers:
        parts.append(f' They quoted reference/case number "{iocs.reference_numbers[0]}".')
    if iocs.amounts:
        parts.append(f" An amount of {iocs.amounts[0]} was demanded.")

    if data.amount_lost and data.amount_lost > 0:
        parts.append(
            f" Unfortunately, I lost ₹{data.amount_lost:,.0f} in the transaction"
            + (f" (ref: {data.transaction_ref})" if data.transaction_ref else "")
            + "."
        )
    else:
        parts.append(
            " I recognized the fraud and did not share any details or lose money."
        )

    if iocs.domains:
        parts.append(
            f" Domain analysis shows {iocs.domains[0].value} is not an official website."
        )
    return "".join(parts)


def _llm_narrative(data: ReportRequest, iocs: ThreatIOCs) -> str | None:
    """LLM narrative (plan §5.6 step 2). Returns None if unavailable."""
    from app.clients.llm import chat_completion

    payload = {
        "scammer_iocs": {
            "phone_numbers": [i.value for i in iocs.phone_numbers],
            "upi_ids": [i.value for i in iocs.upi_ids],
            "urls": [i.value for i in iocs.urls],
            "domains": [i.value for i in iocs.domains],
            "bank_accounts": [i.value for i in iocs.bank_accounts],
            "ifsc_codes": [i.value for i in iocs.ifsc_codes],
            "names": iocs.scammer_names,
            "reference_numbers": iocs.reference_numbers,
            "amounts": iocs.amounts,
        },
        "scam_type": data.scam_type,
        "incident_date": data.incident_date,
        "incident_time": data.incident_time,
        "mode_of_contact": data.mode_of_contact,
        "amount_demanded": data.amount_demanded,
        "amount_lost": data.amount_lost,
        "transaction_ref": data.transaction_ref,
    }
    import json

    try:
        raw = chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Convert this scam incident data into a formal complaint narrative "
                        "for the Indian cyber crime portal. Be factual, chronological, and "
                        "specific. Output ONLY the narrative text, no headings or JSON."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            timeout=25,
        )
        text = (raw or "").strip()
        return text or None
    except Exception as exc:
        logger.warning("LLM narrative unavailable, using template (%s)", exc)
        return None


def _first(items: list, attr: str = "value") -> str:
    return str(getattr(items[0], attr)) if items else NA


def _template_report(data: ReportRequest, iocs: ThreatIOCs, narrative: str, report_id: str) -> str:
    honeypot = bool(data.honeypot_session_id)
    header = "INTELLIGENCE REPORT (HONEYPOT SESSION)" if honeypot else "CYBER CRIME COMPLAINT"

    name = "Anonymous" if data.anonymous else (data.user_name or NA)
    phone = NA if data.anonymous else (data.user_phone or NA)
    city = data.user_city or NA
    email = NA if data.anonymous else (data.user_email or NA)

    amount_demanded = data.amount_demanded or (iocs.amounts[0] if iocs.amounts else NA)
    if data.amount_lost and data.amount_lost > 0:
        amount_lost = f"₹{data.amount_lost:,.0f}"
    else:
        amount_lost = "₹0 (no loss)"

    urgent_note = ""
    if data.amount_lost and data.amount_lost > 0:
        urgent_note = (
            "\n⚠️ MONEY WAS LOST — call 1930 IMMEDIATELY. The faster you report, "
            "the higher the chance of recovering your funds.\n"
        )

    bank_line = NA
    if iocs.bank_accounts or iocs.ifsc_codes or iocs.bank_names:
        bank_line = ", ".join(filter(lambda s: s != NA, [
            iocs.bank_names[0] if iocs.bank_names else NA,
            f"A/c: {iocs.bank_accounts[0].value}" if iocs.bank_accounts else NA,
            f"IFSC: {iocs.ifsc_codes[0].value}" if iocs.ifsc_codes else NA,
        ]))

    actions = []
    if iocs.phone_numbers:
        actions.append(f"Block the scammer's phone number: {iocs.phone_numbers[0].value}")
    if iocs.upi_ids:
        actions.append(f"Freeze the scammer's UPI ID: {iocs.upi_ids[0].value}")
    if iocs.domains:
        actions.append(f"Investigate the fraudulent domain: {iocs.domains[0].value}")
    if iocs.bank_accounts:
        actions.append(f"Take action against the scammer's bank account: {iocs.bank_accounts[0].value}")
    if not actions:
        actions.append("Investigate the reported incident based on the narrative")

    domain_note = (
        f"- Domain analysis: {iocs.domains[0].value} registered recently (not official)"
        if iocs.domains
        else "- Domain analysis: [Not available]"
    )

    return f"""{header}
=====================

Report ID: {report_id}
Date Generated: {datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")}
Report Generated By: Mirage AI Scam Shield

COMPLAINANT DETAILS:
Name: {name}
Phone: {phone}
City: {city}
Email: {email}

INCIDENT DETAILS:
Type of Fraud: {SCAM_TYPE_READABLE.get(data.scam_type or 'unknown', 'Cyber Fraud')}
Mode of Contact: {data.mode_of_contact or NA}
Scammer's Phone Number: {_first(iocs.phone_numbers)}
Scammer's UPI ID: {_first(iocs.upi_ids)}
Scammer's Bank Details: {bank_line}
Fraudulent URL: {_first(iocs.urls)}
Scammer Names: {', '.join(iocs.scammer_names) if iocs.scammer_names else NA}
Reference Numbers: {', '.join(iocs.reference_numbers) if iocs.reference_numbers else NA}
Locations Mentioned: {', '.join(iocs.locations) if iocs.locations else NA}

AMOUNT INVOLVED:
Amount Demanded: {amount_demanded}
Amount Lost: {amount_lost}
Transaction Reference: {data.transaction_ref or NA}
{urgent_note}
NARRATIVE:
{narrative}

EVIDENCE:
- Call recording: [attach if available]
- Screenshots: [attach if available]
- Message logs: [attach if available]
{domain_note}

ACTION REQUESTED:
{chr(10).join(f'{i}. {a}' for i, a in enumerate(actions, start=1))}

This report was auto-generated by Mirage AI Scam Shield.
For assistance, call the National Cyber Crime Helpline: 1930"""


def _helpline_script(data: ReportRequest, iocs: ThreatIOCs) -> str:
    name = "Anonymous" if data.anonymous else (data.user_name or "________")
    city = data.user_city or "________"
    phone = _first(iocs.phone_numbers)
    upi = _first(iocs.upi_ids)
    institution = ", ".join(iocs.bank_names) if iocs.bank_names else "a bank/government office"
    goal = _SCAM_GOAL.get(data.scam_type or "unknown", "transfer money")
    if data.amount_lost and data.amount_lost > 0:
        loss = f"Yes. The amount is ₹{data.amount_lost:,.0f}."
    else:
        loss = "No, I did not lose any money."

    return f"""📞 1930 HELPLINE SCRIPT

When you call 1930, say:

"Hello, I want to report a cyber fraud.

My name is {name} from {city}.

I received a scam call on {data.incident_date or '________'} at {data.incident_time or '________'}.

The scammer's number is {phone}.

They pretended to be from {institution} and tried to get me to {goal}.

Their UPI ID is {upi}.

{loss}

Please block this number and UPI ID.

My complaint reference number is ________."

 Tips:
 • Keep this report ID handy: the portal asks for it.
 • Report online too: cybercrime.gov.in (menu → "Report Cyber Financial Fraud").
 • Do NOT delete the messages or call log — screenshots help the investigator.
"""


def generate_report(data: ReportRequest, iocs: ThreatIOCs | None = None) -> ReportResponse:
    """Build report_text + helpline_script (plan §5.6)."""
    resolved = iocs if iocs is not None else data.iocs
    report_id = f"RPT-{datetime.now(timezone.utc).strftime('%Y')}-{datetime.now(timezone.utc).strftime('%m%d')}-{str(abs(hash((data.user_phone, data.incident_date, resolved.total()))) % 100000).zfill(5)}"

    narrative = _llm_narrative(data, resolved) or _fallback_narrative(data, resolved)

    return ReportResponse(
        report_id=report_id,
        report_text=_template_report(data, resolved, narrative, report_id),
        helpline_script=_helpline_script(data, resolved),
        urgent=bool(data.amount_lost and data.amount_lost > 0),
    )
