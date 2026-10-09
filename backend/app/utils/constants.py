"""Shared constants for URL/domain analysis (Phase 1.2).

Kept in app.utils so both the analyzer and tests can import without
pulling in the service layer.
"""

from __future__ import annotations

# ------------------------------------------------------------------
# Suspicious TLDs — commonly abused by scam operators
# ------------------------------------------------------------------
SUSPICIOUS_TLDS = frozenset({
    ".xyz", ".top", ".click", ".link", ".buzz", ".tk", ".ml", ".ga",
    ".cf", ".gq", ".pw", ".cc", ".ws", ".info", ".icu", ".cam",
    ".loan", ".work",
})

LEGITIMATE_TLDS = frozenset({
    ".co.in", ".in", ".com", ".org", ".gov.in", ".ac.in", ".net",
})

# ------------------------------------------------------------------
# URL shorteners — flag as suspicious because destination is hidden
# ------------------------------------------------------------------
URL_SHORTENER_DOMAINS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
    "is.gd", "buff.ly", "shorturl.at", "cli.gs", "tr.im",
    "vb.ly", "snipurl.com", "cutt.ly", "v.gd", "bc.vc",
})

# ------------------------------------------------------------------
# Brand keywords — if a domain contains one AND is not the official
# domain, it is a lookalike
# ------------------------------------------------------------------
BRAND_KEYWORDS = frozenset({
    "sbi", "hdfc", "icici", "axis", "kotak", "yesbank",
    "pnb", "bankofbaroda", "canara", "idbi", "federal",
    "rbi", "incometax", "uidai", "epassport",
    "jio", "airtel", "vodafone", "bsnl",
    "amazon", "flipkart", "myntra", "meesho",
    "bluedart", "delhivery", "dhl", "fedex", "indiapost",
    "paytm", "phonepe", "razorpay", "billdesk",
})

# ------------------------------------------------------------------
# Official legitimate domains (Indian context) — fast-path check
# ------------------------------------------------------------------
LEGITIMATE_DOMAINS = frozenset({
    # banks
    "sbi.co.in", "sbi.com", "onlinesbi.com",
    "hdfcbank.com", "hdfc.com",
    "icicibank.com",
    "axisbank.com",
    "kotak.com",
    "yesbank.in",
    "pnbindia.in",
    "bankofbaroda.in",
    "canarabank.com",
    "idbibank.in",
    "federalbank.co.in",
    # government
    "rbi.org.in",
    "incometax.gov.in",
    "gov.in",
    "nic.in",
    "uidai.gov.in",
    "epassport.gov.in",
    # telecom
    "jio.com",
    "airtel.in",
    "vodafoneidea.com",
    "bsnl.co.in",
    # e-commerce
    "amazon.in", "amazon.com",
    "flipkart.com",
    "myntra.com",
    "meesho.com",
    # delivery
    "bluedart.com",
    "delhivery.com",
    "dhl.com",
    "fedex.com",
    "indiapost.gov.in",
    "ekartlogistics.com",
    # payments
    "paytm.com",
    "phonepe.com",
    "razorpay.com",
    "billdesk.com",
})

# ------------------------------------------------------------------
# Suspicious path keywords — signal when combined with a
# non-official domain
# ------------------------------------------------------------------
SUSPICIOUS_PATH_KEYWORDS = frozenset({
    "login", "verify", "update", "secure", "confirm",
    "bank", "otp", "kyc",
})
