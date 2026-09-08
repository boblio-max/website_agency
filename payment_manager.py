"""
payment_manager.py (Bot 11) — TODO stub.

Planned responsibility: collect payment / record transactions once a client
accepts the preview site. Not implemented yet.

The stub exposes the same orchestrator-friendly convention as the other bots
so ``import payment_manager; payment_manager.main(...)`` fails loudly instead
of with an ImportError/AttributeError:

    payment_manager.main(argv=None, **kwargs) -> str | int

Currently always returns exit code 2 with a "not implemented" error.
"""

from __future__ import annotations

import argparse
import sys


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Bot 11 (stub): payments — not implemented yet.")
    return p.parse_args(argv)


def main(argv=None, **kwargs) -> str | int:
    """Stub entry point. Returns int exit code 2 (not implemented).

    Accepts ``argv``/``kwargs`` (unknown options raise TypeError, matching the
    convention of the implemented bots). A bare main() call uses defaults;
    sys.argv is only used via the CLI.
    """
    if argv is None:
        argv = []
    args = parse_args(argv)
    for _k in kwargs:
        if not hasattr(args, _k):
            raise TypeError(f"payment_manager.main() got an unexpected option {_k!r}")
    print("[payment_manager] ERROR: not implemented yet (Bot 11 stub)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    _rc = main(sys.argv[1:])
    raise SystemExit(_rc if isinstance(_rc, int) else 0)
