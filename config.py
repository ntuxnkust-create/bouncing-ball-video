"""All creative and physics defaults. Coordinates use a 1080 × 1920 canvas."""
from dataclasses import dataclass, field
import math
from pathlib import Path


@dataclass(frozen=True)
class Brand:
    name: str
    short: str
    color: tuple[int, int, int]
    radius: float
    logo: str


BRANDS = (
    Brand("RENAULT", "R", (255, 206, 56), 31, "renault.png"),
    Brand("FORD", "Ford", (65, 153, 255), 39, "ford.png"),
    Brand("MERCEDES-BENZ", "BENZ", (200, 224, 241), 49, "mercedes.png"),
    Brand("BMW", "BMW", (67, 197, 255), 62, "bmw.png"),
    Brand("FERRARI", "F", (255, 76, 75), 78, "ferrari.png"),
    Brand("LAMBORGHINI", "L", (188, 255, 64), 98, "lamborghini.png"),
    Brand("BUGATTI", "B", (191, 128, 255), 123, "bugatti.png"),
    Brand("APEX / FINAL FORM", "APEX", (255, 215, 100), 154, "final.png"),
)


@dataclass(frozen=True)
class SoundConfig:
    """Effects-only sound design; optional replacements are 16-bit PCM WAVs."""
    assets_dir: Path = Path("assets/sounds")
    wall_file: str = "wall.wav"
    ball_file: str = "ball.wav"
    merge_file: str = "merge.wav"
    final_file: str = "final.wav"
    wall_gain: float = 0.30
    ball_gain: float = 0.32
    merge_gain: float = 0.54
    final_gain: float = 0.67
    master_gain: float = 1.30
    ceiling: float = 0.86
    minimum_impact: float = 35.0
    full_impact: float = 600.0
    pair_cooldown: float = 0.12
    global_cooldown: float = 0.045
    max_voices: int = 8
    upgrade_duck_seconds: float = 0.24
    collision_duck_gain: float = 0.26
    block_frames: int = 48000

    def validate(self):
        gains = (self.wall_gain, self.ball_gain, self.merge_gain, self.final_gain,
                 self.master_gain, self.ceiling, self.collision_duck_gain)
        if any(not math.isfinite(v) or not 0 <= v <= 2 for v in gains):
            raise ValueError("Sound gains must be finite and between 0 and 2")
        if not 0 < self.ceiling <= .94 or not 0 <= self.collision_duck_gain <= 1:
            raise ValueError("Sound ceiling must be ≤0.94 and duck gain must be ≤1")
        if not 0 < self.minimum_impact < self.full_impact:
            raise ValueError("Impact thresholds must satisfy 0 < minimum < full")
        if any(not math.isfinite(v) or v < 0 for v in
               (self.pair_cooldown, self.global_cooldown, self.upgrade_duck_seconds)):
            raise ValueError("Sound cooldowns must be finite and nonnegative")
        if not 1 <= self.max_voices <= 64 or not 64 <= self.block_frames <= 192000:
            raise ValueError("Invalid sound polyphony or block size")


@dataclass(frozen=True)
class Config:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float = 60.0
    seed: int = 42
    output: Path = Path("output/bouncing-ball-sfx.mp4")
    logos_dir: Path = Path("assets/logos")
    music: Path | None = None
    music_gain: float = 0.18
    # Retained for old callers; music and score are rejected in effects-only mode.
    score: bool = False
    sound: SoundConfig = field(default_factory=SoundConfig)
    title: str = "Will They Merge Into The Final Form?"
    gravity: float = 1180.0
    elasticity: float = 0.48
    friction: float = 0.62
    physics_hz: int = 120
    arena_center: tuple[float, float] = (540.0, 1110.0)
    arena_radius: float = 460.0
    entrance_half_angle: float = 0.29
    spawn_interval: float = 0.70
    feed_unlock_rate: float = 5.6
    lower_level_weight: float = 0.40
    late_pairing_start: float = 0.72
    late_pairing_bias: float = 0.72
    max_balls: int = 65
    merge_equal_levels: bool = True
    merge_grace: float = 0.09
    crf: int = 18
    preset: str = "fast"
    encoder_threads: int = 4
    audio_rate: int = 48000
    brands: tuple[Brand, ...] = field(default=BRANDS)

    @property
    def frames(self) -> int:
        return round(self.duration * self.fps)

    def validate(self) -> None:
        self.sound.validate()
        if self.score or self.music is not None:
            raise ValueError("Effects-only mode: background music and voices are not supported")
        if self.audio_rate not in (44100, 48000):
            raise ValueError("Audio sample rate must be 44100 or 48000 Hz")
        if self.width < 270 or self.height < 480 or self.width % 2 or self.height % 2:
            raise ValueError("Video dimensions must be even and at least 270 × 480")
        if self.width * 16 != self.height * 9:
            raise ValueError("Use a 9:16 canvas (for example 1080 × 1920 or 540 × 960)")
        if not (1 <= self.fps <= 120 and 0 < self.duration <= 3600):
            raise ValueError("FPS must be 1–120; duration must be >0 and ≤3600 seconds")
        if self.frames < 1 or self.physics_hz <= 0 or self.physics_hz % self.fps:
            raise ValueError("physics_hz must be divisible by FPS and video needs ≥1 frame")
        if not 0 <= self.crf <= 35 or not 1 <= self.encoder_threads <= 32:
            raise ValueError("Invalid encoder CRF or thread count")
        if self.spawn_interval <= 0 or self.gravity <= 0 or self.max_balls < 2:
            raise ValueError("Invalid physics/spawn configuration")
        if not (0 <= self.music_gain <= 1 and 0 <= self.elasticity <= 1 and self.friction >= 0):
            raise ValueError("Invalid audio gain or material properties")
        if self.feed_unlock_rate <= 0 or not 0 < self.lower_level_weight <= 1:
            raise ValueError("Invalid feed progression")
        if not all(math.isfinite(v) for v in (self.gravity, self.friction, self.spawn_interval,
                                              self.feed_unlock_rate, self.arena_radius)):
            raise ValueError("Physics parameters must be finite")
        if not 0 <= self.late_pairing_start <= 1 or not 0 <= self.late_pairing_bias <= 1:
            raise ValueError("Pairing progress and probability must be between 0 and 1")
        if len(self.brands) < 2 or any(b.radius <= 0 for b in self.brands):
            raise ValueError("At least two brands with positive radii are needed")
        if self.music is not None and not self.music.is_file():
            raise ValueError(f"Music file does not exist: {self.music}")

