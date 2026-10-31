"""First exercise: arguments are an interface; no network or business mutation."""
import argparse
import sys

sys.stdout.reconfigure(encoding='utf-8')
parser = argparse.ArgumentParser(description='Print a greeting from a command argument')
parser.add_argument('--name', required=True, help='Name to greet')
args = parser.parse_args()
print(f'你好，{args.name}。这是你的第一个 CLI。')
