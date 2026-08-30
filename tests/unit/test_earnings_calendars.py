"""Tests for the earnings calendar strategy described by Volatility Vibes."""

from datetime import date

import pytest

from src.analysis.earnings_calendars import (
    AnnouncementTiming,
    EarningsCalendarParameters,
    EarningsCalendarScreen,
    OhlcvBar,
    Recommendation,
    TermPoint,
    analyze_screen,
    choose_calendar,
    interpolate_iv,
    yang_zhang_volatility,
)

pytestmark = pytest.mark.unit


def _bars(count: int = 31) -> list[OhlcvBar]:
    """Return a deterministic price path with non-zero intraday and overnight moves."""
    bars = []
    previous_close = 100.0
    for index in range(count):
        open_price = previous_close * (1.001 if index % 2 == 0 else 0.999)
        close = open_price * (1.006 if index % 3 == 0 else 0.996)
        bars.append(
            OhlcvBar(
                open=open_price,
                high=max(open_price, close) * 1.004,
                low=min(open_price, close) * 0.996,
                close=close,
                volume=2_000_000 + index,
            )
        )
        previous_close = close
    return bars


def test_published_defaults_are_named_and_visible():
    parameters = EarningsCalendarParameters()

    assert parameters.minimum_average_volume == 1_500_000
    assert parameters.minimum_iv_to_realized_volatility == 1.25
    assert parameters.maximum_term_structure_slope == pytest.approx(-0.00406)
    assert parameters.term_structure_target_dte == 45
    assert parameters.target_calendar_gap_days == 30
    assert parameters.entry_minutes_before_close == 15
    assert parameters.exit_minutes_after_open == 15
    assert parameters.reference_debit_fraction == pytest.approx(0.06)


@pytest.mark.parametrize(
    ("volume_passes", "ratio_passes", "slope_passes", "expected"),
    [
        (True, True, True, Recommendation.RECOMMENDED),
        (True, False, True, Recommendation.CONSIDER),
        (False, True, True, Recommendation.CONSIDER),
        (False, False, True, Recommendation.AVOID),
        (True, True, False, Recommendation.AVOID),
        (True, False, False, Recommendation.AVOID),
        (False, True, False, Recommendation.AVOID),
        (False, False, False, Recommendation.AVOID),
    ],
)
def test_recommendation_matches_the_video_rule(volume_passes, ratio_passes, slope_passes, expected):
    screen = EarningsCalendarScreen.from_flags(
        average_volume_passes=volume_passes,
        iv_to_realized_volatility_passes=ratio_passes,
        term_structure_slope_passes=slope_passes,
    )

    assert screen.recommendation is expected


def test_interpolate_iv_uses_linear_term_structure():
    points = [TermPoint(dte=5, iv=0.80), TermPoint(dte=30, iv=0.50), TermPoint(dte=55, iv=0.40)]

    assert interpolate_iv(points, 45) == pytest.approx(0.44)


def test_interpolate_iv_requires_the_target_to_be_bracketed():
    points = [TermPoint(dte=5, iv=0.80), TermPoint(dte=30, iv=0.50)]

    with pytest.raises(ValueError, match="bracket"):
        interpolate_iv(points, 45)


def test_analyze_screen_calculates_metrics_and_expected_move():
    bars = _bars()
    realized_volatility = yang_zhang_volatility(bars)
    points = [
        TermPoint(dte=5, iv=realized_volatility * 3.0),
        TermPoint(dte=30, iv=realized_volatility * 1.30),
        TermPoint(dte=45, iv=realized_volatility * 1.20),
    ]

    result = analyze_screen(
        term_structure=points,
        price_history=bars,
        underlying_price=100.0,
        front_dte=5,
        front_call_mid=4.0,
        front_put_mid=3.5,
    )

    assert result.metrics.average_volume == pytest.approx(sum(bar.volume for bar in bars[-30:]) / 30)
    assert result.metrics.iv30_to_realized_volatility == pytest.approx(1.30)
    assert result.metrics.expected_move_fraction == pytest.approx(0.075)
    assert result.filters.average_volume is True
    assert result.filters.iv_to_realized_volatility is True
    assert result.filters.term_structure_slope is True
    assert result.recommendation is Recommendation.RECOMMENDED


