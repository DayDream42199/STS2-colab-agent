from .Internals import _Pipeline
from .Internals import _ProfileStore
from .Internals import _Validation

__all__ = ["newProfile", "connectProfile", "updateProfile", "setProfileDir"]


def newProfile(index, filename, overwrite=False):
    return _ProfileStore.create(index, filename, overwrite)


def connectProfile(index, filename):
    return _ProfileStore.connect(index, filename)


def updateProfile(index, history):
    path = _ProfileStore.connected(index)
    _Validation.checkHistory(history)

    newProfile_ = _Pipeline.run(history, _ProfileStore.read(path))

    _Validation.checkFinite(newProfile_)
    _ProfileStore.write(path, newProfile_)
    return _Pipeline.output(newProfile_)


def setProfileDir(directory):
    return _ProfileStore.setDir(directory)
