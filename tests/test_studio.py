import numpy as np
from PIL import Image

from mac import studio
from mac.anchors import portrait


def test_desk_shot_puts_the_anchor_behind_the_desk():
    key = "kent-state"
    pic = portrait(key)
    assert pic, "kent-state portrait is committed"
    empty = np.asarray(studio.desk_shot(None, 540, 400, x=0.3).convert("RGB")).astype(int)
    shot = np.asarray(studio.desk_shot(pic, 540, 400, x=0.3).convert("RGB")).astype(int)
    assert shot.shape == (400, 540, 3)
    # Above the desk, where the anchor sits, the picture changed; below the desk's front edge it did not.
    assert np.abs(shot[60:200, 120:200] - empty[60:200, 120:200]).mean() > 20
    assert np.abs(shot[340:, :] - empty[340:, :]).max() <= 2


def test_desk_shot_fades_into_the_card():
    im = studio.desk_shot(None, 300, 400, fade_top=100, fade_left=80)
    a = np.asarray(im.getchannel("A"))
    assert a[0, 200] == 0 and a[399, 0] == 0 and a[399, 299] == 255


def test_cached_reuses_the_file(tmp_path):
    calls = []

    def make(n):
        calls.append(n)
        return Image.new("RGB", (4, 4))
    a = studio.cached(tmp_path, "x", make, n=1)
    b = studio.cached(tmp_path, "x", make, n=1)
    assert a == b and calls == [1]
