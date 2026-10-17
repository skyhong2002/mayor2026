"""Forward the pipeline's advisory lock through cooperating subprocesses."""

from __future__ import annotations

import os
import subprocess

LOCK_FDS_ENV = "MAYOR_PIPELINE_LOCK_FDS"


def run(command, *, pass_fds=(), env=None, **kwargs):
    # Every Python launch site in the pipeline uses this helper. The descriptor
    # and its environment marker travel together, including into grandchildren.
    inherited = tuple(int(value) for value in os.environ.get(LOCK_FDS_ENV, "").split(",") if value)
    descriptors = tuple(sorted(set((*inherited, *pass_fds))))
    for descriptor in descriptors:
        os.fstat(descriptor)  # Fail closed if an advertised lock was lost.
    child_env = dict(os.environ if env is None else env)
    if descriptors:
        child_env[LOCK_FDS_ENV] = ",".join(map(str, descriptors))
    else:
        child_env.pop(LOCK_FDS_ENV, None)
    return subprocess.run(command, pass_fds=descriptors, env=child_env, **kwargs)
