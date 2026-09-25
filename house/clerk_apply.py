"""Apply Riemann Clerk decisions. No-op unless the App id and PEM are set.

CI variables (masked): CLERK_APP_ID, CLERK_INSTALLATION_ID, CLERK_APP_PEM.
CLERK_DRY_RUN=1 prints decisions and does not approve or deny.
Does not read the owner user token.
"""

from __future__ import annotations

import os
import sys

from rc.clerk_github import apply_pending, installation_token, live_fetch


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
    dry = os.environ.get("CLERK_DRY_RUN") == "1"
    token = installation_token(
        os.environ["CLERK_APP_ID"],
        os.environ["CLERK_INSTALLATION_ID"],
        os.environ["CLERK_APP_PEM"],
    )
    lines = apply_pending(live_fetch(token), dry_run=dry)
    print(f"clerk_ran dry_run={str(dry).lower()} count={len(lines)}")
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
