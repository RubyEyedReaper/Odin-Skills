"""Put an --auto search into the run's qa.json.

Stdlib only. `i2c.sh --auto` calls it twice over: after a winner's QA stage (the report exists and gains
a "search" key), and when no candidate passed (there is no QA report, so a failing one is written whose
"search" names every candidate and the nearest miss), and when the source was refused before the search
(`"refused": "source-quality"`, whose reason becomes the failure).

    python3 -m scripts.autorecord search.json Name.qa.json

Exit codes: 0 written, 2 unreadable search report or unwritable qa.json.
"""
from __future__ import annotations

import json
import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: autorecord.py search.json Name.qa.json", file=sys.stderr)
        return 2
    search_path, qa_path = argv
    try:
        with open(search_path, encoding="utf-8") as fh:
            search = json.load(fh)
        if os.path.exists(qa_path):
            with open(qa_path, encoding="utf-8") as fh:
                report = json.load(fh)
        else:
            # A source refused before any candidate was traced names its reason; otherwise nothing passed.
            report = {"pass": False, "failures": [search.get("refused", "auto")]}
        report["search"] = search
        with open(qa_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
    except (OSError, ValueError) as exc:
        print(f"autorecord: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
