#!/usr/bin/env python3
"""Download Hadoop winutils.exe for local PySpark on Windows."""

from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "tools" / "hadoop" / "bin"
BASE = "https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.5/bin"
FILES = ("winutils.exe", "hadoop.dll")


def main() -> None:
    BIN.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        url = f"{BASE}/{name}"
        dest = BIN / name
        print(f"Downloading {url} -> {dest}")
        urllib.request.urlretrieve(url, dest)
    print("Done. HADOOP_HOME will default to tools/hadoop")


if __name__ == "__main__":
    main()
