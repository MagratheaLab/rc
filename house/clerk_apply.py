"""Apply Riemann Clerk decisions. No-op unless the App id and PEM are set.

CI variables (masked): CLERK_APP_ID, CLERK_INSTALLATION_ID, CLERK_APP_PEM.
Does not read the owner user token.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    missing = [
        name
        for name in ("CLERK_APP_ID", "CLERK_INSTALLATION_ID", "CLERK_APP_PEM")
        if not os.environ.get(name)
    ]
    if missing:
        print("clerk_skip missing " + ",".join(missing))
        print("Register the Riemann Clerk GitHub App, then set the CI variables.")
        return 0
    print("clerk_ready app=riemann-clerk")
    print("apply loop is not wired until the App PEM is installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
