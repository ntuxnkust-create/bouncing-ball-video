"""Behavioral checks for effects-only sound and unchanged original physics."""
from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

from config import Config, SoundConfig
from bouncing_ball.audio import SoundBank, procedural, schedule, synthesize
from bouncing_ball.simulation import Event, Simulation


def read_pcm(path):
    with wave.open(str(path), "rb") as stream:
        return np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").reshape(-1, 2)


class SoundSystemTests(unittest.TestCase):
    def test_no_events_is_digital_silence_and_music_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/"silence.wav"
            stats = synthesize(Config(duration=2), [], target)
            self.assertFalse(read_pcm(target).any())
            self.assertEqual(stats["rms"], 0)
            self.assertFalse(stats["music"])
            self.assertFalse(stats["speech"])
            for cfg in (Config(score=True), Config(music=target)):
                with self.assertRaises(ValueError):
                    cfg.validate()

    def test_glass_and_pop_have_distinct_soft_spectra(self):
        rate = 48000
        peaks = []
        for kind in ("wall", "ball"):
            signal = procedural(kind, 1, rate)
            spectrum = np.abs(np.fft.rfft(signal))
            frequencies = np.fft.rfftfreq(len(signal), 1/rate)
            peaks.append(frequencies[np.argmax(spectrum)])
            self.assertLess(np.sum(spectrum[frequencies > 5000]**2)/np.sum(spectrum**2), .01)
            self.assertEqual(signal[0], 0)
            self.assertEqual(signal[-1], 0)
        self.assertGreater(peaks[0], 700)
        self.assertLess(peaks[1], 400)

    def test_louder_impact_is_louder_and_stereo_pan_is_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            peaks = []
            for strength in (.05, 1):
                target = Path(tmp)/f"{strength}.wav"
                synthesize(Config(duration=1), [Event(.15, "wall", 1000, 1000, 1, strength)], target)
                data = read_pcm(target).astype(float)
                peaks.append(np.max(np.abs(data)))
                self.assertGreater(np.sum(data[:, 1]**2), np.sum(data[:, 0]**2))
            self.assertGreater(peaks[1], peaks[0]*1.6)

    def test_pair_and_global_cooldowns_never_delay_sounds(self):
        cfg = Config(duration=1)
        events = [Event(.1+i*.002, "ball", 540, 1000, 0, 1, (1, 2)) for i in range(200)]
        voices, stats = schedule(cfg, events, SoundBank(cfg))
        self.assertLess(len(voices), 5)
        self.assertGreater(stats["suppressed"].get("pair_cooldown", 0), 100)
        allowed = {round(e.time*cfg.audio_rate) for e in events}
        self.assertTrue(all(v.start in allowed for v in voices))
        events = [Event(.1+i*.002, "wall", 540, 1000, 0, 1, (i,)) for i in range(200)]
        _, stats = schedule(cfg, events, SoundBank(cfg))
        self.assertGreater(stats["suppressed"].get("global_cooldown", 0), 100)

    def test_sample_accurate_onset_and_presentation_offset(self):
        cfg = Config(duration=1)
        event = Event(.12345, "wall", 540, 1000, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"onset.wav"
            synthesize(cfg, [event], path)
            data = read_pcm(path)
            expected = round(event.time*cfg.audio_rate)
            first = np.flatnonzero(np.any(data != 0, axis=1))[0]
            self.assertTrue(expected <= first <= expected+3)
            voices, _ = schedule(cfg, [event], SoundBank(cfg), 1/cfg.fps)
            self.assertEqual(voices[0].start, round((event.time-1/cfg.fps)*cfg.audio_rate))

    def test_upgrade_priority_polyphony_and_no_clipping(self):
        cfg = Config(duration=2, sound=SoundConfig(max_voices=3, global_cooldown=0))
        events = [Event(.1+i*.025, "wall", 540, 1000, 2, 1, (i,)) for i in range(12)]
        events += [Event(.4, "wall", 540, 1000, 2), Event(.4, "merge", 540, 1000, 4),
                   Event(.5, "final", 540, 1000, 7)]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/"busy.wav"
            stats = synthesize(cfg, events, target)
            data = read_pcm(target)
            self.assertLessEqual(stats["max_scheduled_voices"], 3)
            self.assertEqual(stats["event_counts"]["merge"], 1)
            self.assertEqual(stats["event_counts"]["final"], 1)
            self.assertGreater(stats["suppressed"].get("upgrade_contact", 0), 0)
            self.assertGreater(stats["suppressed"].get("polyphony", 0), 0)
            self.assertLessEqual(np.max(np.abs(data.astype(int))), round(cfg.sound.ceiling*32767))

    def test_chunk_size_does_not_change_waveform(self):
        cfg = Config(duration=3)
        events = [Event(.99, "final", 720, 1000, 7), Event(1.18, "wall", 100, 900, 0)]
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"a.wav", Path(tmp)/"b.wav"
            synthesize(cfg, events, a)
            synthesize(replace(cfg, sound=replace(cfg.sound, block_frames=4096)), events, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_custom_wav_replacement_and_resampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rate = 22050
            t = np.arange(rate//5)/rate
            with wave.open(str(root/"wall.wav"), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(rate)
                stream.writeframes((np.sin(math.tau*440*t)*15000).astype("<i2").tobytes())
            cfg = Config(duration=1, sound=SoundConfig(assets_dir=root))
            bank = SoundBank(cfg)
            self.assertEqual(set(bank.custom), {"wall"})
            signal = bank.get("wall", 0)
            self.assertEqual(len(signal), 9600)
            frequencies = np.fft.rfftfreq(len(signal), 1/cfg.audio_rate)
            self.assertAlmostEqual(frequencies[np.argmax(abs(np.fft.rfft(signal)))], 440, delta=5)

    def test_invalid_events_and_sound_settings_fail(self):
        for sound in (SoundConfig(ceiling=1), SoundConfig(pair_cooldown=-1),
                      SoundConfig(max_voices=0), SoundConfig(block_frames=0)):
            with self.subTest(sound=sound), self.assertRaises(ValueError):
                Config(sound=sound).validate()
        for event in (Event(.2, "speech", 1, 1, 0), Event(float("nan"), "wall", 1, 1, 0),
                      Event(.2, "wall", 1, 1, 0, 2)):
            with self.subTest(event=event), self.assertRaises(ValueError):
                schedule(Config(), [event], SoundBank(Config()))


class PhysicsAudioIntegrationTests(unittest.TestCase):
    def test_wall_and_ball_events_come_from_real_contacts(self):
        wall = Simulation(Config())
        wall.next_spawn = math.inf
        wall.add_ball(0, (960, 1110), (400, 0))
        for _ in range(6):
            wall.step_frame()
        contacts = [e for e in wall.events if e.kind == "wall"]
        self.assertTrue(contacts)
        self.assertGreater(contacts[0].x, 990)
        self.assertGreater(contacts[0].impact, 0)
        self.assertEqual(contacts[0].pair, (1,))
        ball = Simulation(Config(merge_equal_levels=False))
        ball.next_spawn = math.inf
        ball.add_ball(0, (500, 1100), (200, 0))
        ball.add_ball(0, (565, 1100), (-200, 0))
        for _ in range(6):
            ball.step_frame()
        contacts = [e for e in ball.events if e.kind == "ball"]
        self.assertTrue(contacts)
        self.assertEqual(contacts[0].pair, (1, 2))
        self.assertAlmostEqual(contacts[0].time*120, round(contacts[0].time*120), places=6)

    def test_all_original_trajectory_checkpoints_and_merge_results_unchanged(self):
        fixture = json.loads((Path(__file__).parent/"fixtures/physics-8d0f406.json").read_text())
        sim = Simulation(Config())
        for frame in range(1800):
            sim.step_frame()
            if str(frame) not in fixture:
                continue
            expected = fixture[str(frame)]
            self.assertEqual((sim.spawned, sim.merges, sim.highest),
                             (expected["spawned"], expected["merges"], expected["highest"]))
            balls = sorted(sim.balls.values(), key=lambda b: b.id)
            self.assertEqual(len(balls), len(expected["balls"]))
            for b, old in zip(balls, expected["balls"]):
                self.assertEqual((b.id, b.level), tuple(old[:2]))
                for actual, target in zip((*b.body.position, b.body.angle), old[2:]):
                    self.assertAlmostEqual(actual, target, places=6)


if __name__ == "__main__":
    unittest.main()
