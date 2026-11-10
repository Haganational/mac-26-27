"""Transcribe a conversation and split it by speaker (runs in Actions; Hugging Face is reachable there).

    python tools/diarize.py in.mp3 out.json [--ref matthew.wav] [--speakers 2]

faster-whisper gives timed segments; Resemblyzer voice embeddings, clustered, say who spoke.
With --ref, each cluster gets its similarity to that voice, so Matthew's cluster is obvious.
"""
import argparse, json
import numpy as np
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
from sklearn.cluster import AgglomerativeClustering
import librosa

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--ref"); ap.add_argument("--speakers", type=int, default=2)
a = ap.parse_args()
model = WhisperModel("small.en", device="cpu", compute_type="int8")
wav, sr = librosa.load(a.src, sr=16000, mono=True)
segs, _ = model.transcribe(wav, vad_filter=True, word_timestamps=False)
segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
enc = VoiceEncoder("cpu")
embs, keep = [], []
for i, s in enumerate(segs):
    piece = wav[int(s["start"] * sr):int(s["end"] * sr)]
    if len(piece) < sr * 0.8:
        continue
    embs.append(enc.embed_utterance(preprocess_wav(piece, source_sr=sr))); keep.append(i)
E_ = np.array(embs)
labels = AgglomerativeClustering(n_clusters=a.speakers, metric="cosine", linkage="average").fit_predict(E_)
ref = enc.embed_utterance(preprocess_wav(a.ref)) if a.ref else None
for i, lab, e in zip(keep, labels, E_):
    segs[i]["spk"] = int(lab)
    if ref is not None:
        segs[i]["sim_ref"] = round(float(np.dot(e, ref)), 3)
summary = {}
for lab in set(labels):
    idx = [k for k, l in zip(range(len(labels)), labels) if l == lab]
    summary[int(lab)] = {"segments": len(idx), "seconds": round(sum(segs[keep[k]]["end"] - segs[keep[k]]["start"] for k in idx), 1),
                         "sim_ref": round(float(np.mean([np.dot(E_[k], ref) for k in idx])), 3) if ref is not None else None}
json.dump({"speakers": summary, "segments": segs}, open(a.out, "w"), indent=1)
print(summary)
