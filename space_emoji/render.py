"""Streaming H.264/AAC export; publish final file only after complete decoding."""
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from bouncing_ball.audio import synthesize
from bouncing_ball.verify import verify_video
from .geometry import background_identity
from .graphics import SpaceRenderer
from .simulation import SpaceSimulation


def render(cfg, overwrite=False):
    cfg.validate()
    # Fail before expensive work and never silently replace the user's background.
    renderer = SpaceRenderer(cfg)
    for binary in ('ffmpeg', 'ffprobe'):
        if not shutil.which(binary):
            raise RuntimeError(f'{binary} must be installed')
    output = cfg.output.resolve()
    if output.exists() and not overwrite:
        raise FileExistsError(f'Output exists: {output}; choose another path or --overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    sim = SpaceSimulation(cfg)
    with tempfile.TemporaryDirectory(prefix='.space-render-', dir=output.parent) as directory:
        work = Path(directory)
        silent, wav, complete = work/'silent.mp4', work/'effects.wav', work/'complete.mp4'
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
               '-pixel_format', 'rgb24', '-video_size', f'{cfg.width}x{cfg.height}',
               '-framerate', str(cfg.fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264',
               '-preset', cfg.preset, '-crf', str(cfg.crf), '-pix_fmt', 'yuv420p',
               '-threads', str(cfg.encoder_threads), '-color_primaries', 'bt709',
               '-color_trc', 'bt709', '-colorspace', 'bt709',
               '-vf', 'scale=out_color_matrix=bt709', str(silent)]
        with (work/'encoder.log').open('w+') as log:
            encoder = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log)
            try:
                for frame in range(cfg.frames):
                    sim.step_frame()
                    image = renderer.draw(sim)
                    encoder.stdin.write(image.tobytes())
                    if frame % (cfg.fps*3) == 0:
                        print(f'Rendering {frame+1}/{cfg.frames}: merges={sim.merges}, level={sim.highest+1}', flush=True)
                    if frame in {0, cfg.frames//3, cfg.frames*2//3, cfg.frames-1}:
                        image.save(work/f'frame-{frame:04d}.png')
                encoder.stdin.close()
                if encoder.wait():
                    log.seek(0)
                    raise RuntimeError(log.read()[-5000:])
            except BaseException as error:
                if encoder.poll() is None:
                    encoder.kill()
                encoder.wait()
                if isinstance(error, BrokenPipeError):
                    log.seek(0)
                    raise RuntimeError(log.read()[-5000:]) from error
                raise
        audio = synthesize(cfg, sim.events, wav, presentation_offset=1/cfg.fps)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-i', str(silent), '-i', str(wav), '-map', '0:v:0', '-map', '1:a:0',
                        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', str(cfg.audio_rate),
                        '-ac', '2', '-t', str(cfg.frames/cfg.fps), '-movflags', '+faststart',
                        '-metadata', 'title=Space Emoji Merge', '-metadata',
                        'comment=Actual collision and merge sound effects; no music or speech', str(complete)], check=True)
        validation = verify_video(complete, cfg.width, cfg.height, cfg.fps, cfg.frames)
        report = {'simulation': sim.report(), 'audio': audio, 'validation': validation,
                  'background': background_identity(cfg.background), 'config': asdict(cfg),
                  'render_seconds': round(time.monotonic()-started, 2)}
        complete.replace(output)
        output.with_suffix('.report.json').write_text(json.dumps(report, indent=2, default=str)+'\n')
        output.with_suffix('.events.json').write_text(json.dumps([asdict(e) for e in sim.events], separators=(',', ':'))+'\n')
        stills = output.parent/(output.stem+'-stills')
        stills.mkdir(exist_ok=True)
        for path in work.glob('frame-*.png'):
            shutil.copy2(path, stills/path.name)
    print(json.dumps({'output': str(output), 'validation': validation, 'simulation': sim.report()}, indent=2))
    return report
