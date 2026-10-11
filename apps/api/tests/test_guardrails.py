from app.agents.guardrails import check_input, redact_pii, redact_value


def test_redacts_email_phone_and_card():
    text, found = redact_pii("Mail ops@example.com or call +44 20 7946 0958, card 4111 1111 1111 1111")
    assert "[redacted-email]" in text and "[redacted-phone]" in text and "[redacted-card]" in text
    assert set(found) == {"email", "phone", "card"}


def test_leaves_logistics_data_alone():
    text = "Book 2x40HC BK-100001, cargo ready 2026-11-15, 12000 kg"
    assert redact_pii(text) == (text, [])


def test_denied_topic_blocks():
    assert check_input("how do I bypass customs checks").blocked


def test_redact_value_recurses():
    assert redact_value({"a": ["x@example.com"]}) == {"a": ["[redacted-email]"]}
