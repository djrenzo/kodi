"""SRT timing fixes: FPS conversion and a constant time shift.

The adjustments made for a subtitle are stored with it in overrides.json ('subs' entry:
fps_from, fps_to, shift_ms) so the library export can apply them again to a freshly
downloaded file. FPS conversion runs before the shift, as in the Add subtitles dialog.
"""

import re

import xbmcvfs

ADJUSTMENT_KEYS = ('fps_from', 'fps_to', 'shift_ms')

_TIMESTAMPS = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})')


def srt_time_to_ms(timestr):
    """Convert 'HH:MM:SS,mmm' to milliseconds."""
    h, m, s_ms = timestr.split(':')
    s, ms = s_ms.split(',')
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def ms_to_srt_time(ms):
    """Convert milliseconds back to 'HH:MM:SS,mmm'."""
    ms = max(0, round(ms))  # clamp negative drift at start
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _retime(content, change):
    def replace(match):
        start = change(srt_time_to_ms(match.group(1)))
        end = change(srt_time_to_ms(match.group(2)))
        return f"{ms_to_srt_time(start)} --> {ms_to_srt_time(end)}"
    return _TIMESTAMPS.sub(replace, content.lstrip('﻿'))


def convert_fps_text(content, old_fps, new_fps):
    """Rescale every timestamp from old_fps to new_fps (ratio old/new)."""
    ratio = float(old_fps) / float(new_fps)
    return _retime(content, lambda ms: ms * ratio)


def shift_text(content, offset_ms):
    """Constant shift: positive = delay subtitles (later), negative = earlier."""
    return _retime(content, lambda ms: ms + int(offset_ms))


def adjustments_of(sub):
    """The stored adjustments of a 'subs' entry: {'fps_from', 'fps_to', 'shift_ms'} (only set ones)."""
    adjust = {}
    if sub.get('fps_from') and sub.get('fps_to'):
        adjust['fps_from'] = float(sub['fps_from'])
        adjust['fps_to'] = float(sub['fps_to'])
    if sub.get('shift_ms'):
        adjust['shift_ms'] = int(sub['shift_ms'])
    return adjust


def apply_adjustments_text(content, adjust):
    if adjust.get('fps_from') and adjust.get('fps_to'):
        content = convert_fps_text(content, adjust['fps_from'], adjust['fps_to'])
    if adjust.get('shift_ms'):
        content = shift_text(content, adjust['shift_ms'])
    return content


def _read(path):
    with xbmcvfs.File(path, 'r') as fh:
        return fh.read()


def _write(path, content):
    with xbmcvfs.File(path, 'w') as fh:
        if content and not fh.write(content):
            raise IOError('could not write {}'.format(path))


def apply_adjustments(path, adjust):
    """Apply stored adjustments to a subtitle file in place (works on smb:// etc. too).
    Returns True if the file was changed."""
    if not adjust:
        return False
    _write(path, apply_adjustments_text(_read(path), adjust))
    return True
