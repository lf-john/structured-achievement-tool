"""Tests for src.agents.critic_agent."""

from src.agents.critic_agent import (
    ACRating,
    CriticResponse,
    validate_ratings,
)


class TestValidateRatings:
    def test_empty_ratings_passes(self):
        response = CriticResponse(ratings=[])
        result = validate_ratings(response, ["AC1"])
        assert result.passed is True
        assert result.average == 0.0

    def test_all_high_ratings_pass(self):
        response = CriticResponse(
            ratings=[
                ACRating(ac_id="AC-1", ac_name="Tests pass", rating=9, justification="Good"),
                ACRating(ac_id="AC-2", ac_name="Clean code", rating=8, justification="OK"),
            ]
        )
        result = validate_ratings(response, ["Tests pass", "Clean code"])
        assert result.passed is True
        assert result.average == 8.5

    def test_low_individual_fails(self):
        response = CriticResponse(
            ratings=[
                ACRating(ac_id="AC-1", ac_name="Tests pass", rating=9, justification="Good"),
                ACRating(ac_id="AC-2", ac_name="Clean code", rating=3, justification="Bad"),
            ]
        )
        result = validate_ratings(response, ["Tests pass", "Clean code"])
        assert result.passed is False
        assert len(result.failing_acs) == 1
        assert result.failing_acs[0]["ac_id"] == "AC-2"

    def test_low_average_fails(self):
        response = CriticResponse(
            ratings=[
                ACRating(ac_id="AC-1", rating=6, justification="Meh"),
                ACRating(ac_id="AC-2", rating=6, justification="Meh"),
            ]
        )
        result = validate_ratings(response, ["AC1", "AC2"])
        assert result.passed is False
        assert result.average == 6.0

    def test_detects_missing_acs(self):
        response = CriticResponse(
            ratings=[
                ACRating(ac_id="AC-1", rating=8, justification="OK"),
            ]
        )
        result = validate_ratings(response, ["First AC", "Second AC", "Third AC"])
        assert len(result.missing_acs) == 2

    def test_message_on_pass(self):
        response = CriticResponse(
            ratings=[
                ACRating(ac_id="AC-1", rating=8, justification="OK"),
            ]
        )
        result = validate_ratings(response, ["First AC"])
        assert "All criteria met" in result.message

    def test_message_on_fail(self):
        response = CriticResponse(
            ratings=[
                ACRating(ac_id="AC-1", rating=3, justification="Bad"),
            ]
        )
        result = validate_ratings(response, ["First AC"])
        assert "below" in result.message.lower()


class TestCriticResponse:
    def test_empty_response(self):
        r = CriticResponse()
        assert r.ratings == []
        assert r.overall_assessment == ""

    def test_with_ratings(self):
        r = CriticResponse(
            ratings=[ACRating(ac_id="AC-1", rating=7, justification="OK")],
            overall_assessment="Decent work",
            recommendations=["Fix typo"],
        )
        assert len(r.ratings) == 1
        assert r.recommendations == ["Fix typo"]


class TestACRating:
    def test_valid_rating(self):
        r = ACRating(ac_id="AC-1", rating=7, justification="OK")
        assert r.rating == 7

    def test_min_rating(self):
        r = ACRating(rating=1)
        assert r.rating == 1

    def test_max_rating(self):
        r = ACRating(rating=10)
        assert r.rating == 10
