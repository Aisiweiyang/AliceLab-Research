import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
import pytest
from alicelab.changepoints import detect, one_break_posterior, exact_posterior, cusum_stat
from alicelab.event_study import empirical_window_pvalue, run_event_study, load_prices
from alicelab.pricing import link_factor, pareto_front_mask, decompose, threshold_prices, hedonic_reference_prices, validate_panel
from alicelab.cli import demo, run_spec
from alicelab.provenance import sha256


def test_original_detector_regressions():
    result = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('regression_detector.py'))], capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ALL PASS' in result.stdout


def test_min_seg_is_forwarded():
    x = np.r_[np.zeros(8), np.ones(45)]
    t, p = one_break_posterior(x, min_seg=5)
    assert detect(x, min_seg=5)['t'] == t[np.argmax(p)]


@pytest.mark.parametrize('series', [[], [1, 2], [0] * 30 + [np.nan], [[1, 2], [3, 4]]])
def test_invalid_series_rejected(series):
    with pytest.raises(ValueError):
        exact_posterior(series)


def test_cusum_includes_first_observation():
    assert cusum_stat([3.0], nu=.5)[0] == 2.5


def test_link_excludes_invalid_ratios_from_overlap():
    old = pd.Series([0., 10., np.nan], index=list('abc'))
    new = pd.Series([20., 20., 20.], index=list('abc'))
    flags = pd.Series(True, index=list('abc'))
    result = link_factor(old, new, flags, flags, min_overlap=2)
    assert result['n_overlap'] == 1 and result['kappa'] == 2 and result['weak_link']


def test_pareto_keeps_duplicates():
    assert pareto_front_mask([[1, 2], [1, 2], [2, 1], [3, 4]]).tolist() == [True, True, False, True]


def panel():
    return pd.DataFrame([{'month': month, 'model': f'm{i}', 'price': float((i+1)**2 * scale), 'capability': float(i+1),
                          'benchmark_version': 'test-v1', 'currency': 'USD'}
                         for month, scale in [('2024-01', 1), ('2024-02', .5)] for i in range(4)])


def test_price_indices_known_answers():
    p = panel()
    d = decompose(p).iloc[0]
    assert abs(d['within'] - np.log(.5)) < 1e-12 and abs(d['residual']) < 1e-12
    h = hedonic_reference_prices(p, reference=2)
    assert np.allclose(h.beta, 2) and np.allclose(h.reference_price, [4, 2])
    minimum = threshold_prices(p, [100])
    assert minimum.price.isna().all() and (minimum.n_models == 0).all()


def test_composition_entry():
    p = panel()
    p.loc[len(p)] = ['2024-02', 'cheap', .01, 4., 'test-v1', 'USD']
    d = decompose(p).iloc[0]
    assert d['n_entry'] == 1 and d['residual'] < 0


def test_cross_version_and_duplicate_rejected():
    p = panel()
    p.loc[0, 'benchmark_version'] = 'different'
    with pytest.raises(ValueError):
        validate_panel(p)
    with pytest.raises(ValueError):
        validate_panel(pd.concat([panel(), panel().iloc[[0]]]))


def test_event_pvalue_uses_single_day_distribution():
    residuals = np.tile([-1., 1.], 200)
    assert empirical_window_pvalue(.5, residuals, 1, n_boot=999) == 1.0
    # A two-session contiguous sum is identically zero for this sequence.
    assert empirical_window_pvalue(.5, residuals, 2, n_boot=999) == .001
    # The discarded implementation compared a 400-day mean to a single day.
    assert empirical_window_pvalue(10, residuals, 1, n_boot=999) > 0


def test_event_model_coefficients_and_boundaries():
    rng = np.random.default_rng(4)
    dates = pd.bdate_range('2020-01-01', periods=340)
    market = rng.normal(0, .01, len(dates))
    firm = .001 + 1.5 * market
    firm[300] += .1
    a = pd.DataFrame({'date': dates, 'ret': firm})
    b = pd.DataFrame({'date': dates, 'ret': market})
    result = run_event_study(a, b, dates[300], n_boot=999)
    assert np.allclose(result.beta, 1.5) and np.allclose(result.car, .1)
    for date in [dates[10], dates[-1] + pd.Timedelta(days=10), dates[-1]]:
        with pytest.raises(ValueError):
            run_event_study(a, b, date)


def test_full_demo_and_provenance(tmp_path):
    out = demo(tmp_path / 'demo')
    for recipe in ['factor_health', 'event_study', 'capability_price']:
        manifest = json.loads((out / recipe / 'manifest.json').read_text())
        assert manifest['source_type'] == 'synthetic'
        for record in manifest['inputs']:
            assert record['sha256'] == sha256(out / 'inputs' / record['file'])
    with pytest.raises(ValueError, match='already exists'):
        demo(out)
    spec_path = out / 'inputs' / 'factor_health.json'
    spec = json.loads(spec_path.read_text())
    spec['parameters']['silently_ignored'] = True
    spec_path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='unknown'):
        run_spec(spec_path, tmp_path / 'rejected')
    assert not (tmp_path / 'rejected').exists()


def test_prices_reject_duplicate_dates(tmp_path):
    path = tmp_path / 'prices.csv'
    pd.DataFrame({'date': ['2020-01-01'] * 2, 'close': [1, 2]}).to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_prices(path)
