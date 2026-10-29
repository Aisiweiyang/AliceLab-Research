"""Capability-price frontier and descriptive monthly indices; no vendor data bundled."""
import numpy as np
import pandas as pd


def pareto_front_mask(points):
    """Minimize price (column 0), maximize capability (column 1); retain ties."""
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('points must be a finite n-by-2 array')
    weak = (points[:, 0, None] <= points[None, :, 0]) & (points[:, 1, None] >= points[None, :, 1])
    strict = (points[:, 0, None] < points[None, :, 0]) | (points[:, 1, None] > points[None, :, 1])
    return ~(weak & strict).any(axis=0)


def link_factor(scores_old, scores_new, measured_old, measured_new, min_overlap=10):
    """Median positive new/old ratio, counting only valid paired measurements."""
    for values in (scores_old, scores_new, measured_old, measured_new):
        if not values.index.is_unique:
            raise ValueError('model indices must be unique')
    if min_overlap < 1:
        raise ValueError('min_overlap must be positive')
    idx = scores_old.index.intersection(scores_new.index)
    masks = []
    for flags in (measured_old, measured_new):
        flags = flags.reindex(idx)
        if not flags.dropna().map(lambda v: isinstance(v, (bool, np.bool_))).all():
            raise ValueError('measurement flags must be actual booleans')
        masks.append(flags.eq(True))
    old, new = scores_old.reindex(idx), scores_new.reindex(idx)
    valid = masks[0] & masks[1] & np.isfinite(old) & np.isfinite(new) & (old > 0) & (new > 0)
    ratios = new[valid] / old[valid]
    ratios = ratios[np.isfinite(ratios) & (ratios > 0)]
    n = len(ratios)
    return {'kappa': float(ratios.median()) if n else np.nan, 'n_overlap': n,
            'iqr': float(ratios.quantile(.75) - ratios.quantile(.25)) if n else np.nan,
            'weak_link': n < min_overlap}


def validate_panel(panel):
    required = {'month', 'model', 'price', 'capability', 'benchmark_version', 'currency'}
    if not required.issubset(panel.columns) or panel.empty:
        raise ValueError(f'nonempty panel requires columns: {sorted(required)}')
    panel = panel.copy()
    panel['month'] = pd.PeriodIndex(panel['month'], freq='M')
    if panel[list(required)].isna().any().any() or panel.duplicated(['month', 'model']).any():
        raise ValueError('missing values or duplicate model-month keys')
    if panel['benchmark_version'].nunique() != 1 or panel['currency'].nunique() != 1:
        raise ValueError('use one benchmark version and currency per panel; no automatic cross-version stitching')
    for column in ('price', 'capability'):
        panel[column] = pd.to_numeric(panel[column], errors='raise')
        if not np.isfinite(panel[column]).all() or (panel[column] <= 0).any():
            raise ValueError(f'{column} must be finite and positive')
    return panel


def threshold_prices(panel, thresholds=(10.0, 20.0, 40.0)):
    panel = validate_panel(panel)
    rows = []
    for threshold in thresholds:
        if not np.isfinite(threshold) or threshold <= 0:
            raise ValueError('thresholds must be positive and finite')
        for month, group in panel.groupby('month'):
            eligible = group[group.capability >= threshold].sort_values(['price', 'model'])
            row = {'month': str(month), 'threshold': threshold, 'n_models': len(eligible),
                   'price': np.nan, 'model': None}
            if len(eligible):
                best = eligible.iloc[0]
                row.update(price=float(best.price), model=best.model)
            rows.append(row)
    return pd.DataFrame(rows)


def decompose(panel):
    """Matched-model change + residual composition effect; no causal attribution."""
    panel = validate_panel(panel)
    pivot = panel.assign(log_price=np.log(panel.price)).pivot(index='month', columns='model', values='log_price')
    pivot = pivot.reindex(pd.period_range(pivot.index.min(), pivot.index.max(), freq='M'))
    rows = []
    for previous, current in zip(pivot.index[:-1], pivot.index[1:]):
        a, b = pivot.loc[previous], pivot.loc[current]
        common = a.notna() & b.notna()
        change = float(b.mean() - a.mean())
        within = float((b[common] - a[common]).mean()) if common.any() else np.nan
        rows.append({'month': str(current), 'd_index': change, 'within': within,
                     'residual': change - within, 'n_surviving': int(common.sum()),
                     'n_entry': int((b.notna() & a.isna()).sum()),
                     'n_exit': int((a.notna() & b.isna()).sum())})
    return pd.DataFrame(rows, columns=['month', 'd_index', 'within', 'residual', 'n_surviving', 'n_entry', 'n_exit'])


def hedonic_reference_prices(panel, reference=10.0, min_models=4):
    panel = validate_panel(panel)
    if not np.isfinite(reference) or reference <= 0 or min_models < 3:
        raise ValueError('positive reference and min_models >= 3 required')
    rows = []
    for month, group in panel.groupby('month'):
        if len(group) < min_models or group.capability.nunique() < 2:
            continue
        x = np.column_stack([np.ones(len(group)), np.log(group.capability)])
        coefficients = np.linalg.lstsq(x, np.log(group.price), rcond=None)[0]
        rows.append({'month': str(month), 'reference_price': float(np.exp(coefficients[0] + coefficients[1] * np.log(reference))),
                     'beta': float(coefficients[1]), 'n_models': len(group)})
    return pd.DataFrame(rows, columns=['month', 'reference_price', 'beta', 'n_models'])
