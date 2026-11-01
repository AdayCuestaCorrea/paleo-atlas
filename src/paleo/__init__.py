"""Paleo Atlas: a living, visual paleontology encyclopedia (ES/EN)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("paleo-atlas")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"
