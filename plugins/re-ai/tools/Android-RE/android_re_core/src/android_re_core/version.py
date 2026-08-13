"""Version constants for android_re_core and the Android-RE monorepo."""

from __future__ import annotations

__all__ = [
    "ANDROID_RE_VERSION",
    "PYTHON_MIN_VERSION",
    "__version__",
]

#: android_re_core library version. Bumped per its own semver, mirrored at
#: the monorepo top-level tag in v0.1.x.
__version__ = "0.1.0"

#: Monorepo top-level version. Matches __version__ for now.
ANDROID_RE_VERSION = "0.1.0"

#: Minimum supported Python version. See pyproject.toml `requires-python`.
PYTHON_MIN_VERSION = (3, 12)
