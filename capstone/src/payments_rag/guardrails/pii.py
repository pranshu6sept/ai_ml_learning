"""Find and redact payment identifiers in text: card numbers, IBANs and bank account numbers.

    from payments_rag.guardrails.pii import redact
    redact("my card is 4111 1111 1111 1111").text   # 'my card is [CARD_NUMBER]'

Each detector validates what it finds, so ordinary numbers are left alone:

* **Card numbers** need 13 to 19 digits, a valid Luhn checksum and a known issuer prefix. About one
  in ten random digit strings passes Luhn alone; the prefix check removes most of those.
* **IBANs** need a country code, the country's length where known, and the mod-97 checksum.
  Lower-case is accepted.
* **Account numbers** have no checksum, so they are found by context only: 9 to 18 digits right
  after words such as "account number" or "a/c". A bare 12-digit number is not flagged.

Text is normalised first (compatibility forms such as full-width digits become ASCII, and
invisible characters are removed) so a full-width number or a zero-width space inside a number does
not hide it. As a result the redacted text is the *normalised* text.

Limits, stated plainly: the account-number rule misses numbers with no nearby keyword; the issuer
prefix list is not exhaustive; a valid example IBAN in a document is redacted like any other, which
is the safe default for output but is a false positive if you only wanted to hide real customers;
nothing here detects names, addresses, phone numbers or Aadhaar numbers.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

CARD = "CARD_NUMBER"
IBAN = "IBAN"
ACCOUNT = "ACCOUNT_NUMBER"
ALL_KINDS = (CARD, IBAN, ACCOUNT)

# IBAN length by country (the SWIFT registry values for common countries).
IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AT": 20, "BE": 16, "BG": 22, "BH": 22, "CH": 21, "CY": 28, "CZ": 24,
    "DE": 22, "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21,
    "HU": 28, "IE": 22, "IL": 23, "IS": 26, "IT": 27, "LI": 21, "LT": 20, "LU": 20, "LV": 21,
    "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "QA": 29, "RO": 24, "SA": 24,
    "SE": 24, "SI": 19, "SK": 24, "TR": 26,
}  # fmt: skip

# Issuer identification prefixes (first digits) with the lengths those cards use.
_CARD_PREFIXES = (
    (r"4", (13, 16, 19)),  # Visa
    (r"5[1-5]|2(?:2[2-9][1-9]|2[3-9]\d|[3-6]\d\d|7[01]\d|720)", (16,)),  # Mastercard
    (r"3[47]", (15,)),  # American Express
    (r"6011|64[4-9]|65", (16, 17, 18, 19)),  # Discover / RuPay-Discover
    (r"60|65|81|82|508", (16,)),  # RuPay
    (r"3(?:0[0-5]|[68])", (14, 16)),  # Diners Club
    (r"35(?:2[89]|[3-8]\d)", (16, 17, 18, 19)),  # JCB
)

_CARD_CANDIDATE = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?![\w-])")
_IBAN_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]{1,4}){2,8}(?![A-Za-z0-9])"
)
_ACCOUNT_CONTEXT = re.compile(
    r"(?i)\b(?:a/c|acct?\.?|account)"  # the keyword
    r"(?:\s+(?:no\.?|number|num|#))?\s*[:#-]?\s*"  # an optional "number" word and separator
    r"(\d(?:[ -]?\d){7,17})(?!\d)"  # 8 to 18 digits, groups allowed
)


@dataclass(frozen=True)
class Finding:
    """One identifier found in the *normalised* text, at [start, end)."""

    kind: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Redaction:
    text: str  # the normalised text with each finding replaced by ``[KIND]``
    findings: tuple[Finding, ...]

    @property
    def found(self) -> bool:
        return bool(self.findings)


def normalize(text: str) -> str:
    """NFKC-normalise and drop invisible format characters (zero-width, joiners, bidi marks)."""
    folded = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")


def luhn_valid(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        n = int(char)
        if index % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _is_card(digits: str) -> bool:
    if len(set(digits)) == 1 or not luhn_valid(digits):
        return False
    return any(
        re.match(prefix, digits) and len(digits) in lengths for prefix, lengths in _CARD_PREFIXES
    )


def iban_valid(compact: str) -> bool:
    """Country length (when known), then mod 97 with the first four characters moved to the end."""
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        return False
    expected = IBAN_LENGTHS.get(compact[:2])
    if expected is not None and len(compact) != expected:
        return False
    rearranged = compact[4:] + compact[:4]
    number = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(number) % 97 == 1


def find_pii(text: str, kinds: tuple[str, ...] = ALL_KINDS) -> list[Finding]:
    """Identifiers in ``text`` (which should already be normalised), sorted, without overlaps."""
    found: list[Finding] = []
    if CARD in kinds:
        for match in _CARD_CANDIDATE.finditer(text):
            digits = re.sub(r"\D", "", match.group())
            if _is_card(digits):
                found.append(Finding(CARD, match.start(), match.end(), match.group()))
    if IBAN in kinds:
        for match in _IBAN_CANDIDATE.finditer(text):
            # The pattern may also swallow following words ("... 00 now"), so try shorter endings.
            groups = match.group().split(" ")
            for count in range(len(groups), 0, -1):
                written = " ".join(groups[:count])
                if iban_valid(written.replace(" ", "").upper()):
                    found.append(
                        Finding(IBAN, match.start(), match.start() + len(written), written)
                    )
                    break
    if ACCOUNT in kinds:
        for match in _ACCOUNT_CONTEXT.finditer(text):
            found.append(Finding(ACCOUNT, match.start(1), match.end(1), match.group(1)))
    found.sort(key=lambda f: (f.start, -(f.end - f.start)))
    result: list[Finding] = []
    for finding in found:  # keep the first (longest) of any overlapping pair
        if not result or finding.start >= result[-1].end:
            result.append(finding)
    return result


def redact(text: str, kinds: tuple[str, ...] = ALL_KINDS) -> Redaction:
    """Normalise ``text`` and replace every identifier with ``[KIND]``."""
    clean = normalize(text)
    findings = find_pii(clean, kinds)
    out, position = [], 0
    for finding in findings:
        out.append(clean[position : finding.start])
        out.append(f"[{finding.kind}]")
        position = finding.end
    out.append(clean[position:])
    return Redaction("".join(out), tuple(findings))
