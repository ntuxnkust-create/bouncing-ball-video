"""Streaming encoder and atomic output publication. No full-video frame buffer."""
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import pygame as pg

from config import Config
from .audio import synthesize
from .graphics import Renderer
from .simulation import Simulation
from .verify import verify_video


def render(cfg: Config, overwrite=False):
    cfg.validate()
    for binary in ("ffmpeg", "ffprobe"):
        if shutil.which(binary) is None:
            raise RuntimeError(f"Install {binary} and make it available on PATH")
    output = cfg.output.resolve()
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output}; use --overwrite to replace")
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    sim, renderer = Simulation(cfg), Renderer(cfg)
    with tempfile.TemporaryDirectory(prefix=".render-", dir=output.parent) as scratch:
        work = Path(scratch)
        silent, wav, complete = work/"silent.mp4", work/"audio.wav", work/"complete.mp4"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size",
                   f"{cfg.width}x{cfg.height}", "-framerate", str(cfg.fps),
                   "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", cfg.preset,
                   "-crf", str(cfg.crf), "-pix_fmt", "yuv420p", "-threads", str(cfg.encoder_threads),
                   "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                   "-vf", "scale=out_color_matrix=bt709", str(silent)]
        with (work/"encoder.log").open("w+") as log:
            encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
            try:
                for frame in range(cfg.frames):
                    sim.step_frame()
                    surface = renderer.draw(sim)
                    encoder.stdin.write(pg.image.tobytes(surface, "RGB"))
                    if frame % max(1, cfg.fps*5) == 0:
                        print(f"Rendering {frame+1}/{cfg.frames} | {sim.time:.1f}s | "
                              f"merges={sim.merges} | level={sim.highest+1}", flush=True)
                    if frame in {cfg.frames//12, cfg.frames//3, cfg.frames*2//3,
                                 min(cfg.frames-1, round(cfg.frames*.92))}:
                        pg.image.save(surface, work/f"frame-{frame:04d}.png")
                encoder.stdin.close()
                if encoder.wait() != 0:
                    log.seek(0)
                    raise RuntimeError(f"FFmpeg encoder failed: {log.read()[-4000:]}")
            except BaseException as exc:
                if encoder.poll() is None:
                    encoder.kill()
                encoder.wait()
                if isinstance(exc, BrokenPipeError):
                    log.seek(0)
                    raise RuntimeError(f"FFmpeg encoder pipe failed: {log.read()[-4000:]}") from exc
                raise
        # Each frame presents the just-completed physics state at its start PTS.
        # Compensate this one-frame presentation offset, without quantizing events.
        audio_stats = synthesize(cfg, sim.events, wav, presentation_offset=1/cfg.fps)
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-i", str(silent), "-i", str(wav)]
        command += ["-map", "0:v:0", "-map", "1:a:0"]
        command += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(cfg.audio_rate),
                    "-ac", "2", "-t", str(cfg.frames/cfg.fps), "-movflags", "+faststart",
                    "-metadata", "title=Bouncing Ball Merge — The Final Form",
                    "-metadata", "comment=Event-synchronized sound effects only; no music or speech", str(complete)]
        subprocess.run(command, check=True)
        print("Validating complete video and audio streams…", flush=True)
        validation = verify_video(complete, cfg.width, cfg.height, cfg.fps, cfg.frames)
        report = {"simulation": sim.report(), "audio": audio_stats, "validation": validation,
                  "render_seconds": round(time.monotonic()-started, 2),
                  "config": asdict(cfg), "toolchain": {
                      "pygame": pg.version.ver, "pymunk": __import__("pymunk").version}}
        # Publish only after full decode succeeds; partial runs never replace output.
        complete.replace(output)
        report_path = output.with_suffix(".report.json")
        report_path.write_text(json.dumps(report, indent=2, default=str)+"\n")
        output.with_suffix(".events.json").write_text(json.dumps(
            [asdict(e) for e in sim.events], separators=(",", ":"))+"\n")
        stills = output.parent / f"{output.stem}-stills"
        stills.mkdir(exist_ok=True)
        for path in work.glob("frame-*.png"):
            shutil.copy2(path, stills/path.name)
    print(json.dumps({"output": str(output), "report": str(report_path),
                      "simulation": sim.report(), "validation": validation}, indent=2), flush=True)
    return report
