#!/usr/bin/env python3
import argparse
from pathlib import Path
from site_config import ROOT, render, settings

parser = argparse.ArgumentParser(description='Render validated site configuration without printing values.')
parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
parser.add_argument('--output', type=Path, default=ROOT / 'deployment/generated')
args = parser.parse_args()
try:
    count = render(settings(args.env_file), args.output)
except (ValueError, OSError) as error:
    raise SystemExit(str(error)) from None
print(f'PASS: rendered {count} configuration files (values omitted)')
