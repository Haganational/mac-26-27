"""Write Chatterbox jobs for every take still missing from audio/, cloned from each anchor's audition."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = json.loads((HERE / "lines.json").read_text())
jobs = []
for t in spec["takes"]:
    out = HERE / "audio" / f"{t['id']}.wav"
    if out.exists():
        continue
    key = spec["cast"][t["who"]]["key"]
    jobs.append({"text": t["text"].replace("...", "…"), "out": str(out), "ref": f"/tmp/auditions/{key}.wav"})
(HERE / "audio").mkdir(exist_ok=True)
Path("/tmp/voice-jobs.json").write_text(json.dumps(jobs))
print(f"{len(jobs)} takes to clone")