def test_choose_calendar_uses_first_post_event_expiry_and_nearest_30_day_back_expiry():
    plan = choose_calendar(
        earnings_date=date(2026, 9, 2),
        expirations=[
            date(2026, 9, 4),
            date(2026, 9, 11),
            date(2026, 10, 2),
            date(2026, 10, 9),
        ],
        strikes_by_expiration={
            date(2026, 9, 4): [115.0, 120.0, 125.0],
            date(2026, 10, 2): [110.0, 120.0, 130.0],
            date(2026, 10, 9): [115.0, 120.0, 125.0],
        },
        underlying_price=121.30,
    )

    assert plan.front_expiration == date(2026, 9, 4)
    assert plan.back_expiration == date(2026, 10, 2)
    assert plan.strike == 120.0
    assert plan.calendar_gap_days == 28


def test_choose_calendar_rejects_an_expiry_set_without_a_post_event_back_month():
    with pytest.raises(ValueError, match="back expiration"):
        choose_calendar(
            earnings_date=date(2026, 9, 2),
            expirations=[date(2026, 9, 4)],
            strikes_by_expiration={date(2026, 9, 4): [120.0]},
            underlying_price=121.30,
        )


def test_choose_calendar_only_uses_strikes_listed_in_both_expirations():
    plan = choose_calendar(
        earnings_date=date(2026, 9, 2),
        expirations=[date(2026, 9, 4), date(2026, 10, 2)],
        strikes_by_expiration={
            date(2026, 9, 4): [120.0, 125.0],
            date(2026, 10, 2): [115.0, 125.0],
        },
        underlying_price=121.0,
    )

    assert plan.strike == 125.0


def test_before_open_allows_same_day_expiry_but_after_close_does_not():
    expirations = [date(2026, 9, 4), date(2026, 10, 2), date(2026, 10, 9)]
    strikes = {expiration: [120.0] for expiration in expirations}

    before_open = choose_calendar(
        earnings_date=date(2026, 9, 4),
        announcement_timing=AnnouncementTiming.BEFORE_OPEN,
        expirations=expirations,
        strikes_by_expiration=strikes,
        underlying_price=120.0,
    )
    after_close = choose_calendar(
        earnings_date=date(2026, 9, 4),
        announcement_timing=AnnouncementTiming.AFTER_CLOSE,
        expirations=expirations,
        strikes_by_expiration=strikes,
        underlying_price=120.0,
    )

    assert before_open.front_expiration == date(2026, 9, 4)
    assert after_close.front_expiration == date(2026, 10, 2)


def test_custom_realized_volatility_window_does_not_change_iv30_target():
    bars = _bars(21)
    realized_volatility = yang_zhang_volatility(bars, window=20)
    parameters = EarningsCalendarParameters(realized_volatility_window=20)

    result = analyze_screen(
        term_structure=[
            TermPoint(dte=5, iv=0.80),
            TermPoint(dte=20, iv=realized_volatility),
            TermPoint(dte=30, iv=realized_volatility * 1.30),
            TermPoint(dte=45, iv=0.40),
        ],
        price_history=bars,
        underlying_price=100.0,
        front_dte=5,
        front_call_mid=4.0,
        front_put_mid=3.5,
        parameters=parameters,
    )

    assert result.metrics.iv30 == pytest.approx(realized_volatility * 1.30)
    assert result.metrics.iv30_to_realized_volatility == pytest.approx(1.30)


def test_screen_uses_explicit_post_event_front_dte():
    bars = _bars()
    result = analyze_screen(
        term_structure=[
            TermPoint(dte=2, iv=1.50),
            TermPoint(dte=5, iv=0.80),
            TermPoint(dte=30, iv=0.30),
            TermPoint(dte=45, iv=0.20),
        ],
        price_history=bars,
        underlying_price=100.0,
        front_dte=5,
        front_call_mid=4.0,
        front_put_mid=3.5,
    )

    assert result.metrics.front_dte == 5
    assert result.metrics.front_iv == 0.80
