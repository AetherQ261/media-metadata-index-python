from src.media_index import decide_delivery


def test_wide_source_is_sent_to_creator_delivery() -> None:
    decision = decide_delivery("cover-17", {"width": 1920, "height": 1080, "format": "jpeg"})

    assert decision.status == "ready_for_delivery"
    assert decision.format == "jpeg"


def test_small_or_portrait_source_needs_processing() -> None:
    decision = decide_delivery("portrait-3", {"width": 900, "height": 1200, "format": "png"})

    assert decision.status == "needs_processing"
