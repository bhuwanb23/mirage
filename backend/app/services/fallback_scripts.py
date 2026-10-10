"""Pre-written fallback scam scripts (Phase 3.2).

Used when the LLM call fails or returns garbage, so the demo NEVER breaks.
Each template has all 5 stages with {name}/{city}/{bank} placeholders.
"""

from __future__ import annotations

# scam_type -> {
#   "title": ...,
#   "stages": { stage: {"script": ..., "tactic": ...}, ... },
#   "red_flags_planted": [...],
#   "difficulty_level": ...,
# }
FALLBACK_SCRIPTS: dict[str, dict] = {
    "bank_kyc": {
        "title": "Fake {bank} KYC Verification Call",
        "difficulty_level": "medium",
        "stages": {
            "hook": {
                "script": (
                    "Hello, am I speaking with {name}? [pause 2s] Good, good. "
                    "My name is Officer Kumar, I am calling from the {bank} "
                    "customer verification department."
                ),
                "tactic": "Uses your full name to establish instant familiarity",
            },
            "authority": {
                "script": (
                    "This is Officer Kumar from the {bank} fraud department here "
                    "in {city}. [pause 1s] I have your file open in front of me, "
                    "account ending in the last four digits you gave at the branch."
                ),
                "tactic": "Impersonates a specific bank officer with a fake department",
            },
            "isolation": {
                "script": (
                    "Now {name} ji, this is a confidential security matter. "
                    "Please do not discuss this with anyone, not even your family "
                    "members, because of RBI confidentiality rules. [pause 1s]"
                ),
                "tactic": "Prevents the victim from getting a second opinion",
            },
            "urgency": {
                "script": (
                    "Your KYC verification is incomplete and your account will be "
                    "blocked within 30 minutes. [pause 1s] After that your balance "
                    "of two lakh forty five thousand rupees will be frozen."
                ),
                "tactic": "Creates extreme time pressure to prevent rational thinking",
            },
            "payment": {
                "script": (
                    "To verify, I need you to share the OTP you will receive on "
                    "your phone, and your ATM PIN for verification. [pause 1s] "
                    "Quickly please, the system is about to close my window."
                ),
                "tactic": "Demands OTP and PIN — no real bank ever asks for these",
            },
        },
        "red_flags_planted": [
            "Used full name to create false familiarity",
            "Claimed to be from the bank fraud department (banks don't call customers about KYC)",
            "Asked to keep the call secret from family",
            "Threatened account freeze within 30 minutes",
            "Asked for OTP and ATM PIN over the phone",
        ],
    },
    "fedex": {
        "title": "Fake FedEx Customs Parcel Notice",
        "difficulty_level": "medium",
        "stages": {
            "hook": {
                "script": (
                    "Good afternoon, is this {name}? [pause 2s] This is Officer "
                    "Sharma calling from the FedEx customs clearance desk in {city}. "
                    "We are holding a parcel in your name."
                ),
                "tactic": "Uses your name and a familiar brand to seem legitimate",
            },
            "authority": {
                "script": (
                    "The parcel arriving from Thailand contains illegal documents "
                    "and has been flagged by the customs department. [pause 1s] "
                    "A case has been registered under your Aadhaar number."
                ),
                "tactic": "Invokes official institutions and implies criminal involvement",
            },
            "isolation": {
                "script": (
                    "This matter is strictly confidential under the Customs Act. "
                    "If you discuss it with anyone, the case will be compromised "
                    "and your passport will be suspended. [pause 1s]"
                ),
                "tactic": "Threatens consequences for seeking help",
            },
            "urgency": {
                "script": (
                    "You must pay the customs clearance fee of two thousand four "
                    "hundred ninety nine rupees within one hour, or the parcel "
                    "will be automatically transferred to the police. [pause 1s]"
                ),
                "tactic": "Short deadline plus legal threat to induce panic",
            },
            "payment": {
                "script": (
                    "I will send you a UPI link right now. Pay two thousand four "
                    "hundred ninety nine rupees to that link immediately and send "
                    "me the confirmation screenshot. [pause 1s]"
                ),
                "tactic": "Directs payment to a fraudulent UPI link",
            },
        },
        "red_flags_planted": [
            "Impersonates FedEx customs desk",
            "Claims parcel contains illegal items",
            "Threatens passport suspension",
            "One-hour deadline for a small customs fee",
            "Sends a fraudulent UPI link",
        ],
    },
    "relative_distress": {
        "title": "Relative in Distress — Emergency Call",
        "difficulty_level": "hard",
        "stages": {
            "hook": {
                "script": (
                    "Hello? Is this {name}? [pause 2s] This is Inspector Reddy "
                    "from the {city} traffic police. Your {relative_relation} "
                    "{relative_name} has been in a serious accident."
                ),
                "tactic": "Weaponizes family concern — you stop thinking and start worrying",
            },
            "authority": {
                "script": (
                    "We have your {relative_relation} in police custody after the "
                    "accident. He has hit a very influential person's car. "
                    "[pause 1s] The FIR is being registered right now."
                ),
                "tactic": "Police authority plus family emergency overwhelms judgment",
            },
            "isolation": {
                "script": (
                    "Listen carefully — do not call {relative_name}'s phone, it "
                    "is evidence now. And do not tell the rest of the family, "
                    "they will only panic and this will become a media matter. "
                    "[pause 1s]"
                ),
                "tactic": "Cuts the victim off from family who might recognize the scam",
            },
            "urgency": {
                "script": (
                    "The complainant is agreeing to settle if money is paid right "
                    "now, before the court opens in the morning. [pause 1s] "
                    "Otherwise your {relative_relation} spends the night in jail."
                ),
                "tactic": "Overnight deadline creates unbearable emotional pressure",
            },
            "payment": {
                "script": (
                    "Arrange fifty thousand rupees and send it to this UPI ID "
                    "immediately. [pause 1s] I will release your {relative_relation} "
                    "within the hour. Do it fast, the complainant is losing patience."
                ),
                "tactic": "Demands immediate money transfer to an unknown UPI ID",
            },
        },
        "red_flags_planted": [
            "Police officer calls instead of family",
            "Relative suddenly in custody with no way to verify",
            "Forbids calling the relative directly",
            "Settlement before court opens — artificial deadline",
            "UPI transfer to a personal ID, not a court or police account",
        ],
    },
    "rbi_police": {
        "title": "Fake RBI / Police Impersonation Call",
        "difficulty_level": "hard",
        "stages": {
            "hook": {
                "script": (
                    "Is this {name}? [pause 2s] This is Deputy Director Mehta "
                    "from the Reserve Bank of India, {city} zone. I am calling "
                    "about a money laundering investigation."
                ),
                "tactic": "Name-drops India's highest financial authority",
            },
            "authority": {
                "script": (
                    "Your PAN card has been found linked to three fraudulent "
                    "accounts totalling eighteen lakh rupees. [pause 1s] A CBI "
                    "case number has already been generated: RBI-2026-8834."
                ),
                "tactic": "Fake case number and legal accusation make it feel official",
            },
            "isolation": {
                "script": (
                    "This investigation is sealed under the Official Secrets Act. "
                    "If you mention this call to anyone, including your family or "
                    "your bank, you will be named as an accomplice. [pause 1s]"
                ),
                "tactic": "Fear of prosecution keeps the victim silent",
            },
            "urgency": {
                "script": (
                    "The freeze order goes to your bank at 5 PM today. [pause 1s] "
                    "After that every account you hold will be locked for nine "
                    "months pending investigation."
                ),
                "tactic": "End-of-day deadline prevents verification",
            },
            "payment": {
                "script": (
                    "To clear your name, you must transfer two lakh rupees into a "
                    "reserve RBI verification account I will provide. [pause 1s] "
                    "The amount will be returned in 24 hours with a clearance "
                    "certificate."
                ),
                "tactic": "Fake 'safe account' — the classic advance-fee trap",
            },
        },
        "red_flags_planted": [
            "Claims to be RBI Deputy Director — RBI does not call individuals",
            "Fake CBI case number",
            "Threatens arrest as accomplice for telling anyone",
            "Same-day freeze deadline",
            "Demands transfer to a 'safe RBI account'",
        ],
    },
    "job_offer": {
        "title": "Fake Work-from-Home Job Offer",
        "difficulty_level": "easy",
        "stages": {
            "hook": {
                "script": (
                    "Hello {name}, congratulations! [pause 2s] This is Priyanka "
                    "from the HR department of a reputed IT firm in {city}. Your "
                    "profile was shortlisted for a work-from-home position."
                ),
                "tactic": "Flattery and good news lower your guard",
            },
            "authority": {
                "script": (
                    "The package is forty five thousand rupees per month for just "
                    "two hours of data entry work. [pause 1s] We found your "
                    "details on a job portal and the HR head has personally "
                    "approved your candidature."
                ),
                "tactic": "Too-good-to-be-true offer anchored with official-sounding process",
            },
            "isolation": {
                "script": (
                    "This position is confidential until the offer letter is "
                    "issued, so please do not discuss it with your current "
                    "employer or family. [pause 1s] It could void your offer."
                ),
                "tactic": "Prevents the victim from sanity-checking with anyone",
            },
            "urgency": {
                "script": (
                    "We have only three slots left for {city} candidates. "
                    "[pause 1s] I can hold your slot for today only — tomorrow "
                    "it goes to the next candidate on the list."
                ),
                "tactic": "Artificial scarcity forces a fast decision",
            },
            "payment": {
                "script": (
                    "There is a one time registration fee of nine hundred ninety "
                    "nine rupees for the employee ID and kit. [pause 1s] Pay it "
                    "now on this UPI ID and your joining letter will reach you "
                    "in ten minutes."
                ),
                "tactic": "Small 'registration fee' — the real profit of the scam",
            },
        },
        "red_flags_planted": [
            "Unsolicited job offer out of nowhere",
            "High pay for trivial work",
            "Confidentiality clause stops you asking around",
            "Only three slots — false scarcity",
            "Asks for a registration fee — real jobs never do",
        ],
    },
}

