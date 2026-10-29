"""Run registered research recipes against explicit CSV inputs."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .event_study import load_prices, run_event_study
from .pricing import threshold_prices, decompose, hedonic_reference_prices, validate_panel, pareto_front_mask
from .provenance import write_manifest


def run_spec(path, out=None):
    path = Path(path).resolve()
    spec = json.loads(path.read_text(encoding='utf-8-sig'))
    required = {'schema_version', 'recipe', 'hypothesis', 'source_type', 'seed', 'inputs', 'parameters'}
    if not isinstance(spec, dict) or set(spec) != required or spec['schema_version'] != 1:
        raise ValueError('spec must have exactly the documented schema_version=1 fields')
    if not isinstance(spec['hypothesis'], str) or not spec['hypothesis'].strip():
        raise ValueError('a nonempty hypothesis is required')
    if spec['source_type'] not in {'synthetic', 'user_supplied'} or not isinstance(spec['seed'], int) or spec['seed'] < 0:
        raise ValueError('invalid source_type or nonnegative integer seed')
    if not isinstance(spec['inputs'], dict) or any(not isinstance(v, str) for v in spec['inputs'].values()):
        raise ValueError('inputs must map names to CSV path strings')
    inputs = {k: (path.parent / v).resolve() for k, v in spec['inputs'].items()}
    params = spec['parameters']
    recipe = spec['recipe']
    contracts = {
        'factor_health': ({'series'}, {'column', 'min_seg', 'lam', 'k_max', 'standardize'}),
        'event_study': ({'firm', 'market'}, {'event_date', 'estimation', 'gap', 'horizons', 'n_boot'}),
        'capability_price': ({'panel'}, {'thresholds', 'reference', 'min_models'}),
    }
    if recipe not in contracts:
        raise ValueError('unknown recipe')
    input_keys, parameter_keys = contracts[recipe]
    if set(inputs) != input_keys or not isinstance(params, dict) or set(params) - parameter_keys:
        raise ValueError('unknown or missing input keys / unknown parameters')
    if not all(p.is_file() for p in inputs.values()):
        raise ValueError('an input CSV does not exist; paths are relative to the spec')
    if out is None:
        raise ValueError('--out is required')
    output = Path(out).resolve()
    if output.exists():
        raise ValueError('output directory already exists; use a new run directory')
    # Validate and compute before creating output files.
    tables = {}
    result = None
    if recipe == 'factor_health':
        frame = pd.read_csv(inputs['series'])
        parameters = dict(params)
        column = parameters.pop('column', 'ic')
        if column not in frame:
            raise ValueError(f'missing series column: {column}')
        parameters.setdefault('standardize', True)
        # Exact posterior supports scale normalization explicitly.
        from .changepoints import exact_posterior
        series = pd.to_numeric(frame[column], errors='raise').to_numpy()
        posterior = exact_posterior(series, **parameters)
        result = {'break_count_posterior': posterior['k_dist'].tolist(),
                  'mode_position_given_one_break': int(posterior['ts'][np.argmax(posterior['loc1_post'])]),
                  'note': 'Offline, full-series inference; not a real-time trading signal.'}
        tables['location_posterior.csv'] = pd.DataFrame({'position': posterior['ts'], 'probability': posterior['loc1_post']})
    elif recipe == 'event_study':
        parameters = dict(params)
        if 'event_date' not in parameters:
            raise ValueError('event_date is required')
        tables['event_results.csv'] = run_event_study(load_prices(inputs['firm']), load_prices(inputs['market']), seed=spec['seed'], **parameters)
    else:
        panel = validate_panel(pd.read_csv(inputs['panel']))
        tables['threshold_prices.csv'] = threshold_prices(panel, params.get('thresholds', [10, 20, 40]))
        tables['decomposition.csv'] = decompose(panel)
        tables['hedonic.csv'] = hedonic_reference_prices(panel, params.get('reference', 10), params.get('min_models', 4))
        last = panel[panel.month == panel.month.max()].copy()
        tables['frontier.csv'] = last[pareto_front_mask(last[['price', 'capability']])]
    output.mkdir(parents=True)
    for name, frame in tables.items():
        frame.to_csv(output / name, index=False)
    if result is not None:
        (output / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    # Copy the actual specification for inspection; input paths remain relative to original spec.
    (output / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_manifest(output, [path, *inputs.values()], {'recipe': recipe, 'hypothesis': spec['hypothesis'], **params},
                   source_type=spec['source_type'], seed=spec['seed'])
    return output


def demo(out):
    """Build synthetic inputs and run all three actual recipe paths."""
    output = Path(out).resolve()
    if output.exists():
        raise ValueError('demo output already exists; use a new directory')
    inputs = output / 'inputs'
    inputs.mkdir(parents=True)
    rng = np.random.default_rng(20260910)
    signal = rng.normal(0, 1, 120)
    signal[60:] += 2
    pd.DataFrame({'ic': signal}).to_csv(inputs / 'factor.csv', index=False)
    dates = pd.bdate_range('2020-01-01', periods=360)
    market = rng.normal(.0002, .012, len(dates))
    firm = .0001 + 1.2 * market + rng.normal(0, .008, len(dates))
    firm[300] -= .08
    for name, returns in [('firm', firm), ('market', market)]:
        pd.DataFrame({'date': dates, 'adjclose': 100 * np.cumprod(1 + returns)}).to_csv(inputs / f'{name}.csv', index=False)
    rows = []
    for t, month in enumerate(pd.period_range('2024-01', periods=6, freq='M')):
        for j in range(6):
            rows.append({'month': str(month), 'model': f'synthetic-{j}', 'price': float((j+1)**1.2 * .9**t),
                         'capability': 10 * (j+1), 'benchmark_version': 'synthetic-v1', 'currency': 'USD'})
    pd.DataFrame(rows).to_csv(inputs / 'prices.csv', index=False)
    recipes = {
        'factor_health': ({'series': 'factor.csv'}, {'column': 'ic', 'min_seg': 15, 'standardize': True}),
        'event_study': ({'firm': 'firm.csv', 'market': 'market.csv'}, {'event_date': str(dates[300].date()), 'estimation': 230, 'gap': 20, 'n_boot': 999}),
        'capability_price': ({'panel': 'prices.csv'}, {'thresholds': [10, 20, 40], 'reference': 10}),
    }
    for recipe, (files, parameters) in recipes.items():
        spec = {'schema_version': 1, 'recipe': recipe, 'hypothesis': 'Synthetic mechanics demonstration; no economic inference.',
                'source_type': 'synthetic', 'seed': 20260910, 'inputs': files, 'parameters': parameters}
        spec_path = inputs / f'{recipe}.json'
        spec_path.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
        run_spec(spec_path, output / recipe)
    (output / 'README.txt').write_text('SYNTHETIC DATA ONLY. These results verify software mechanics, not market performance, current model prices or paper reproduction.\n', encoding='utf-8')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description='AliceLab portable research recipes')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='run a JSON recipe on supplied CSV inputs')
    run.add_argument('--spec', required=True)
    run.add_argument('--out', required=True)
    example = sub.add_parser('demo', help='run all recipes with explicitly synthetic inputs')
    example.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        result = demo(args.out) if args.command == 'demo' else run_spec(args.spec, args.out)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f'error: {exc}\n')
    print(result)
