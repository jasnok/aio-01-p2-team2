"""Compare public localhost catalog GETs; no credentials or model requests."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontend.clients import backend_client as api
from frontend.clients.http_client import close_client
from frontend.core.config import get_frontend_settings
from scripts.benchmark_provenance import capture, finish

CODE_PATHS = ['scripts/benchmark_frontend_http.py', 'scripts/benchmark_provenance.py',
              'frontend/clients/http_client.py', 'frontend/clients/backend_client.py',
              'frontend/core/config.py']
PACKAGES = ['httpx', 'httpcore']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new output path; existing evidence is preserved')
    settings = get_frontend_settings()
    base = settings.normalized_backend_url
    parsed = urlsplit(base)
    if parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.username or parsed.password:
        raise ValueError('Configure a credential-free localhost backend')
    provenance = capture(CODE_PATHS, PACKAGES)
    results = {}
    close_client()
    try:
        for category in ('housing', 'labor', 'consumer'):
            path = '/api/catalog/' + category
            samples = {'new_client': [], 'pooled_client': []}
            reference = None
            for index in range(12):
                payloads = []
                order = ['new_client', 'pooled_client'] if index % 2 == 0 else ['pooled_client', 'new_client']
                for variant in order:
                    start = perf_counter()
                    if variant == 'new_client':
                        response = httpx.request('GET', base + path, timeout=settings.frontend_request_timeout_seconds)
                        response.raise_for_status()
                        payload = response.json()
                    else:
                        payload = api._request('GET', path)
                    elapsed = (perf_counter() - start) * 1000
                    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                    digest = hashlib.sha256(encoded).hexdigest()
                    if reference is None:
                        reference = digest
                    if digest != reference or payload.get('category') != category or not isinstance(payload.get('terms'), list):
                        raise AssertionError('Catalog changed or response contract differs')
                    payloads.append(digest)
                    if index >= 2:
                        samples[variant].append(elapsed)
                assert payloads[0] == payloads[1]
            results[category] = {
                'warmup_pairs': 2, 'measured_pairs': 10, 'equal_pairs_including_warmup': 12,
                'response_sha256': reference,
                **{name: {'samples_ms': values, 'median_ms': median(values)} for name, values in samples.items()},
            }
    finally:
        close_client()
    report = {
        'scope': 'public localhost catalog HTTP GET; includes client construction/close on old path; excludes model and retrieval',
        'authenticated_requests': 0, 'model_requests': 0,
        'provenance': finish(provenance, CODE_PATHS, PACKAGES), 'results': results,
    }
    if not report['provenance']['code_unchanged_during_measurement']:
        raise RuntimeError('Measured code changed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    for category, result in results.items():
        print(category, {name: round(result[name]['median_ms'], 4) for name in ('new_client', 'pooled_client')})


if __name__ == '__main__':
    main()
