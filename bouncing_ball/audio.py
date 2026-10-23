"""Sample-synchronized effects only: glass, pop/boing, upgrade and success.

No oscillator runs without an event. No music, speech or downloaded samples.
Mixing is deterministic and bounded by block/voice limits.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import wave

import numpy as np

from config import Config


KINDS = {"wall", "ball", "merge", "final"}
PRIORITY = {"wall": 0, "ball": 0, "merge": 1, "final": 2}


@dataclass
class Voice:
    start: int
    samples: np.ndarray
    kind: str
    gain: float
    left: float
    right: float

    @property
    def end(self):
        return self.start + len(self.samples)


def _bell(t, frequency, decay=10):
    positive = np.maximum(t, 0)
    envelope = (-np.expm1(-positive*650))*np.exp(-positive*decay)
    # Warm fundamental and quiet upper partials, with no harsh noise spike.
    value = (np.sin(math.tau*frequency*positive)
             + .12*np.sin(math.tau*frequency*2.01*positive)
             + .025*np.sin(math.tau*frequency*2.76*positive))
    return value*envelope*(t >= 0)


def _pop(t, strength=1.0):
    frequency = 240+100*strength
    # Integrated exponential pitch sweep: a soft pitched pop / short boing.
    phase = math.tau*(125*t+(frequency-125)*(-np.expm1(-t*21))/21)
    envelope = (-np.expm1(-t*950))*np.exp(-t*27)
    return np.sin(phase)*envelope


def procedural(kind, level, rate):
    """Replace this sound bank or supply WAVs; event scheduling is independent."""
    length = {"wall": .23, "ball": .19, "merge": .48+min(level, 12)*.025, "final": 1.55}[kind]
    t = np.arange(round(length*rate))/rate
    if kind == "wall":
        samples = _bell(t, 870+min(level, 8)*24, 18)
        samples += _bell(t-.004, 1330, 26)*.13
    elif kind == "ball":
        samples = _pop(t, .45+min(level, 8)*.055)
        samples += _bell(t, 210, 24)*.12
    elif kind == "merge":
        frequency = 520*2**(min(level, 12)/16)
        samples = _pop(t)*.65 + _bell(t-.022, frequency, 8)*.62
        samples += _bell(t-.065, frequency*1.5, 9)*.28
        if level >= 4:
            samples += _bell(t-.12, frequency*2, 10)*.19
        if level >= 6:
            samples += _bell(t-.18, frequency*2.5, 11)*.14
    else:
        samples = _pop(t)*.28
        for i, interval in enumerate((1, 1.25, 1.5, 2, 2.5, 3)):
            samples += _bell(t-i*.075, 523.2511*interval, 4.7)*.35
        samples += _bell(t-.45, 1046.5022, 4)*.27
    # Short tail fade prevents truncation clicks.
    fade = np.minimum(1, (len(t)-1-np.arange(len(t)))/(rate*.025))
    return (samples*np.maximum(0, fade)).astype(np.float64)


class SoundBank:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cache = {}
        self.custom = {}
        for kind in sorted(KINDS):
            path = cfg.sound.assets_dir/getattr(cfg.sound, f"{kind}_file")
            if path.is_file():
                self.custom[kind] = self._load(path)

    def _load(self, path):
        try:
            with wave.open(str(path), "rb") as stream:
                channels = stream.getnchannels()
                rate = stream.getframerate()
                if stream.getsampwidth() != 2 or channels not in (1, 2):
                    raise ValueError(f"Sound replacement must be 16-bit mono/stereo PCM WAV: {path}")
                length = stream.getnframes()
                if not 0 < length <= rate*3:
                    raise ValueError(f"Sound replacement must be >0 and ≤3 seconds: {path}")
                data = np.frombuffer(stream.readframes(length), dtype="<i2")
                data = data.reshape(-1, channels).astype(float).mean(axis=1)/32768
        except (wave.Error, EOFError) as exc:
            raise ValueError(f"Invalid PCM WAV sound replacement: {path}") from exc
        if rate != self.cfg.audio_rate:
            count = max(1, round(len(data)*self.cfg.audio_rate/rate))
            data = np.interp(np.arange(count)*rate/self.cfg.audio_rate, np.arange(len(data)), data)
        peak = float(np.max(np.abs(data)))
        if peak > 0:
            data *= .85/peak
        fade = np.minimum(np.arange(len(data)), len(data)-1-np.arange(len(data)))
        return data*np.clip(fade/(self.cfg.audio_rate*.003), 0, 1)

    def get(self, kind, level):
        if kind in self.custom:
            return self.custom[kind]
        key = (kind, min(level, 12))
        if key not in self.cache:
            self.cache[key] = procedural(kind, level, self.cfg.audio_rate)
        return self.cache[key]


def schedule(cfg, events, bank, presentation_offset=0.0):
    """Suppress crowded contacts; never delay accepted sounds from their events."""
    cfg.sound.validate()
    selected = []
    suppressed = Counter()
    counts = Counter()
    # Legacy 'hit' logs remain readable but lack wall/ball contact information.
    normalized = []
    for event in events:
        kind = "ball" if event.kind == "hit" else event.kind
        if kind not in KINDS:
            raise ValueError(f"Unknown sound event: {event.kind}")
        if (not all(math.isfinite(v) for v in (event.time, event.x, event.y, event.strength))
                or event.time < 0 or event.level < 0 or not 0 <= event.strength <= 1):
            raise ValueError("Events need finite nonnegative times/levels and strength in [0,1]")
        normalized.append((event, kind))
    normalized.sort(key=lambda item: (item[0].time, -PRIORITY[item[1]], -item[0].strength))
    upgrades = sorted(e.time for e, k in normalized if k in {"merge", "final"})
    last_global = -math.inf
    last_pair = {}
    active = []
    max_active = 0
    duration = cfg.frames/cfg.fps
    for event, kind in normalized:
        when = event.time-presentation_offset
        if when >= duration:
            suppressed["outside_duration"] += 1
            continue
        start = round(when*cfg.audio_rate)
        active = [v for v in active if v.end > max(0, start)]
        collision = kind in {"wall", "ball"}
        pair = (kind, tuple(event.pair)) if event.pair else None
        if collision:
            if pair and event.time-last_pair.get(pair, -math.inf) < cfg.sound.pair_cooldown:
                suppressed["pair_cooldown"] += 1
                continue
            if event.time-last_global < cfg.sound.global_cooldown:
                suppressed["global_cooldown"] += 1
                continue
            # Upgrade effects already include a pop; don't stack contact clicks.
            idx = bisect_left(upgrades, event.time)
            nearby = upgrades[max(0, idx-1):idx+1]
            if any(abs(value-event.time) < .028 for value in nearby):
                suppressed["upgrade_contact"] += 1
                continue
            if len(active) >= cfg.sound.max_voices:
                suppressed["polyphony"] += 1
                continue
        elif len(active) >= cfg.sound.max_voices:
            # Important upgrades replace the quietest low-priority voice with
            # a 4-ms release, preventing both voice-steal clicks and overload.
            victim = min(active, key=lambda v: (PRIORITY[v.kind], v.gain))
            cut = max(0, start-victim.start)
            tail = min(round(.004*cfg.audio_rate), max(0, len(victim.samples)-cut))
            samples = victim.samples[:cut+tail].copy()
            if tail:
                samples[cut:] *= np.linspace(1, 0, tail)
            victim.samples = samples
            active.remove(victim)
        samples = bank.get(kind, event.level)
        if start < 0:
            samples = samples[-start:]
            start = 0
        if not len(samples):
            continue
        gain = getattr(cfg.sound, f"{kind}_gain")
        gain *= (.24+.76*math.sqrt(event.strength)) if collision else (1+min(event.level, 8)*.025)
        pan = np.clip((event.x/1080*2-1)*.7, -.7, .7)
        voice = Voice(start, samples, kind, gain, math.sqrt((1-pan)/2), math.sqrt((1+pan)/2))
        selected.append(voice)
        active.append(voice)
        max_active = max(max_active, len(active))
        counts[kind] += 1
        if collision:
            last_global = event.time
            if pair:
                last_pair[pair] = event.time
    return selected, {"event_counts": dict(counts), "suppressed": dict(suppressed),
                      "max_scheduled_voices": max_active, "audible_events": len(selected)}


def synthesize(cfg: Config, events, path: Path, presentation_offset=0.0):
    cfg.validate()
    bank = SoundBank(cfg)
    voices, stats = schedule(cfg, events, bank, presentation_offset)
    rate = cfg.audio_rate
    total = round(cfg.frames/cfg.fps*rate)
    peak, square, count = 0.0, 0.0, 0
    pending = 0
    active = []
    upgrades = [v for v in voices if v.kind in {"merge", "final"}]
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        for start in range(0, total, cfg.sound.block_frames):
            end = min(start+cfg.sound.block_frames, total)
            while pending < len(voices) and voices[pending].start < end:
                active.append(voices[pending])
                pending += 1
            active = [v for v in active if v.end > start]
            mix = np.zeros((end-start, 2), dtype=np.float64)
            positions = np.arange(start, end)
            duck = np.ones(end-start)
            duck_length = round(cfg.sound.upgrade_duck_seconds*rate)
            if duck_length:
                for v in upgrades:
                    if v.start <= end and v.start+duck_length >= start:
                        age = (positions-v.start)/duck_length
                        envelope = np.where((age >= 0) & (age <= 1),
                                            cfg.sound.collision_duck_gain+(1-cfg.sound.collision_duck_gain)*age, 1)
                        duck = np.minimum(duck, envelope)
            for voice in active:
                lo, hi = max(start, voice.start), min(end, voice.end)
                signal = voice.samples[lo-voice.start:hi-voice.start]*voice.gain
                if voice.kind in {"wall", "ball"}:
                    signal = signal*duck[lo-start:hi-start]
                mix[lo-start:hi-start, 0] += signal*voice.left
                mix[lo-start:hi-start, 1] += signal*voice.right
            # Smooth saturator and AAC headroom, without hard clipping.
            mix = cfg.sound.ceiling*np.tanh(mix*cfg.sound.master_gain/cfg.sound.ceiling)
            mix *= np.clip((total-1-positions)/(rate*.012), 0, 1)[:, None]
            peak = max(peak, float(np.max(np.abs(mix))))
            square += float(np.sum(mix*mix))
            count += mix.size
            out.writeframes((mix*32767).round().astype("<i2").tobytes())
    return {**stats, "sample_rate": rate, "channels": 2, "peak": peak,
            "rms": math.sqrt(square/count), "music": False, "speech": False,
            "presentation_offset_seconds": presentation_offset,
            "custom_sounds": sorted(bank.custom), "source": "event-triggered sound effects only"}
