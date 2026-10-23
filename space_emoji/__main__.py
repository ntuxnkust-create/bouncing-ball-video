"""python -m space_emoji: production renderer, simulation, sound, calibration."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import sys

from bouncing_ball.audio import synthesize
from .config import SpaceConfig, ROOT
from .geometry import GlassGeometry
from .simulation import SpaceSimulation


def main(argv=None):
    parser = argparse.ArgumentParser(description='Space Emoji Merge — 30-second H.264/AAC production export')
    parser.add_argument('--background', type=Path, help='Original supplied glass PNG (no replacement)')
    parser.add_argument('--import-background', type=Path, help='Copy original PNG into project assets, then render')
    parser.add_argument('--geometry', type=Path, default=SpaceConfig.geometry)
    parser.add_argument('--output', type=Path, default=SpaceConfig.output)
    parser.add_argument('--duration', type=float, default=30)
    parser.add_argument('--seed', type=int, default=SpaceConfig.seed)
    parser.add_argument('--width', type=int, default=1080)
    parser.add_argument('--height', type=int, default=1920)
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--simulate-only', action='store_true')
    parser.add_argument('--audio-only', action='store_true', help='Full real-event simulation plus effects WAV; no video claim')
    parser.add_argument('--calibrate', type=Path, help='Write a separate geometry overlay PNG, not a production frame')
    args = parser.parse_args(argv)
    cfg = SpaceConfig(duration=args.duration, seed=args.seed, output=args.output,
                      geometry=args.geometry, width=args.width, height=args.height)
    if args.background:
        cfg = replace(cfg, background=args.background.resolve())
    cfg.validate()
    if args.import_background:
        from .geometry import load_background
        load_background(args.import_background)  # validate before copying
        destination = ROOT/'assets/glass-container.png'
        if destination.exists() and destination.resolve() != args.import_background.resolve():
            raise FileExistsError('Original background already stored; will not overwrite it')
        if destination.resolve() != args.import_background.resolve():
            shutil.copy2(args.import_background, destination)
        cfg = replace(cfg, background=destination)
    if args.calibrate:
        GlassGeometry(cfg.geometry).draw_debug(cfg.background, args.calibrate)
        return
    if args.simulate_only or args.audio_only:
        sim = SpaceSimulation(cfg)
        for _ in range(cfg.frames):
            sim.step_frame()
        cfg.output.parent.mkdir(parents=True, exist_ok=True)
        report = {'simulation': sim.report(), 'video_rendered': False,
                  'background_available': cfg.background.is_file()}
        if args.audio_only:
            report['audio'] = synthesize(cfg, sim.events, cfg.output.with_suffix('.effects.wav'),
                                        presentation_offset=1/cfg.fps)
        cfg.output.with_suffix('.simulation.json').write_text(json.dumps(report, indent=2)+'\n')
        cfg.output.with_suffix('.events.json').write_text(json.dumps([asdict(e) for e in sim.events], separators=(',', ':'))+'\n')
        print(json.dumps(report, indent=2))
    else:
        from .render import render
        render(cfg, overwrite=args.overwrite)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as error:
        print(f'Space Emoji Merge: {error}', file=sys.stderr)
        sys.exit(1)
