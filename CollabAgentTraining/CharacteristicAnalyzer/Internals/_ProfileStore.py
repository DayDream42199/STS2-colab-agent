import json
import os
import tempfile

from ._Validation import checkProfile

PROFILE_KEYS = ("A", "S", "T", "d_A", "d_S", "d_T", "c_A", "c_S", "c_T")

_profileDir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Profiles")
_connections = {}


def zeroProfile():
    return {k: 0 for k in PROFILE_KEYS}


def setDir(directory):
    global _profileDir
    _profileDir = os.path.abspath(directory)
    _connections.clear()
    return _profileDir


def create(index, filename, overwrite=False):
    path = _pathFor(filename)
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(
            f"{path} already exists - use connectProfile({index!r}, {filename!r}) "
            f"to reuse it, or newProfile(..., overwrite=True) to reset it")
    write(path, zeroProfile())
    _connections[index] = path
    return path


def connect(index, filename):
    path = _pathFor(filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"{path} does not exist - create it first with newProfile({index!r}, {filename!r})")
    read(path)
    _connections[index] = path
    return path


def connected(index):
    try:
        return _connections[index]
    except KeyError:
        raise KeyError(
            f"index {index!r} has no profile attached - call newProfile({index!r}, name) "
            f"or connectProfile({index!r}, name) first") from None


def read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return checkProfile(json.load(fh), PROFILE_KEYS)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"profile file {path} is invalid: {exc}") from exc


def write(path, profile):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _pathFor(filename):
    name = str(filename)
    if name.lower().endswith(".json"):
        name = name[:-5]
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError(f"filename must be a plain name (no folders), got {filename!r}")
    return os.path.join(_profileDir, name + ".json")
