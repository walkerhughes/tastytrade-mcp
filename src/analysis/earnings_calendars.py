"""Faithful, configurable implementation of the Volatility Vibes earnings screen.

The screen is intentionally separate from market-data acquisition and order handling.
It describes the strategy in https://www.youtube.com/watch?v=oW6MHjzxHpU and keeps
the three published recommendation filters distinct from execution-quality checks.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from math import isfinite, log, sqrt
from statistics import variance
from typing import Iterable, Mapping, Sequence


class Recommendation(StrEnum):
    """Recommendation labels used by the video's companion script."""

    RECOMMENDED = "recommended"
    CONSIDER = "consider"
    AVOID = "avoid"


class AnnouncementTiming(StrEnum):
    """When an earnings announcement occurs relative to the regular session."""

    BEFORE_OPEN = "before_open"
    AFTER_CLOSE = "after_close"


@dataclass(frozen=True)
class EarningsCalendarParameters:
    """Published strategy constants, named so they can be tested and recalibrated.

    The thresholds reproduce the companion resource. They are historical model
    parameters, not universal constants or a guarantee of positive expectancy.
    """

    minimum_average_volume: float = 1_500_000
    minimum_iv_to_realized_volatility: float = 1.25
    maximum_term_structure_slope: float = -0.00406
    realized_volatility_window: int = 30
    annualization_days: int = 252
    iv_ratio_target_dte: int = 30
    term_structure_target_dte: int = 45
    target_calendar_gap_days: int = 30
    entry_minutes_before_close: int = 15
    exit_minutes_after_open: int = 15
    full_kelly_fraction: float = 0.60
    kelly_fraction_multiplier: float = 0.10

    @property
    def reference_debit_fraction(self) -> float:
        """The video's illustrative 10 percent fractional-Kelly value: 10% of 60%."""
        return self.full_kelly_fraction * self.kelly_fraction_multiplier


@dataclass(frozen=True)
class TermPoint:
    """At-the-money implied volatility at one expiration."""

    dte: int
    iv: float


@dataclass(frozen=True)
class OhlcvBar:
    """One regular-session price and volume observation."""

    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ScreenMetrics:
    """Raw metrics used by the strategy decision."""

    average_volume: float
    realized_volatility: float
    iv30: float
    iv30_to_realized_volatility: float
    front_dte: int
    front_iv: float
    iv45: float
    term_structure_slope: float
    expected_move_fraction: float


@dataclass(frozen=True)
class ScreenFilters:
    """Pass or fail state for the exact three recommendation filters."""

    average_volume: bool
    iv_to_realized_volatility: bool
    term_structure_slope: bool


@dataclass(frozen=True)
class EarningsCalendarScreen:
    """Metrics, filter results, and the resulting recommendation."""

    filters: ScreenFilters
    recommendation: Recommendation
    metrics: ScreenMetrics | None = None

    @classmethod
    def from_flags(
        cls,
        *,
        average_volume_passes: bool,
        iv_to_realized_volatility_passes: bool,
        term_structure_slope_passes: bool,
        metrics: ScreenMetrics | None = None,
    ) -> "EarningsCalendarScreen":
        filters = ScreenFilters(
            average_volume=average_volume_passes,
            iv_to_realized_volatility=iv_to_realized_volatility_passes,
            term_structure_slope=term_structure_slope_passes,
        )
        if all((average_volume_passes, iv_to_realized_volatility_passes, term_structure_slope_passes)):
            recommendation = Recommendation.RECOMMENDED
        elif term_structure_slope_passes and (average_volume_passes ^ iv_to_realized_volatility_passes):
            recommendation = Recommendation.CONSIDER
        else:
            recommendation = Recommendation.AVOID
        return cls(filters=filters, recommendation=recommendation, metrics=metrics)


@dataclass(frozen=True)
class CalendarPlan:
    """Expiry and strike selection specified by the video."""

    front_expiration: date
    back_expiration: date
    strike: float
    calendar_gap_days: int
    entry_minutes_before_close: int
    exit_minutes_after_open: int


