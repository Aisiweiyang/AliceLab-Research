"""Descriptive market-model event study with horizon-matched empirical inference."""
import numpy as np
import pandas as pd


def load_prices(path):
    frame = pd.read_csv(path)
    price = 'adjclose' if 'adjclose' in frame else 'close'
    if not {'date', price}.issubset(frame.columns):
        raise ValueError('prices require date and adjclose (preferred) or close')
    frame['date'] = pd.to_datetime(frame.date, errors='raise')
    frame = frame.sort_values('date')
    values = pd.to_numeric(frame[price], errors='raise')
    if frame.date.isna().any() or frame.date.duplicated().any() or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('prices must be finite, positive and uniquely dated')
    frame['ret'] = values.pct_change(fill_method=None)
    return frame[['date', 'ret']].dropna()


def empirical_window_pvalue(observed_sum, residuals, horizon, *, n_boot=4999, seed=20260910):
    """Sample centered contiguous residual windows of the SAME horizon as the CAR.

    Preserves within-window serial dependence. Overlapping historical windows are
    resampled with replacement. This is a descriptive empirical-tail reference,
    not a causal or parameter-uncertainty-adjusted significance test.
    """
    residuals = np.asarray(residuals, dtype=float)
    if residuals.ndim != 1 or not np.isfinite(residuals).all() or not np.isfinite(observed_sum):
        raise ValueError('finite observed sum and one-dimensional residuals required')
    if not isinstance(horizon, int) or horizon < 1 or len(residuals) < horizon or n_boot < 99:
        raise ValueError('invalid horizon, history or number of draws (minimum 99)')
    centered = residuals - residuals.mean()
    sums = np.convolve(centered, np.ones(horizon), mode='valid')
    rng = np.random.default_rng(seed)
    draws = rng.choice(sums, size=n_boot, replace=True)
    return float((1 + np.count_nonzero(np.abs(draws) >= abs(observed_sum))) / (n_boot + 1))


def run_event_study(firm, market, event_date, *, estimation=230, gap=20, horizons=(1, 2, 6), n_boot=4999, seed=20260910):
    data = firm.merge(market, on='date', how='inner', suffixes=('_firm', '_market')).sort_values('date').reset_index(drop=True)
    if estimation < 30 or gap < 0:
        raise ValueError('estimation >= 30 and gap >= 0 required')
    if not len(data) or data.date.duplicated().any():
        raise ValueError('require nonempty, uniquely dated common returns')
    if not np.isfinite(data[['ret_firm', 'ret_market']]).all().all():
        raise ValueError('returns must be finite')
    requested = pd.Timestamp(event_date)
    index = data.index[data.date >= requested]
    if not len(index):
        raise ValueError('event date is after the available data')
    i = int(index[0])
    if i < estimation + gap:
        raise ValueError('insufficient pre-event history')
    if not horizons or any(not isinstance(h, int) or h < 1 for h in horizons) or i + max(horizons) > len(data):
        raise ValueError('invalid horizons or incomplete event window')
    estimate = data.iloc[i-gap-estimation:i-gap]
    x = np.column_stack([np.ones(len(estimate)), estimate.ret_market])
    if np.linalg.matrix_rank(x) < 2:
        raise ValueError('market estimation returns have no variation')
    alpha, beta = np.linalg.lstsq(x, estimate.ret_firm, rcond=None)[0]
    residuals = estimate.ret_firm.to_numpy() - x @ np.array([alpha, beta])
    ar = data.ret_firm - alpha - beta * data.ret_market
    rows = []
    for horizon in horizons:
        car = float(ar.iloc[i:i+horizon].sum())
        p = empirical_window_pvalue(car, residuals, horizon, n_boot=n_boot, seed=seed)
        rows.append({'requested_date': str(requested.date()), 'reaction_date': str(data.date.iloc[i].date()),
                     'horizon_sessions': horizon, 'car': car, 'empirical_p': p,
                     'alpha': float(alpha), 'beta': float(beta), 'n_estimation': len(estimate),
                     'method': 'market_model_horizon_matched_empirical_reference'})
    return pd.DataFrame(rows)
