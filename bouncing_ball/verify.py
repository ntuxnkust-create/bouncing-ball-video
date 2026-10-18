"""Independent checks of the produced MP4, including full-stream decoding."""
import json
from pathlib import Path
import subprocess


def probe(path: Path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(path)], text=True))


def verify_video(path: Path, width: int, height: int, fps: int, frames: int):
    metadata = probe(path)
    video = next((s for s in metadata["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in metadata["streams"] if s["codec_type"] == "audio"), None)
    if not video or not audio:
        raise RuntimeError("MP4 must contain both video and audio")
    if (video["width"], video["height"]) != (width, height):
        raise RuntimeError("Unexpected video dimensions")
    if video["codec_name"] != "h264" or video["pix_fmt"] != "yuv420p":
        raise RuntimeError("Video must be H.264 yuv420p")
    if audio["codec_name"] != "aac" or audio["channels"] != 2:
        raise RuntimeError("Audio must be stereo AAC")
    if int(video["nb_read_frames"]) != frames:
        raise RuntimeError(f"Frame count mismatch: {video['nb_read_frames']} != {frames}")
    num, den = map(int, video["avg_frame_rate"].split("/"))
    if abs(num/den-fps) > .0001:
        raise RuntimeError("Unexpected frame rate")
    target = frames/fps
    if abs(float(video["duration"])-target) > 1/fps:
        raise RuntimeError("Video duration does not match requested duration")
    if abs(float(audio["duration"])-target) > .1:
        raise RuntimeError("Audio duration does not match video")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                    "-f", "null", "-"], check=True, stdout=subprocess.DEVNULL)
    return {"video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
            "width": width, "height": height, "fps": fps, "frames": frames,
            "duration": float(video["duration"]), "full_decode": "passed",
            "bytes": path.stat().st_size}
