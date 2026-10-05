# -*- coding: utf-8 -*-
"""从 GitHub 读取文件内容（走 api.github.com，适合 raw 被墙的情况）。

用法：python tools/gh_get.py <owner/repo> <路径1> [路径2 ...]
"""
from __future__ import annotations

import sys
import urllib.request


def get(repo: str, path: str) -> str:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "opencode", "Accept": "application/vnd.github.raw"},
    )
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        return
    repo = sys.argv[1]
    for path in sys.argv[2:]:
        print("=" * 78)
        print(f"FILE: {path}")
        print("=" * 78)
        try:
            print(get(repo, path))
        except Exception as exc:  # noqa: BLE001
            print(f"[失败] {exc}")


if __name__ == "__main__":
    main()
