"""Hash inputs and preserve parameters without exposing absolute machine paths."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(directory, inputs, parameters, *, source_type, seed):
    if source_type not in {'synthetic', 'user_supplied'}:
        raise ValueError('source_type must be synthetic or user_supplied')
    from . import __version__
    import numpy, pandas, scipy
    import platform
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        'package_version': __version__,
        'source_type': source_type,
        'seed': seed,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'inputs': [{'file': Path(p).name, 'sha256': sha256(p)} for p in inputs],
        'code_sha256': {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
        'parameters': parameters,
        'environment': {'python': platform.python_version(), 'numpy': numpy.__version__,
                        'pandas': pandas.__version__, 'scipy': scipy.__version__},
        'evidence_boundary': 'Synthetic runs demonstrate software mechanics only.' if source_type == 'synthetic'
                             else 'User-supplied data; provenance and economic validity require independent review.',
    }
    (directory / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return record
