"""Voice a studio dialogue: cloned voices for Matthew and Bumrod, a plainly synthetic Piper voice for Cynthia.

    python tools/dialogue_voice.py studio/<name>.dialogue.json out_dir/

Writes out_dir/NN-<speaker>.wav per line. Expects /tmp/ref-<speaker>.wav for cloned speakers,
CLONE_PY (a Python with Chatterbox) and voices/<piper voice>.onnx for Cynthia.
"""
import json, os, subprocess, sys
from pathlib import Path

d = json.load(open(sys.argv[1]))
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
jobs = {}
for i, (spk, text) in enumerate(d["lines"]):
    wav = out / f"{i:02d}-{spk}.wav"
    if spk in ("cynthia", "craig"):  # plainly synthetic Piper voices
        voice, scale = (d["cynthia_voice"], "0.92") if spk == "cynthia" else (d["craig_voice"], "1.3")
        subprocess.run([sys.executable, "-m", "piper", "-m", f"voices/{voice}.onnx", "-f", str(wav), "--length-scale", scale],
                       input=text.encode(), check=True)
    else:
        jobs.setdefault(spk, []).append({"text": text, "out": str(wav.resolve())})
for spk, js in jobs.items():
    jf = out / f"jobs-{spk}.json"; jf.write_text(json.dumps(js))
    subprocess.run([os.environ["CLONE_PY"], "tools/clone_voice.py", "--ref", f"/tmp/ref-{spk}.wav", "--jobs", str(jf)], check=True)
    jf.unlink()
print(sorted(p.name for p in out.glob("*.wav")))
