import faulthandler
import sys

if "--appimage-self-test" in sys.argv:
    faulthandler.enable(all_threads=True)
    print("[AppImage self-test] Runtime hook started", file=sys.stderr, flush=True)

from felismusic_gui.host_process import capture_host_environment

capture_host_environment()
