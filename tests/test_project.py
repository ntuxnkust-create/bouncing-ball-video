import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

from config import Config
from bouncing_ball.audio import synthesize
from bouncing_ball.simulation import Event, Simulation


class PhysicsTests(unittest.TestCase):
    def scene(self):
        sim = Simulation(Config())
        sim.next_spawn = math.inf
        return sim

    def test_contact_merges_equal_levels_once_and_conserves_mass(self):
        s = self.scene()
        for x, vx in ((510, 10), (570, -10), (630, -10)):
            b = s.add_ball(0, (x, 1100), (vx, 0))
            b.born = -1
        s.step_frame()
        self.assertEqual(s.merges, 1)
        self.assertEqual(len(s.balls), 2)
        self.assertEqual(sum(b.body.mass for b in s.balls.values()), 3)
        self.assertEqual(sorted(b.level for b in s.balls.values()), [0, 1])

    def test_no_merge_for_unlike_levels_or_separated_balls(self):
        s = self.scene()
        s.add_ball(0, (510, 1100)).born = -1
        s.add_ball(1, (565, 1100)).born = -1
        s.add_ball(0, (750, 1000)).born = -1
        for _ in range(12):
            s.step_frame()
        self.assertEqual(s.merges, 0)

    def test_merge_rule_can_be_disabled(self):
        s = Simulation(Config(merge_equal_levels=False))
        s.next_spawn = math.inf
        for x in (510, 570):
            s.add_ball(0, (x, 1100)).born = -1
        for _ in range(10):
            s.step_frame()
        self.assertEqual(s.merges, 0)

    def test_full_default_story_is_repeatable_finite_and_reaches_final(self):
        outcomes = []
        for run in range(2):
            s = Simulation(Config())
            for _ in range(1800):
                s.step_frame()
                for b in s.balls.values():
                    x, y = b.body.position
                    self.assertTrue(math.isfinite(x+y+b.body.angle))
                    self.assertTrue(-20 < x < 1100 and 200 < y < 1650, (x, y))
            self.assertEqual(s.highest, 7)
            self.assertTrue(45 < s.first_final < 57)
            self.assertEqual(sum(b.level == 7 for b in s.balls.values()), 1)
            self.assertGreater(s.merges, 45)
            self.assertEqual(s.spawned-s.merges, len(s.balls))
            outcomes.append(s.report())
        self.assertEqual(outcomes[0], outcomes[1])


class AudioTests(unittest.TestCase):
    def test_stereo_event_crosses_block_boundary_without_clipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"sound.wav"
            cfg = Config(duration=3, score=False)
            stats = synthesize(cfg, [Event(.99, "final", 900, 1000, 7)], path)
            with wave.open(str(path)) as stream:
                self.assertEqual(stream.getnframes(), 3*48000)
                data = np.frombuffer(stream.readframes(3*48000), dtype="<i2").reshape(-1, 2)
            self.assertEqual(int(np.max(np.abs(data[:47000]))), 0)
            self.assertGreater(np.max(np.abs(data[48000:60000])), 1000)
            self.assertGreater(np.sum(data[:, 1].astype(float)**2), np.sum(data[:, 0].astype(float)**2))
            self.assertTrue(.01 < stats["peak"] < .98)


class PipelineTests(unittest.TestCase):
    def test_custom_transparent_png_is_used(self):
        import pygame as pg
        from bouncing_ball.graphics import Renderer
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            logo = pg.Surface((100, 100), pg.SRCALPHA)
            logo.fill((255, 0, 150, 255))
            pg.image.save(logo, path/"renault.png")
            renderer = Renderer(Config(logos_dir=path))
            sprite = renderer.sprites[0]
            color = sprite.get_at((sprite.get_width()//2, sprite.get_height()//2))
            # Resampling may round channels slightly; identify the replacement's
            # magenta center rather than the yellow procedural Renault emblem.
            self.assertGreater(color.r, 230)
            self.assertLess(color.g, 10)
            self.assertGreater(color.b, 130)

    def test_real_streaming_h264_aac_pipeline_and_existing_output_protection(self):
        from bouncing_ball.render import render
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"smoke.mp4"
            cfg = Config(duration=4, width=270, height=480, output=output, preset="ultrafast")
            report = render(cfg)
            self.assertEqual(report["validation"]["frames"], 120)
            self.assertGreater(report["simulation"]["spawned"], 0)
            self.assertEqual(report["validation"]["full_decode"], "passed")
            self.assertGreater(output.stat().st_size, 10000)
            self.assertGreater(report["audio"]["rms"], .01)
            self.assertEqual(json.loads(output.with_suffix(".report.json").read_text())["validation"]["audio_codec"], "aac")
            with self.assertRaises(FileExistsError):
                render(cfg)
            self.assertEqual(list(Path(tmp).glob(".render-*")), [])


class ConfigurationTests(unittest.TestCase):
    def test_reject_invalid_dimensions_rates_and_missing_music(self):
        for cfg in (Config(width=100), Config(width=1000), Config(fps=29),
                    Config(duration=0), Config(music=Path("/missing/music.wav")),
                    Config(music_gain=2)):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                cfg.validate()


if __name__ == "__main__":
    unittest.main()
