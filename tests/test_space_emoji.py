"""Space-theme behavior, independent geometry, actual codec and sound checks."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np
from PIL import Image
import pymunk

from bouncing_ball.audio import synthesize
from space_emoji.config import SpaceConfig, ROOT
from space_emoji.geometry import GlassGeometry, load_background
from space_emoji.simulation import SpaceSimulation


class GeometryTests(unittest.TestCase):
    def test_calibration_matches_untouched_original_png(self):
        spec = json.loads(SpaceConfig.geometry.read_text())
        original = ROOT/spec['source_filename']
        stored = SpaceConfig.background
        self.assertEqual(original.read_bytes(), stored.read_bytes())
        self.assertEqual(hashlib.sha256(stored.read_bytes()).hexdigest(), spec['source_sha256'])
        self.assertEqual(list(Image.open(stored).size), spec['source_size'])
        self.assertEqual(spec['reference_registration'], 'calibrated-original-png')

    def test_open_inlet_and_clearance(self):
        geo = GlassGeometry(SpaceConfig.geometry)
        self.assertTrue(geo.contains((540, 100)))
        self.assertGreater(geo.clearance((540, 200)), 100)
        self.assertTrue(geo.contains((540, 1200)))
        self.assertFalse(geo.contains((30, 1200)))
        # There is no segment joining the top guide tips.
        self.assertTrue(all(max(a.y,b.y) > -100 for a,b in geo.segments))
        sim = SpaceSimulation(SpaceConfig())
        self.assertEqual(len(sim.space.shapes), len(geo.points)-1)

    def test_inward_fit_respects_every_level(self):
        geo = GlassGeometry(SpaceConfig.geometry)
        for emoji in SpaceConfig.brands:
            for point in ((65,1110), (540,1535), (1015,1110), (460,700)):
                fitted = geo.fit(point, emoji.radius)
                self.assertGreaterEqual(geo.clearance(fitted), emoji.radius+1.8)
                self.assertLess((fitted-pymunk.Vec2d(*point)).length, 250)

    def test_missing_original_is_explicit(self):
        with self.assertRaisesRegex(FileNotFoundError, 'Original glass PNG missing'):
            load_background(Path('/nonexistent-glass-original.png'))

    def test_original_not_cropped_recolored_or_mutated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.png'
            original = Image.new('RGB', (1080,1920), (20,45,73))
            original.putpixel((300,700), (220,100,45))
            original.save(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            canvas = load_background(path)
            self.assertEqual(canvas.getpixel((300,700)), (220,100,45))
            self.assertEqual(canvas.getpixel((100,100)), (20,45,73))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


class EmojiTests(unittest.TestCase):
    def test_all_pngs_color_alpha_and_hashes(self):
        records = json.loads((ROOT/'assets/emoji/manifest.json').read_text())
        self.assertEqual(len(records),7)
        for record in records:
            path = ROOT/'assets/emoji'/record['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record['sha256'])
            image = Image.open(path).convert('RGBA')
            pixels = np.asarray(image)
            mask = pixels[:,:,3] > 100
            self.assertGreater(np.count_nonzero(mask),500)
            self.assertTrue(np.any(np.ptp(pixels[:,:,:3].astype(int),axis=2)[mask] > 50))
            self.assertLess(pixels[0,0,3],10)


class ContactTests(unittest.TestCase):
    def make(self):
        sim = SpaceSimulation(SpaceConfig())
        sim.next_spawn = float('inf')
        return sim

    def test_equal_contact_mass_and_pair_reuse(self):
        sim = self.make()
        sim.add_ball(0, (500,1150))
        sim.add_ball(0, (569,1150))
        for _ in range(12): sim.step_frame()
        self.assertEqual(sim.merges, 1)
        ball = next(iter(sim.balls.values()))
        self.assertEqual(ball.level, 1)
        self.assertEqual(ball.body.mass, 2)
        self.assertEqual(sim.merge_pairs, [(1,2)])
        self.assertGreaterEqual(sim.geometry.clearance(ball.body.position), ball.shape.radius-1)

    def test_different_levels_and_final_never_merge(self):
        for levels, distance in [((0,1),77), ((6,6),203)]:
            sim = self.make()
            sim.add_ball(levels[0], (430,1200))
            sim.add_ball(levels[1], (430+distance,1200))
            for _ in range(12): sim.step_frame()
            self.assertEqual(sim.merges,0)
            self.assertEqual(len(sim.balls),2)

    def test_largest_feed_falls_through_open_rails(self):
        sim = self.make()
        ball = sim.add_ball(4, (540,40), (0,50))
        for _ in range(36): sim.step_frame()
        self.assertGreater(ball.body.position.y, 850)
        self.assertLess(abs(ball.body.position.x-540),1)

    def test_fast_impact_stays_in_glass(self):
        sim = self.make()
        ball = sim.add_ball(0, (200,1100), (-1300,250))
        for _ in range(150):
            sim.step_frame()
            self.assertGreaterEqual(sim.geometry.clearance(ball.body.position), ball.shape.radius-1.1)
        self.assertTrue(any(e.kind=='wall' for e in sim.events))


class ProductionTests(unittest.TestCase):
    def test_full_900_frame_simulation_and_sound(self):
        cfg = SpaceConfig()
        sim = SpaceSimulation(cfg)
        for _ in range(cfg.frames):
            sim.step_frame()
            for ball in sim.balls.values():
                if ball.body.position.y >= 0:
                    self.assertGreaterEqual(sim.geometry.clearance(ball.body.position), ball.shape.radius-1.1)
        self.assertEqual(cfg.frames,900)
        self.assertEqual(sim.highest,6)
        self.assertIsNotNone(sim.first_final)
        self.assertGreater(sim.merges,25)
        self.assertGreater(sim.spawned,60)
        used = [ball_id for pair in sim.merge_pairs for ball_id in pair]
        self.assertEqual(len(used),len(set(used)))
        kinds = {e.kind for e in sim.events}
        self.assertEqual(kinds, {'wall','ball','merge','final'})
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory)/'effects.wav'
            stats = synthesize(cfg,sim.events,wav,presentation_offset=1/cfg.fps)
            with wave.open(str(wav)) as stream:
                self.assertEqual(stream.getnframes(),1440000)
                self.assertEqual(stream.getnchannels(),2)
            self.assertGreater(stats['rms'],.001)
            self.assertLessEqual(stats['peak'],cfg.sound.ceiling)
            self.assertFalse(stats['music'])
            self.assertFalse(stats['speech'])
            self.assertLessEqual(stats['max_scheduled_voices'],cfg.sound.max_voices)
            self.assertIn('final',stats['event_counts'])

    def test_real_encode_decode_pipeline_fixture_not_final_artwork(self):
        from space_emoji.render import render
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            background = directory/'test-fixture.png'
            Image.new('RGB',(1080,1920),(6,12,20)).save(background)
            cfg = replace(SpaceConfig(),duration=2.2,width=270,height=480,
                          background=background,output=directory/'codec-test.mp4',preset='ultrafast')
            report = render(cfg)
            self.assertEqual(report['validation']['frames'],66)
            self.assertGreater(report['simulation']['spawned'],2)
            self.assertGreater(report['audio']['audible_events'],0)
            self.assertEqual(report['validation']['full_decode'],'passed')
            self.assertEqual(report['validation']['audio_codec'],'aac')
            self.assertEqual(report['validation']['video_codec'],'h264')
            self.assertEqual(report['background']['sha256'],hashlib.sha256(background.read_bytes()).hexdigest())
            self.assertEqual(report['config']['title'],'Can They Reach the Final Form?')


if __name__ == '__main__':
    unittest.main()