def interpolate_iv(term_structure: Sequence[TermPoint], target_dte: int) -> float:
    """Linearly interpolate ATM IV, requiring observed points around the target."""
    points = _validated_term_structure(term_structure)
    if target_dte < points[0].dte or target_dte > points[-1].dte:
        raise ValueError(f"term structure must bracket {target_dte} DTE")

    for left, right in zip(points, points[1:], strict=False):
        if target_dte == left.dte:
            return left.iv
        if left.dte < target_dte <= right.dte:
            weight = (target_dte - left.dte) / (right.dte - left.dte)
            return left.iv + weight * (right.iv - left.iv)
    return points[-1].iv


def yang_zhang_volatility(
    price_history: Sequence[OhlcvBar],
    *,
    window: int = 30,
    annualization_days: int = 252,
) -> float:
    """Calculate annualized Yang-Zhang volatility from ``window + 1`` bars.

    This uses the standard overnight, open-to-close, and Rogers-Satchell
    components. The linked resource instead labels close-to-close variance as
    the open-to-close component, which is treated here as an implementation bug.
    """
    if window < 2:
        raise ValueError("Yang-Zhang window must be at least 2")
    if len(price_history) < window + 1:
        raise ValueError(f"Yang-Zhang volatility requires at least {window + 1} bars")
    if annualization_days <= 0:
        raise ValueError("annualization_days must be positive")

    bars = list(price_history[-(window + 1) :])
    for bar in bars:
        _validate_bar(bar)

    overnight_returns: list[float] = []
    open_to_close_returns: list[float] = []
    rogers_satchell_terms: list[float] = []
    for previous, current in zip(bars, bars[1:], strict=False):
        overnight_returns.append(log(current.open / previous.close))
        open_to_close_returns.append(log(current.close / current.open))
        high_to_open = log(current.high / current.open)
        high_to_close = log(current.high / current.close)
        low_to_open = log(current.low / current.open)
        low_to_close = log(current.low / current.close)
        rogers_satchell_terms.append(high_to_open * high_to_close + low_to_open * low_to_close)

    k = 0.34 / (1.34 + (window + 1) / (window - 1))
    daily_variance = (
        variance(overnight_returns)
        + k * variance(open_to_close_returns)
        + (1 - k) * (sum(rogers_satchell_terms) / window)
    )
    return sqrt(max(daily_variance, 0.0) * annualization_days)


def analyze_screen(
    *,
    term_structure: Sequence[TermPoint],
    price_history: Sequence[OhlcvBar],
    underlying_price: float,
    front_dte: int,
    front_call_mid: float,
    front_put_mid: float,
    parameters: EarningsCalendarParameters | None = None,
) -> EarningsCalendarScreen:
    """Compute the three published filters and recommendation for one event."""
    params = parameters or EarningsCalendarParameters()
    points = _validated_term_structure(term_structure)
    front = next((point for point in points if point.dte == front_dte), None)
    if front is None:
        raise ValueError("front_dte must identify an observed post-event expiration")
    if front.dte >= params.term_structure_target_dte:
        raise ValueError("front expiration must be before the term-structure target")
    if len(price_history) < params.realized_volatility_window + 1:
        raise ValueError("insufficient price history for the realized-volatility window")
    _require_positive("underlying_price", underlying_price)
    _require_non_negative("front_call_mid", front_call_mid)
    _require_non_negative("front_put_mid", front_put_mid)

    realized_volatility = yang_zhang_volatility(
        price_history,
        window=params.realized_volatility_window,
        annualization_days=params.annualization_days,
    )
    if realized_volatility == 0:
        raise ValueError("realized volatility must be positive")

    iv30 = interpolate_iv(points, params.iv_ratio_target_dte)
    iv45 = interpolate_iv(points, params.term_structure_target_dte)
    term_slope = (iv45 - front.iv) / (params.term_structure_target_dte - front.dte)
    average_volume = sum(bar.volume for bar in price_history[-params.realized_volatility_window :]) / (
        params.realized_volatility_window
    )
    metrics = ScreenMetrics(
        average_volume=average_volume,
        realized_volatility=realized_volatility,
        iv30=iv30,
        iv30_to_realized_volatility=iv30 / realized_volatility,
        front_dte=front.dte,
        front_iv=front.iv,
        iv45=iv45,
        term_structure_slope=term_slope,
        expected_move_fraction=(front_call_mid + front_put_mid) / underlying_price,
    )
    return EarningsCalendarScreen.from_flags(
        average_volume_passes=metrics.average_volume >= params.minimum_average_volume,
        iv_to_realized_volatility_passes=(
            metrics.iv30_to_realized_volatility >= params.minimum_iv_to_realized_volatility
        ),
        term_structure_slope_passes=metrics.term_structure_slope <= params.maximum_term_structure_slope,
        metrics=metrics,
    )


