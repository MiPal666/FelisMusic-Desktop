"""Keep system browsers/tools outside a frozen application's library paths."""
import os
import sys

_host_environment = None


def capture_host_environment():
    """Called before PyInstaller's Qt/GI runtime hooks change the environment."""
    global _host_environment
    if not getattr(sys, "frozen", False):
        return
    env = dict(os.environ)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original is None:
        env.pop("LD_LIBRARY_PATH", None)
    else:
        env["LD_LIBRARY_PATH"] = original
    original_path = env.pop("FELISMUSIC_HOST_PATH", None)
    if original_path is not None:
        env["PATH"] = original_path
    _host_environment = env


def host_environment():
    # Return a copy: a child must not change later launches or the app itself.
    return dict(_host_environment if _host_environment is not None else os.environ)
