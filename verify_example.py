"""Black-box checks for the CLI contract, using only fictional local data."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'verification'
OUT.mkdir(exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix='cli-contract-', dir=OUT))
CLI = ROOT / 'triage.py'
records = []


def call(*args):
    result = subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                            text=True, encoding='utf-8', timeout=10, cwd=WORK)
    return result


def check(name, result, code=0, empty_stdout=False):
    assert result.returncode == code, (name, result.returncode, result.stderr)
    if empty_stdout:
        assert not result.stdout, (name, result.stdout)
    records.append({'name': name, 'exit_code': code, 'passed': True})


before = hashlib.sha256((ROOT / 'tickets.json').read_bytes()).hexdigest()
check('help needs no data access', call('--help'))
check('subcommand help', call('list', '--help'))
check('version', call('--version'))
check('missing subcommand', call(), 2, True)
check('negative wait', call('list', '--min-days', '-1'), 2, True)
check('unknown option', call('list', '--typo'), 2, True)
check('unknown status', call('list', '--status', 'unknown'), 2, True)
r = call('list', '--status', 'blocked', '--min-days', '3', '--format', 'json')
check('stable JSON success with clean stderr', r)
assert not r.stderr
data = json.loads(r.stdout)
assert data['schema_version'] == 1 and data['as_of'] == '2026-10-31'
assert [t['id'] for t in data['tickets']] == ['DEMO-104', 'DEMO-101', 'DEMO-102']
assert data['count'] == 3
r = call('list', '--owner', '小林', '--format', 'json')
check('UTF-8 owner filtering', r)
assert json.loads(r.stdout)['count'] == 3
r = call('list', '--owner', '无人', '--format', 'json')
check('empty query is a successful result', r)
assert json.loads(r.stdout)['count'] == 0
r = call('show', 'DEMO-101', '--format', 'json')
check('show record', r)
assert json.loads(r.stdout)['ticket']['waiting_days'] == 5
r = call('show', 'DEMO-999')
check('missing ticket', r, 3, True)
assert json.loads(r.stderr)['error']['code'] == 'NOT_FOUND'
r = call('summary', '--format', 'json')
check('summary matches input', r)
data = json.loads(r.stdout)
assert data['count'] == 8 and data['by_status'] == {'blocked': 5, 'done': 1, 'in-progress': 2}
assert data['longest_waiting_days'] == 7
r = call('summary', '--status', 'blocked', '--min-days', '3', '--format', 'json')
check('summary filters match list filters', r)
assert json.loads(r.stdout)['count'] == 3
check('missing data', call('list', '--data', str(WORK / 'missing.json')), 2, True)
bad = WORK / 'bad.json'
bad.write_text('{broken', encoding='utf-8')
check('bad JSON', call('list', '--data', str(bad)), 2, True)
fixture = json.loads((ROOT / 'tickets.json').read_text(encoding='utf-8'))
fixture['tickets'].append(fixture['tickets'][0].copy())
bad.write_text(json.dumps(fixture, ensure_ascii=False), encoding='utf-8')
check('duplicate ticket validation', call('list', '--data', str(bad)), 2, True)
fixture = json.loads((ROOT / 'tickets.json').read_text(encoding='utf-8'))
fixture['tickets'][0]['waiting_days'] = True
bad.write_text(json.dumps(fixture, ensure_ascii=False), encoding='utf-8')
check('boolean is not a valid wait count', call('list', '--data', str(bad)), 2, True)
check('export format must be JSON', call('list', '--output', str(WORK / 'wrong.txt')), 2, True)
export = WORK / '含 空格的导出.json'
r = call('list', '--status', 'blocked', '--min-days', '3', '--format', 'json', '--output', str(export))
check('UTF-8 export with spaced path', r, 0, True)
assert 'Export created' in r.stderr
assert json.loads(export.read_text(encoding='utf-8'))['count'] == 3
original = export.read_bytes()
check('refuse file overwrite', call('list', '--format', 'json', '--output', str(export)), 4, True)
assert export.read_bytes() == original
check('missing output directory', call('list', '--format', 'json', '--output', str(WORK / 'absent' / 'out.json')), 4, True)
r = subprocess.run([sys.executable, str(ROOT / 'daily_report.py')], capture_output=True,
                   text=True, encoding='utf-8', timeout=15, cwd=WORK)
check('machine caller from a different cwd', r)
assert '3 条' in r.stdout and 'DEMO-104' in r.stdout
r = subprocess.run([sys.executable, str(ROOT / 'daily_report.py'), '--timeout', '0.001'],
                   capture_output=True, text=True, encoding='utf-8', timeout=15, cwd=WORK)
check('machine caller stops on local subprocess timeout', r, 1, True)
assert 'CLI could not finish' in r.stderr
assert hashlib.sha256((ROOT / 'tickets.json').read_bytes()).hexdigest() == before
records.append({'name': 'input dataset unchanged', 'passed': True})
(OUT / 'example-checks.json').write_text(json.dumps({
    'python': sys.version.split()[0], 'checks': records, 'passed': len(records),
    'artifact_directory': str(WORK), 'scope': 'Local fictional data; no API or MCP integration executed',
}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'{len(records)} observable CLI contract checks passed; artifacts: {WORK}')
