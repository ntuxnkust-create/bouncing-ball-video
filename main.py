#!/usr/bin/env python3
"""Render a 60-second vertical MP4 with event-triggered sound effects only."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import subprocess

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from config import Config


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Config.output)
    parser.add_argument("--duration", type=float, default=Config.duration)
    parser.add_argument("--fps", type=int, default=Config.fps)
    parser.add_argument("--width", type=int, default=Config.width)
    parser.add_argument("--height", type=int, default=Config.height)
    parser.add_argument("--seed", type=int, default=Config.seed)
    parser.add_argument("--logos-dir", type=Path, default=Config.logos_dir)
    parser.add_argument("--sounds-dir", type=Path, default=Config().sound.assets_dir,
                        help="Optional wall/ball/merge/final PCM WAV replacements")
    parser.add_argument("--no-score", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--crf", type=int, default=Config.crf)
    parser.add_argument("--preset", choices=("ultrafast", "veryfast", "fast", "medium", "slow"), default=Config.preset)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--simulate-only", action="store_true", help="Print full physics statistics without encoding")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = replace(Config(), **{k: v for k, v in vars(args).items()
                               if k not in {"no_score", "overwrite", "simulate_only", "sounds_dir"}},
                  sound=replace(Config().sound, assets_dir=args.sounds_dir), score=False)
    try:
        cfg.validate()
        if args.simulate_only:
            from bouncing_ball.simulation import Simulation
            sim = Simulation(cfg)
            for _ in range(cfg.frames):
                sim.step_frame()
            print(json.dumps(sim.report(), indent=2))
        else:
            from bouncing_ball.render import render
            render(cfg, args.overwrite)
    except (ValueError, RuntimeError, FileExistsError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled; incomplete render removed.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