# Default relative wording when the user skipped the relative fields.
DEFAULT_RELATIVE = {"relative_name": "Rahul", "relative_relation": "brother"}


def render_fallback(scam_type: str, profile: dict) -> dict:
    """Render a fallback template with the user's profile.

    Returns a dict shaped like the LLM JSON output. Unknown scam types fall
    back to bank_kyc.
    """
    template = FALLBACK_SCRIPTS.get(scam_type) or FALLBACK_SCRIPTS["bank_kyc"]
    values = {
        "name": profile.get("name", "Customer"),
        "first_name": profile.get("first_name") or profile.get("name", "Customer"),
        "city": profile.get("city", "Mumbai"),
        "bank": profile.get("bank_full_name", "State Bank of India"),
        "relative_name": profile.get("relative_name") or DEFAULT_RELATIVE["relative_name"],
        "relative_relation": profile.get("relative_relation")
        or DEFAULT_RELATIVE["relative_relation"],
    }

    stages: dict[str, dict] = {}
    for stage, data in template["stages"].items():
        stages[stage] = {
            "script": data["script"].format(**values),
            "tactic": data["tactic"],
        }

    return {
        "scam_type": scam_type if scam_type in FALLBACK_SCRIPTS else "bank_kyc",
        "title": template["title"].format(**values),
        "stages": stages,
        "full_script": " ".join(s["script"] for s in stages.values()),
        "red_flags_planted": list(template["red_flags_planted"]),
        "difficulty_level": template["difficulty_level"],
    }