def choose_calendar(
    *,
    earnings_date: date,
    expirations: Iterable[date],
    strikes_by_expiration: Mapping[date, Iterable[float]],
    underlying_price: float,
    announcement_timing: AnnouncementTiming = AnnouncementTiming.AFTER_CLOSE,
    parameters: EarningsCalendarParameters | None = None,
) -> CalendarPlan:
    """Select the first post-event expiry, a roughly 30-day back expiry, and ATM strike."""
    params = parameters or EarningsCalendarParameters()
    _require_positive("underlying_price", underlying_price)
    expiration_dates = sorted(set(expirations))
    if announcement_timing is AnnouncementTiming.BEFORE_OPEN:
        front_candidates = [expiration for expiration in expiration_dates if expiration >= earnings_date]
    else:
        front_candidates = [expiration for expiration in expiration_dates if expiration > earnings_date]
    if not front_candidates:
        raise ValueError("no expiration occurs after the earnings event")

    front = front_candidates[0]
    back_candidates = [expiration for expiration in expiration_dates if expiration > front]
    if not back_candidates:
        raise ValueError("no back expiration occurs after the front expiration")
    back = min(
        back_candidates,
        key=lambda expiration: (abs((expiration - front).days - params.target_calendar_gap_days), expiration),
    )

    front_strikes = set(strikes_by_expiration.get(front, ()))
    back_strikes = set(strikes_by_expiration.get(back, ()))
    valid_strikes = sorted(front_strikes.intersection(back_strikes))
    if not valid_strikes:
        raise ValueError("front and back expirations must share at least one strike")
    for strike in valid_strikes:
        _require_positive("strike", strike)
    strike = min(valid_strikes, key=lambda value: (abs(value - underlying_price), value))

    return CalendarPlan(
        front_expiration=front,
        back_expiration=back,
        strike=strike,
        calendar_gap_days=(back - front).days,
        entry_minutes_before_close=params.entry_minutes_before_close,
        exit_minutes_after_open=params.exit_minutes_after_open,
    )


def _validated_term_structure(term_structure: Sequence[TermPoint]) -> list[TermPoint]:
    if len(term_structure) < 2:
        raise ValueError("term structure requires at least two expirations")
    points = sorted(term_structure, key=lambda point: point.dte)
    if len({point.dte for point in points}) != len(points):
        raise ValueError("term structure DTE values must be unique")
    for point in points:
        if point.dte <= 0:
            raise ValueError("term structure DTE values must be positive")
        _require_positive("implied volatility", point.iv)
    return points


def _validate_bar(bar: OhlcvBar) -> None:
    for field_name in ("open", "high", "low", "close"):
        _require_positive(field_name, getattr(bar, field_name))
    _require_non_negative("volume", bar.volume)
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.low > bar.high:
        raise ValueError("OHLC values are inconsistent")


def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


def _require_non_negative(name: str, value: float) -> None:
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
