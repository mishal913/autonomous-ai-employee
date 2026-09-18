from app.tools import (
    calculate_lead_score,
)


def test_maximum_score_is_100():

    result = calculate_lead_score(
        industry_fit=20,
        company_size_fit=20,
        ai_need=20,
        growth_signal=20,
        contact_potential=20,
    )

    assert result["success"] is True

    assert result[
        "total_score"
    ] == 100


def test_zero_score_is_0():

    result = calculate_lead_score(
        industry_fit=0,
        company_size_fit=0,
        ai_need=0,
        growth_signal=0,
        contact_potential=0,
    )

    assert result["success"] is True

    assert result[
        "total_score"
    ] == 0


def test_dhl_example_score_is_85():

    result = calculate_lead_score(
        industry_fit=18,
        company_size_fit=19,
        ai_need=17,
        growth_signal=16,
        contact_potential=15,
    )

    assert result["success"] is True

    assert result[
        "total_score"
    ] == 85


def test_each_dimension_is_preserved():

    result = calculate_lead_score(
        industry_fit=18,
        company_size_fit=19,
        ai_need=17,
        growth_signal=16,
        contact_potential=15,
    )

    scores = result[
        "scores"
    ]

    assert scores[
        "industry_fit"
    ] == 18

    assert scores[
        "company_size_fit"
    ] == 19

    assert scores[
        "ai_need"
    ] == 17

    assert scores[
        "growth_signal"
    ] == 16

    assert scores[
        "contact_potential"
    ] == 15
