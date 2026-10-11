# ruff: noqa: E501
"""Payment-identifier detection: it must find real numbers, in disguise too, and leave ordinary numbers alone."""

from __future__ import annotations

import pytest

from payments_rag.guardrails.pii import (
    ACCOUNT,
    CARD,
    IBAN,
    find_pii,
    iban_valid,
    luhn_valid,
    normalize,
    redact,
)

# Published test numbers: each passes Luhn and has a real issuer prefix and length.
VALID_CARDS = [
    "4111111111111111",  # Visa
    "4012888888881881",  # Visa
    "5555555555554444",  # Mastercard
    "2223003122003222",  # Mastercard (2-series)
    "378282246310005",  # American Express, 15 digits
    "6011111111111117",  # Discover
    "3530111333300000",  # JCB
    "30569309025904",  # Diners Club, 14 digits
]
VALID_IBANS = [
    "DE89370400440532013000",
    "GB82WEST12345698765432",
    "FR1420041010050500013M02606",
    "NL91ABNA0417164300",
]


@pytest.mark.parametrize("number", VALID_CARDS)
def test_known_test_cards_are_found(number: str) -> None:
    assert luhn_valid(number)

    result = redact(f"please charge {number} today")

    assert result.text == "please charge [CARD_NUMBER] today"
    assert [f.kind for f in result.findings] == [CARD]


@pytest.mark.parametrize(
    "written", ["4111 1111 1111 1111", "4111-1111-1111-1111", "3782 822463 10005"]
)
def test_spaces_and_hyphens_inside_a_card_number_do_not_hide_it(written: str) -> None:
    assert redact(f"card: {written}.").text == "card: [CARD_NUMBER]."


def test_fullwidth_digits_and_invisible_characters_do_not_hide_a_card() -> None:
    fullwidth = "４１１１ １１１１ １１１１ １１１１"
    zero_width = "4111​1111‍1111 1111"

    assert redact(fullwidth).text == "[CARD_NUMBER]"
    assert redact(zero_width).text == "[CARD_NUMBER]"
    assert normalize("a​b") == "ab"


def test_a_number_that_fails_the_luhn_check_is_not_a_card() -> None:
    assert not luhn_valid("4111111111111112")
    assert not find_pii("number 4111111111111112")


def test_a_luhn_valid_number_with_no_issuer_prefix_is_not_a_card() -> None:
    # 16 digits that pass Luhn but start with 9 (no issuer): ordinary reference numbers look like this.
    candidate = next(f"9{n:015d}" for n in range(10**6) if luhn_valid(f"9{n:015d}"))

    assert luhn_valid(candidate)
    assert not find_pii(f"ref {candidate}")


def test_repeated_digits_and_wrong_lengths_are_not_cards() -> None:
    assert not find_pii("4444444444444444")
    assert not find_pii("41111111111")  # too short
    assert not find_pii("4" + "1" * 22)  # too long


@pytest.mark.parametrize("iban", VALID_IBANS)
def test_valid_ibans_are_found_compact_or_grouped(iban: str) -> None:
    grouped = " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))

    assert iban_valid(iban)
    assert redact(f"pay to {iban} now").text == "pay to [IBAN] now"
    assert redact(f"pay to {grouped} now").text == "pay to [IBAN] now"


def test_ibans_with_a_wrong_checksum_or_length_are_not_found() -> None:
    assert not find_pii("DE89370400440532013001")  # checksum off by one
    assert not find_pii("DE8937040044053201300")  # one digit short for Germany
    assert not find_pii("ISO20022 and PSD2 apply")  # looks like letters-digits, is not an IBAN


@pytest.mark.parametrize(
    "text, number",
    [
        ("my account number 123456789012", "123456789012"),
        ("A/C: 50100123456789", "50100123456789"),
        ("acct no. 9876 5432 1098", "9876 5432 1098"),
        ("Account # 000123456789", "000123456789"),
    ],
)
def test_account_numbers_are_found_by_their_context(text: str, number: str) -> None:
    result = redact(text)

    assert [f.kind for f in result.findings] == [ACCOUNT]
    assert number not in result.text
    assert "[ACCOUNT_NUMBER]" in result.text


def test_a_long_number_without_account_context_is_left_alone() -> None:
    assert not find_pii("reference 123456789012 for the batch")
    assert not find_pii("Accounts are settled daily; account 12 is closed")
    assert not find_pii("account numbers are validated before posting")


def test_a_card_after_the_word_account_is_reported_once_as_a_card() -> None:
    result = redact("account number 4111111111111111")

    assert [f.kind for f in result.findings] == [CARD]
    assert result.text == "account number [CARD_NUMBER]"


def test_several_identifiers_in_one_message() -> None:
    text = "Card 4111 1111 1111 1111, IBAN DE89 3704 0044 0532 0130 00, a/c no 123456789012."

    result = redact(text)

    assert result.text == "Card [CARD_NUMBER], IBAN [IBAN], a/c no [ACCOUNT_NUMBER]."
    assert [f.kind for f in result.findings] == [CARD, IBAN, ACCOUNT]


def test_redaction_removes_every_original_digit_and_is_idempotent() -> None:
    text = "4111 1111 1111 1111 and DE89370400440532013000 and account 123456789012"

    once = redact(text)
    twice = redact(once.text)

    assert not any(ch.isdigit() for ch in once.text.replace("[", "").replace("]", ""))
    assert twice.text == once.text and not twice.found


def test_only_the_requested_kinds_are_redacted() -> None:
    text = "card 4111111111111111 iban DE89370400440532013000"

    assert redact(text, kinds=(IBAN,)).text == "card 4111111111111111 iban [IBAN]"


@pytest.mark.parametrize(
    "sentence",
    [
        "ISO 20022 message pacs.008 settles 1,000,000 INR within T+1.",
        "The dispute must be raised within 120 days of the transaction date.",
        "RBI circular DPSS.CO.PD.No.1810/02.14.003/2019-20 applies from 1 October 2020.",
        "Logged at 2026-10-11T03:03:32 with request 8f3a2c1d.",
        "Call +91 98765 43210 or see section 4.2.3 on page 128.",
        "",
    ],
)
def test_ordinary_payment_text_is_not_flagged(sentence: str) -> None:
    assert redact(sentence).text == sentence


def test_a_lower_case_iban_is_found_too() -> None:
    assert redact("pay de89 3704 0044 0532 0130 00 please").text == "pay [IBAN] please"
    assert redact("pay gb82west12345698765432").text == "pay [IBAN]"
