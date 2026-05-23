"""IO handler: save the Live set and export audio.

Live's Python API does not expose ``Save Set`` or ``Export Audio/Video`` to
remote scripts, so we drive the Cocoa dialogs through ``osascript``.

Constraints:
- macOS only.
- Live must be the foreground application during the operation.
- The process running ``osascript`` (Ableton Live, in this case) needs
  Accessibility permission. macOS prompts the first time. Grant it under
  System Settings → Privacy & Security → Accessibility.
- Live remembers the most recent Export dialog settings between sessions
  (sample rate, bit depth, format, range). The export tool reuses them;
  set them once manually before the first run.

OSC addresses:

- ``/live/io/save_set_as path`` — saves the current set to ``path``.
- ``/live/io/export_audio path`` — exports current set to ``path`` using
  Live's current Export-dialog settings.

Both handlers spawn ``osascript`` via :func:`subprocess.Popen` so they return
immediately; the AppleScript runs in parallel and types into Live's UI.
The caller polls the destination path on disk to know when each operation
is finished.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Tuple

from .handler import AbletonOSCHandler

logger = logging.getLogger("abletonosc")


# AppleScript driving File > Save Live Set As… and typing the destination
# path through the standard "Go to folder" sheet (Cmd+Shift+G).
_SAVE_SET_AS_APPLESCRIPT = """\
on run argv
    set targetPath to item 1 of argv
    tell application "Live" to activate
    delay 0.3
    tell application "System Events"
        keystroke "s" using {command down, shift down}
        delay 0.7
        keystroke "g" using {command down, shift down}
        delay 0.4
        keystroke targetPath
        delay 0.2
        keystroke return
        delay 0.5
        keystroke return
    end tell
end run
"""


# AppleScript driving File > Export Audio/Video… and typing the destination
# path through the file-save sheet's "Go to folder" overlay.
#
# The first ``return`` keystroke accepts the Export dialog with current
# defaults. The second ``return`` accepts the file-save sheet after the path
# is typed. Live then renders in the background; the caller polls the file.
_EXPORT_AUDIO_APPLESCRIPT = """\
on run argv
    set targetPath to item 1 of argv
    tell application "Live" to activate
    delay 0.3
    tell application "System Events"
        keystroke "r" using {command down, shift down}
        delay 1.0
        keystroke return
        delay 1.5
        keystroke "g" using {command down, shift down}
        delay 0.4
        keystroke targetPath
        delay 0.2
        keystroke return
        delay 0.5
        keystroke return
    end tell
end run
"""


class IOHandler(AbletonOSCHandler):
    """Save/export OSC endpoints, driven through macOS GUI scripting."""

    def init_api(self) -> None:
        self.class_identifier = "io"

        def save_set_as(params: Tuple) -> Tuple:
            if not params:
                msg = "save_set_as: missing path argument"
                logger.warning(msg)
                return ("error", msg)
            path = str(params[0])
            try:
                proc = subprocess.Popen(
                    ["osascript", "-e", _SAVE_SET_AS_APPLESCRIPT, path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except OSError as exc:
                logger.error("save_set_as: spawn failed: %s", exc)
                return ("error", str(exc))
            logger.info("save_set_as: pid=%d path=%s", proc.pid, path)
            return ("ok", path)

        def export_audio(params: Tuple) -> Tuple:
            if not params:
                msg = "export_audio: missing path argument"
                logger.warning(msg)
                return ("error", msg)
            path = str(params[0])
            try:
                proc = subprocess.Popen(
                    ["osascript", "-e", _EXPORT_AUDIO_APPLESCRIPT, path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except OSError as exc:
                logger.error("export_audio: spawn failed: %s", exc)
                return ("error", str(exc))
            logger.info("export_audio: pid=%d path=%s", proc.pid, path)
            return ("ok", path)

        self.osc_server.add_handler("/live/io/save_set_as", save_set_as)
        self.osc_server.add_handler("/live/io/export_audio", export_audio)
