"""A local, read-only ticket CLI. All bundled records are fictional."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

VERSION = '1.0.0'
DEFAULT_DATA = Path(__file__).resolve().parent / 'tickets.json'
STATUSES = ('blocked', 'in-progress', 'done')


class AppError(Exception):
    def __init__(self, code, message, exit_code=2):
        self.code, self.message, self.exit_code = code, message, exit_code


def nonnegative(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('must be an integer')
    if number < 0:
        raise argparse.ArgumentTypeError('must be zero or greater')
    return number


def parser():
    root = argparse.ArgumentParser(
        description='Inspect fictional local tickets; never changes a business system.',
        epilog='Examples: list --status blocked --min-days 3 --format json; show DEMO-101',
    )
    root.add_argument('--version', action='version', version=f'triage {VERSION}')
    commands = root.add_subparsers(dest='command', required=True)
    for name, help_text in (
        ('list', 'Filter and list tickets'),
        ('show', 'Show one ticket and its suggested next step'),
        ('summary', 'Summarize the selected tickets'),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument('--data', type=Path, default=DEFAULT_DATA, help='UTF-8 JSON dataset')
        command.add_argument('--format', choices=('table', 'json'), default='table')
        command.add_argument('--output', type=Path, help='Create a new JSON export file; refuses overwrite')
        if name == 'show':
            command.add_argument('id', help='Ticket ID, such as DEMO-101')
        else:
            command.add_argument('--status', choices=STATUSES)
            command.add_argument('--owner', help='Exact owner name')
            command.add_argument('--min-days', type=nonnegative, default=0)
    return root


def load_data(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, ValueError) as error:
        raise AppError('DATA_READ_FAILED', f'Cannot read dataset: {error}')
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise AppError('INVALID_DATA', 'Expected dataset schema_version 1')
    if not isinstance(data.get('as_of'), str) or not isinstance(data.get('tickets'), list):
        raise AppError('INVALID_DATA', 'Dataset needs as_of and tickets')
    seen = set()
    text_fields = ('id', 'title', 'owner', 'status', 'reason', 'next_step')
    for item in data['tickets']:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(key), str) or not item[key].strip() for key in text_fields
        ):
            raise AppError('INVALID_DATA', 'Each ticket needs nonempty text fields')
        if item['id'] in seen or item['status'] not in STATUSES:
            raise AppError('INVALID_DATA', 'Duplicate ticket ID or unsupported status')
        if type(item.get('waiting_days')) is not int or item['waiting_days'] < 0:
            raise AppError('INVALID_DATA', 'waiting_days must be a nonnegative integer')
        if item['status'] != 'blocked' and item['waiting_days'] != 0:
            raise AppError('INVALID_DATA', 'Nonblocked tickets must have waiting_days 0')
        seen.add(item['id'])
    return data


def select(data, args):
    result = data['tickets']
    if args.status:
        result = [item for item in result if item['status'] == args.status]
    if args.owner:
        result = [item for item in result if item['owner'] == args.owner]
    result = [item for item in result if item['waiting_days'] >= args.min_days]
    return sorted(result, key=lambda item: (-item['waiting_days'], item['id']))


def run(args):
    data = load_data(args.data)
    payload = {'schema_version': 1, 'as_of': data['as_of'], 'command': args.command}
    if args.command == 'show':
        ticket = next((item for item in data['tickets'] if item['id'] == args.id), None)
        if ticket is None:
            raise AppError('NOT_FOUND', f'Ticket not found: {args.id}', 3)
        payload['ticket'] = ticket
    else:
        selected = select(data, args)
        payload['count'] = len(selected)
        if args.command == 'list':
            payload['tickets'] = selected
        else:
            payload['by_status'] = dict(sorted(Counter(item['status'] for item in selected).items()))
            payload['blocked_by_owner'] = dict(sorted(Counter(
                item['owner'] for item in selected if item['status'] == 'blocked'
            ).items()))
            blocked = [item for item in selected if item['status'] == 'blocked']
            payload['longest_waiting_days'] = max((item['waiting_days'] for item in blocked), default=0)
    return payload


def human_text(payload):
    lines = [f"Local demo dataset | as of {payload['as_of']}"]
    if payload['command'] == 'show':
        item = payload['ticket']
        lines.extend(f'{key}: {value}' for key, value in item.items())
    elif payload['command'] == 'list':
        lines.append('ID | OWNER | STATUS | DAYS | TITLE')
        lines.extend(
            f"{item['id']} | {item['owner']} | {item['status']} | {item['waiting_days']} | {item['title']}"
            for item in payload['tickets']
        )
        lines.append(f"count: {payload['count']}")
    else:
        lines.extend((f"count: {payload['count']}",
                      f"by_status: {json.dumps(payload['by_status'], ensure_ascii=False)}",
                      f"blocked_by_owner: {json.dumps(payload['blocked_by_owner'], ensure_ascii=False)}",
                      f"longest_waiting_days: {payload['longest_waiting_days']}"))
    return '\n'.join(lines)


def main(argv=None):
    # Stable encoding for redirected output and subprocess callers on Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parser().parse_args(argv)
    try:
        if args.output and args.format != 'json':
            raise AppError('INVALID_OUTPUT', '--output requires --format json')
        payload = run(args)
        text = json.dumps(payload, ensure_ascii=False, indent=2) if args.format == 'json' else human_text(payload)
        if args.output:
            try:
                with args.output.open('x', encoding='utf-8', newline='\n') as file:
                    file.write(text + '\n')
            except OSError as error:
                raise AppError('OUTPUT_FAILED', f'Cannot create output file: {error}', 4)
            print(f'Export created: {args.output}', file=sys.stderr)
        else:
            print(text)
        return 0
    except AppError as error:
        # Application errors are JSON; argparse usage errors keep its standard format.
        print(json.dumps({'error': {'code': error.code, 'message': error.message}}, ensure_ascii=False), file=sys.stderr)
        return error.exit_code


if __name__ == '__main__':
    raise SystemExit(main())
