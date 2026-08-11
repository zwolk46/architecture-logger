"""Stub commit hook.

Reads and discards the PostToolUse payload on stdin, then exits 0. A non-zero
exit would surface a hook-error notice to the user on every Bash call.
"""

import sys


def main() -> int:
    sys.stdin.read()
    return 0


if __name__ == "__main__":
    sys.exit(main())
