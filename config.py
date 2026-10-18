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
class Config:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float = 60.0
    seed: int = 42
    output: Path = Path("output/bouncing-ball-merge.mp4")
    logos_dir: Path = Path("assets/logos")
    music: Path | None = None
    music_gain: float = 0.18
    # Original, locally synthesized score; no downloaded music or samples.
    score: bool = True
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

