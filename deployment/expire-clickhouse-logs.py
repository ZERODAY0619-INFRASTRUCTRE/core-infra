"""Remove closed, numbered ClickHouse gzip archives older than 30 days."""
import os
from pathlib import Path
import re
import stat
import subprocess
import time


def expire():
    cutoff = time.time() - 30 * 86400
    candidates = []
    for instance in ('icpm', 'pcpm'):
        volume = f'cpm_{instance}-clickhouse-logs'
        directory = Path(subprocess.check_output(
            ['docker', 'volume', 'inspect', '--format', '{{.Mountpoint}}', volume],
            text=True).strip())
        for path in directory.iterdir():
            if re.fullmatch(r'clickhouse-server(?:\.err)?\.log\.\d+\.gz', path.name):
                info = path.lstat()
                if stat.S_ISREG(info.st_mode) and info.st_mtime < cutoff:
                    candidates.append((path, info))
    if not candidates:
        return
    opened = set()
    for fd in Path('/proc').glob('[0-9]*/fd/*'):
        try:
            info = fd.stat()
        except FileNotFoundError:
            continue
        opened.add((info.st_dev, info.st_ino))
    for path, original in candidates:
        try:
            current = path.lstat()
        except FileNotFoundError:
            continue
        if (os.path.samestat(original, current) and current.st_mtime < cutoff
                and (current.st_dev, current.st_ino) not in opened):
            path.unlink()
            print(f'Removed {path.parent.parent.name}/{path.name}', flush=True)


if __name__ == '__main__':
    expire()
