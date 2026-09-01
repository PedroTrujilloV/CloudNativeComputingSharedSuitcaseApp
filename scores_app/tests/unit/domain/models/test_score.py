from datetime import datetime, timezone

from domain.models.score import Score


def test_score_model_stores_values():
    now = datetime.now(timezone.utc)
    score = Score(
        id="11111111-1111-1111-1111-111111111111",
        offer_id="22222222-2222-2222-2222-222222222222",
        value=150.5,
        created_at=now,
        updated_at=now,
    )

    assert score.id == "11111111-1111-1111-1111-111111111111"
    assert score.offer_id == "22222222-2222-2222-2222-222222222222"
    assert score.value == 150.5
    assert score.created_at == now
    assert score.updated_at == now


def test_score_model_generates_id_by_default():
    score = Score(
        offer_id="22222222-2222-2222-2222-222222222222",
        value=0.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert len(score.id) == 36
    assert score.id != ""


def test_score_model_equality_uses_all_fields():
    now = datetime.now(timezone.utc)
    common_kwargs = {
        "id": "11111111-1111-1111-1111-111111111111",
        "offer_id": "22222222-2222-2222-2222-222222222222",
        "value": 100.0,
        "created_at": now,
        "updated_at": now,
    }
    score_a = Score(**common_kwargs)
    score_b = Score(**common_kwargs)
    score_c = Score(**{**common_kwargs, "value": 99.9})

    assert score_a == score_b
    assert score_a != score_c
