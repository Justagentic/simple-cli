"""Demonstrate a machine caller: subprocess argv, timeout, exit status, JSON."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
cli = Path(__file__).resolve().parent / 'triage.py'
parser = argparse.ArgumentParser(description='Build a local report by consuming the CLI JSON contract')
parser.add_argument('--timeout', type=float, default=10, help='Maximum CLI wait in seconds, default 10')
args = parser.parse_args()
if not 0 < args.timeout < float('inf'):
    parser.error('--timeout must be a finite positive number')
try:
    result = subprocess.run(
        [sys.executable, str(cli), 'list', '--status', 'blocked', '--min-days', '3', '--format', 'json'],
        capture_output=True, text=True, encoding='utf-8', timeout=args.timeout,
    )
except (OSError, subprocess.TimeoutExpired) as error:
    print(f'CLI could not finish: {error}', file=sys.stderr)
    raise SystemExit(1)
if result.returncode != 0:
    print(result.stderr.strip() or f'CLI failed: exit {result.returncode}', file=sys.stderr)
    raise SystemExit(1)
try:
    data = json.loads(result.stdout)
    if data['schema_version'] != 1 or data['command'] != 'list':
        raise ValueError('Unsupported result schema')
    if not isinstance(data['as_of'], str) or not isinstance(data['tickets'], list):
        raise ValueError('Missing result fields')
    if type(data['count']) is not int or data['count'] != len(data['tickets']):
        raise ValueError('Inconsistent result count')
    for item in data['tickets']:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(key), str) for key in ('id', 'owner', 'next_step')
        ) or type(item.get('waiting_days')) is not int:
            raise ValueError('Invalid ticket fields')
except (ValueError, KeyError, TypeError) as error:
    print(f'Invalid CLI result: {error}', file=sys.stderr)
    raise SystemExit(1)
print(f"截至 {data['as_of']}，示例中阻塞至少三天的任务：{data['count']} 条")
for item in data['tickets']:
    print(f"- {item['id']}｜{item['owner']}｜{item['waiting_days']} 天｜{item['next_step']}")
