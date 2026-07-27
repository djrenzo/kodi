import re

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

def convert_srt_fps(input_path, output_path, old_fps, new_fps):
    """
    Rescale every timestamp in an SRT file from old_fps to new_fps.
    ratio = old_fps / new_fps
    """
    ratio = old_fps / new_fps

    timestamp_pattern = re.compile(
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})'
    )

    def replace_timestamps(match):
        start_ms = srt_time_to_ms(match.group(1)) * ratio
        end_ms = srt_time_to_ms(match.group(2)) * ratio
        return f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}"

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    converted = timestamp_pattern.sub(replace_timestamps, content)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(converted)


# Example usage in your addon:
# convert_srt_fps('/path/to/original.srt', '/path/to/synced.srt',
#                  old_fps=23.976, new_fps=25)