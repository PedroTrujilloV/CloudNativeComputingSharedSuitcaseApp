from domain.models.credit_card import CardIssuer
from domain.services.issuer_detection import detect_issuer_from_bin


def test_visa_is_detected_from_the_leading_digit():
    assert detect_issuer_from_bin("4242424242424242") is CardIssuer.VISA
    assert detect_issuer_from_bin("4111111111111111") is CardIssuer.VISA


def test_mastercard_is_detected_from_the_two_digit_prefix():
    assert detect_issuer_from_bin("5555555555554444") is CardIssuer.MASTERCARD
    assert detect_issuer_from_bin("5105105105101007") is CardIssuer.MASTERCARD


def test_mastercard_is_detected_from_the_2221_to_2720_range():
    assert detect_issuer_from_bin("2221000000000009") is CardIssuer.MASTERCARD
    assert detect_issuer_from_bin("2720999999999999") is CardIssuer.MASTERCARD


def test_american_express_is_detected_from_the_two_digit_prefix():
    assert detect_issuer_from_bin("371449635398431") is CardIssuer.AMERICAN_EXPRESS
    assert detect_issuer_from_bin("340000000000009") is CardIssuer.AMERICAN_EXPRESS


def test_discover_is_detected_from_the_documented_prefixes():
    assert detect_issuer_from_bin("6011111111111117") is CardIssuer.DISCOVER
    assert detect_issuer_from_bin("6500000000000014") is CardIssuer.DISCOVER
    assert detect_issuer_from_bin("6221260000000000") is CardIssuer.DISCOVER


def test_diners_club_is_detected_from_the_documented_prefixes():
    assert detect_issuer_from_bin("30569309025904") is CardIssuer.DINERS_CLUB
    assert detect_issuer_from_bin("36399999999999") is CardIssuer.DINERS_CLUB
    assert detect_issuer_from_bin("38520000000006") is CardIssuer.DINERS_CLUB


def test_unrecognized_prefixes_fall_back_to_unknown():
    assert detect_issuer_from_bin("1234567890123") is CardIssuer.UNKNOWN
    assert detect_issuer_from_bin("9999999999999999") is CardIssuer.UNKNOWN


def test_short_numbers_do_not_raise_and_fall_back_to_unknown():
    assert detect_issuer_from_bin("4") is CardIssuer.VISA
    assert detect_issuer_from_bin("3") is CardIssuer.UNKNOWN
