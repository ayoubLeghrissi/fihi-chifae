"""Container entrypoint.

Platform volumes (Railway, Fly, Render) are mounted owned by root. When the
container starts as root, give the data directory to the unprivileged
``appuser`` and drop privileges before starting the server, so the app never
runs as root and the volume is always writable.
"""

import os
import pwd
import sys

DATA_DIR = os.environ.get("FIHI_DATA_DIR", "/data")


def _drop_privileges():
    if os.geteuid() != 0:
        return
    user = pwd.getpwnam("appuser")
    os.makedirs(DATA_DIR, exist_ok=True)
    for root, dirs, files in os.walk(DATA_DIR):
        for name in [root] + [os.path.join(root, f) for f in dirs + files]:
            try:
                os.lchown(name, user.pw_uid, user.pw_gid)
            except OSError:
                pass
    os.setgroups([])
    os.setgid(user.pw_gid)
    os.setuid(user.pw_uid)
    os.environ["HOME"] = user.pw_dir


if __name__ == "__main__":
    _drop_privileges()
    port = os.environ.get("PORT", "8000")
    os.execv(  # noqa: S606 - fixed argv, no shell
        sys.executable,
        [sys.executable, "server.py", "--host", "0.0.0.0", "--port", port],  # noqa: S104
    )
