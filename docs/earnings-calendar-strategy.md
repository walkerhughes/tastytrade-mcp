# Earnings calendar strategy specification

This document codifies the strategy described in the Volatility Vibes video
[This Option Strategy Turned $10k Into $1 Million In One Year](https://www.youtube.com/watch?v=oW6MHjzxHpU)
and audits the linked community implementation in
[earnings_vol_algo.py](https://github.com/namuan/trading-utils/blob/main/earnings_vol_algo.py).
It is a faithful strategy specification, not an endorsement of the video's return claims.

## Timestamped transcript notes

These are paraphrased notes from the video's public auto-captions. They are not a
verbatim republication of the transcript.

| Time | Strategy claim |
| --- | --- |
| 02:20 | Earnings option demand can make event volatility expensive. The trade is short event volatility, not a directional forecast. |
| 03:59 | Compare an ATM short straddle with an ATM long calendar. The calendar sells the first expiry after earnings and buys the same strike farther out. |
| 05:44 | The presenter reports that a back expiry roughly 30 days beyond the front performed best in testing. |
| 06:08 | The claimed study contains about 72,500 earnings events across 4,500 stocks since 2007. |
| 06:26 | Candidate predictors include the IV term-structure slope and ratio, 30-day average share volume, and IV30/RV30. |
| 07:26 | Positions enter about 15 minutes before the close immediately preceding the announcement. |
| 07:35 | The calendar exits about 15 minutes after the first regular-session open following the announcement. |
| 09:54 | The final model uses three factors: term slope, 30-day average volume, and IV30/RV30. |
| 10:53 | The video claims the filter leaves about 10% of calendar events and raises their historical mean return to 7.3% with 28% standard deviation. |
| 12:05 | Full Kelly is presented as 60% for calendars, then explicitly rejected as ruinous. |
| 15:40 | The presenter uses 10% of the stated full-Kelly fraction, equal to a 6% debit allocation, as an illustrative personal sizing rule. |
| 17:39 | All three filters passing is `recommended`; term slope plus exactly one other filter is `consider`; every other combination is `avoid`. |

## Exact screen

The published default parameters are:

| Parameter | Default | Meaning |
| --- | ---: | --- |
| `minimum_average_volume` | 1,500,000 | Mean daily share volume over the latest 30 sessions |
| `minimum_iv_to_realized_volatility` | 1.25 | ATM IV interpolated at 30 DTE divided by annualized 30-session Yang-Zhang volatility |
| `maximum_term_structure_slope` | -0.00406 | Maximum slope in decimal IV per calendar day from the front expiry to 45 DTE |
| `realized_volatility_window` | 30 | Historical sessions used for volume and realized volatility |
| `iv_ratio_target_dte` | 30 | DTE used for the implied-volatility side of IV30/RV30 |
| `term_structure_target_dte` | 45 | Far point used for the slope |
| `target_calendar_gap_days` | 30 | Desired distance from the short expiry to the long expiry |

For front ATM IV `IV_front` at `DTE_front`, linearly interpolated ATM IV `IV45`,
and realized volatility `RV30`:

```text
term_slope = (IV45 - IV_front) / (45 - DTE_front)
iv_rv_ratio = IV30 / RV30
expected_move = (front_ATM_call_mid + front_ATM_put_mid) / spot
```

The expected move is reported by the resource but is not one of the three model
filters. The term-structure ratio is discussed as a predictor but is also absent
from the final rule.

Decision table:

| Volume | IV30/RV30 | Term slope | Label |
| --- | --- | --- | --- |
| Pass | Pass | Pass | `recommended` |
| Pass | Fail | Pass | `consider` |
| Fail | Pass | Pass | `consider` |
| Any other combination | | | `avoid` |

## Trade construction and lifecycle

1. Confirm the earnings date and whether the report is before the open or after
   the close. For an after-close report, the short expiry must be on a later date.
   A same-day expiry is eligible only for a before-open report.
2. Use the first listed expiration after the event for the short option.
3. Choose the listed back expiration closest to 30 calendar days after the short
   expiration.
4. From the strikes listed in both expirations, use the strike nearest spot for
   both legs. The video demonstrates a call calendar, but the volatility screen
   itself does not choose calls versus puts.
5. Enter about 15 minutes before the close immediately before the event.
6. Exit about 15 minutes after the next regular-session open. The video rejects a
   next-close exit because post-earnings drift worsened the historical results.

## Deliberate differences from the linked resource

The implementation in `src.analysis.earnings_calendars` removes or fixes the
following behavior:

- There is no composite score. The resource's normalizations, weekly-expiration
  weight changes, and weights such as 0.5, 0.2, and 0.15 are not specified by the
  video and have no supplied calibration evidence.
- Thresholds, windows, target DTEs, timing, and the fractional-Kelly illustration
  are named parameters rather than literals scattered through the calculation.
- IV30 and IV45 must be bracketed by observed expirations. The resource fetches
  expirations strictly below 45 DTE and then silently clamps IV45 to the last point,
  which can materially distort the slope.
- Realized volatility uses the standard Yang-Zhang overnight, open-to-close, and
  Rogers-Satchell components. The resource labels close-to-close variance as its
  open-to-close component. The 1.25 threshold was published without enough data
  to recalibrate this correction, so this combination remains unvalidated.
- Missing, non-positive, duplicated, and inconsistent inputs fail explicitly.
  They are not converted to a zero metric that can look like a valid observation.
- Before-open and after-close announcements have explicit same-day-expiry behavior.
- The 6% debit fraction is exposed only as the video's reference value. It is not
  an order-sizing instruction and the module never places an order.

Bid/ask quality, open interest, historical earnings moves, event-volatility
decomposition, and scenario expected value should be applied after this screen.
They matter for whether a specific calendar is tradeable, but adding them to the
three-filter label would no longer reproduce the video model.

## Limits of the evidence

The video does not publish the event-level dataset, train/test split, delisting
treatment, exact slippage model, threshold-selection procedure, or out-of-sample
results. Its reported mean returns, Kelly fraction, drawdowns, and growth paths
therefore cannot be independently reproduced from the provided materials. Treat
`recommended` as a screen result that deserves full chain analysis, not as proof
that a trade has positive expected value.
