# Contributing

Use Python 3.11+, install `pip install -e '.[dev]'`, and run `python -m pytest -q`.
Run `python -m alicelab demo --out outputs/new-demo` after changing recipe execution.

Keep research hypotheses, data identity, parameters and evidence boundaries explicit.
Add known-answer tests for numerical changes and regression tests for reported defects.
Never add credentials, private datasets, brokerage/account records or unlicensed third-party snapshots.
Discuss changes that add data sources or external integrations before implementing them.
