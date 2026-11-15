import shutil
import subprocess
from datetime import date

import pytest

from mac import outro


def test_outros_rotate_daily_and_weekly():
    assert all((outro.OUTRO_DIR / n).exists() for n in outro.OUTROS)
    days = {outro.for_day(date(2026, 11, d)).name for d in (15, 16)}
    weeks = {outro.for_week(date(2026, 11, d)).name for d in (9, 16)}
    assert days == weeks == set(outro.OUTROS)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("w,h", [(1080, 1920), (1920, 1080)])
def test_append_adds_the_outro_at_the_frame_size(tmp_path, w, h):
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=red:s={w}x{h}:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=d=1:r=44100", "-shortest", "-c:v", "libx264", "-c:a", "aac", "-ac", "2", str(v)], check=True)
    clip = outro.pick(0)
    outro.append(v, clip, w, h, 30)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(v)], capture_output=True, text=True, check=True).stdout.strip()
    assert probe == f"{w},{h}"
    assert abs(outro.seconds(v) - (1 + outro.seconds(clip))) < 0.3
