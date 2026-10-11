from app.agents.case_processor import CaseInput, process_case
from app.models import case as status

COMPLETE = "Please book 2x40HC from Rotterdam to Singapore. Cargo ready date 2026-11-15, commodity: machinery parts."


def case(description: str, reason: str = "booking_create", subject: str = "Booking") -> CaseInput:
    return CaseInput(id="c1", subject=subject, description=description, reason=reason, from_address="a@example.com")


async def test_unowned_reason_is_skipped():
    result = await process_case(case("Invoice charged twice", reason="invoice_dispute"))
    assert result.status == status.SKIPPED


async def test_shadow_mode_proposes_instead_of_writing():
    result = await process_case(case(COMPLETE), write_mode="shadow")
    assert result.status == status.HITL_REQUIRED
    assert result.shadow
    assert result.hitl_action == "booking_create"
    assert result.proposed_call["arguments"]["origin"] == "Rotterdam"
    assert "Shadow mode" in result.hitl_reason


async def test_live_mode_books_a_confident_complete_case():
    result = await process_case(case(COMPLETE), write_mode="live")
    assert result.status == status.BOOKED
    assert result.booking_ref.startswith("BK-2")
    assert not result.shadow


async def test_live_mode_still_escalates_an_incomplete_case():
    result = await process_case(
        case("We need space for 3x20GP from Shanghai to Los Angeles next month."), write_mode="live"
    )
    assert result.status == status.HITL_REQUIRED
    assert result.hitl_action == "manual_review"
    assert "cargo_ready_date" in result.extraction["missing_fields"]
    assert "below threshold" in result.hitl_reason
    assert result.extraction["destination"] == "Los Angeles"


def test_mock_extractor_stops_the_route_at_time_words():
    from app.agents.llm.mock_scripts import extract_fields

    fields = extract_fields("3x20GP from Shanghai to Los Angeles next month")
    assert (fields["origin"], fields["destination"]) == ("Shanghai", "Los Angeles")


async def test_amend_proposal_carries_the_changes():
    result = await process_case(
        case("Please change the container count to 6 on booking BK-100002.", reason="booking_amend")
    )
    assert result.proposed_call == {
        "tool": "booking_amend",
        "arguments": {"booking_ref": "BK-100002", "changes": {"container_count": 6}},
    }


async def test_reason_and_intent_mismatch_is_escalated():
    result = await process_case(
        case("Please cancel BK-100001 and book a new one from Antwerp to Busan.", reason="booking_amend")
    )
    assert result.status == status.HITL_REQUIRED and result.hitl_action == "manual_review"
    assert "reads as" in result.hitl_reason
