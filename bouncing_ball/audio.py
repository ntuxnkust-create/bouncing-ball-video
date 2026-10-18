"""Original stereo score and event-synchronized synthesis, streamed to WAV."""
from __future__ import annotations

import math
from pathlib import Path
import wave

import numpy as np

from config import Config


def _tone(t, frequency, decay):
    envelope = (1-np.exp(-np.maximum(t, 0)*500))*np.exp(-np.maximum(t, 0)*decay)
    sound = (np.sin(math.tau*frequency*t)
             + .26*np.sin(math.tau*frequency*2.002*t)
             + .08*np.sin(math.tau*frequency*3.01*t))
    return sound*envelope*(t >= 0)


def synthesize(cfg: Config, events, path: Path):
    rate = cfg.audio_rate
    total = round(cfg.frames/cfg.fps*rate)
    # Suppress contact chatter without moving sounds off their collision times.
    selected = []
    last_hit = -1.0
    for e in events:
        if e.kind == "hit":
            if e.time-last_hit < .065:
                continue
            last_hit = e.time
        selected.append(e)
    notes = [261.6256, 293.6648, 329.6276, 391.9954, 440.0, 523.2511, 659.2551, 783.9909]
    peak, square, count = 0.0, 0.0, 0
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        for start in range(0, total, rate):
            end = min(start+rate, total)
            times = np.arange(start, end)/rate
            mix = np.zeros((end-start, 2), dtype=np.float64)
            if cfg.score:
                beat = 60/106
                arp_step = beat/2
                index = np.floor(times/arp_step).astype(np.int64)
                sequence = np.array([0, 2, 4, 6, 4, 2, 1, 4, 0, 2, 5, 7, 5, 4, 2, 1])
                frequency = np.array(notes)[sequence[index % len(sequence)]]
                local = times % arp_step
                melody = _tone(local, frequency*2, 13)*.035
                bass_time = times % (beat*2)
                bass_notes = np.array([65.4064, 55.0, 43.6535, 49.0])
                bass_freq = bass_notes[(times/(beat*8)).astype(int) % 4]
                bass = _tone(bass_time, bass_freq, 3.8)*.10
                # Soft synthesized kick on each beat, no third-party samples.
                kick_time = times % beat
                kick = np.sin(math.tau*(48*kick_time+2.3*(1-np.exp(-kick_time*22))))
                kick *= np.exp(-kick_time*22)*.045
                for ch in range(2):
                    mix[:, ch] += melody*(1+(-1 if ch else 1)*.16*np.sin(times*.8))+bass+kick
            block_start, block_end = start/rate, end/rate
            for e in selected:
                length = 2.5 if e.kind == "final" else .75 if e.kind == "merge" else .24
                if e.time >= block_end or e.time+length < block_start:
                    continue
                t = times-e.time
                mask = (t >= 0) & (t < length)
                if not mask.any():
                    continue
                local = t[mask]
                frequency = notes[min(e.level, len(notes)-1)]
                if e.kind == "hit":
                    sound = _tone(local, frequency*2, 24)*(.06+.12*e.strength)
                elif e.kind == "merge":
                    sound = _tone(local, frequency, 7)*.20
                    sound += _tone(local-.045, frequency*1.5, 9)*.11
                    sound += _tone(local-.09, frequency*2, 9)*.07
                else:
                    sound = np.zeros(len(local))
                    for i, interval in enumerate((1, 1.25, 1.5, 2, 2.5, 3, 4)):
                        sound += _tone(local-i*.075, 261.6256*interval, 2.8)*.13
                    sound += _tone(local, 55, 3)*.23
                pan = max(-.75, min(.75, (e.x/1080*2-1)*.75))
                mix[mask, 0] += sound*math.sqrt((1-pan)/2)
                mix[mask, 1] += sound*math.sqrt((1+pan)/2)
            fade = np.minimum(np.clip(times/.15, 0, 1),
                              np.clip((total/rate-times)/.8, 0, 1))
            # Smooth peak protection without hard clipping.
            mix = np.tanh(mix*1.35)*.94*fade[:, None]
            peak = max(peak, float(np.max(np.abs(mix))))
            square += float(np.sum(mix*mix))
            count += mix.size
            out.writeframes((mix*32767).astype("<i2").tobytes())
    return {"sample_rate": rate, "channels": 2, "peak": peak,
            "rms": math.sqrt(square/count), "audible_events": len(selected),
            "source": "original procedural score and effects"}
