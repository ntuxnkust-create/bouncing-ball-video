"""Independent space theme; the original car configuration stays untouched."""
from dataclasses import dataclass, field
from pathlib import Path

from config import Brand, Config, SoundConfig

ROOT = Path(__file__).resolve().parents[1]
EMOJI = (
    Brand('Star', '⭐', (255, 219, 85), 35, '2b50.png'),
    Brand('Moon', '🌙', (255, 221, 131), 43, '1f319.png'),
    Brand('Saturn', '🪐', (219, 168, 239), 53, '1fa90.png'),
    Brand('Earth', '🌍', (100, 210, 244), 65, '1f30d.png'),
    Brand('Sun', '☀️', (255, 190, 72), 77, '2600.png'),
    Brand('Galaxy', '🌌', (183, 140, 255), 90, '1f30c.png'),
    Brand('Rocket', '🚀', (255, 157, 145), 102, '1f680.png'),
)


@dataclass(frozen=True)
class SpaceConfig(Config):
    duration: float = 30.0
    seed: int = 42
    title: str = 'Can They Reach the Final Form?'
    output: Path = ROOT / 'outputs/emoji-space-merge.mp4'
    background: Path = ROOT / 'assets/glass-container.png'
    geometry: Path = ROOT / 'assets/glass-container.geometry.json'
    logos_dir: Path = ROOT / 'assets/emoji'
    brands: tuple = EMOJI
    physics_hz: int = 240
    gravity: float = 1460.0
    elasticity: float = 0.58
    friction: float = 0.43
    spawn_interval: float = 0.40
    max_balls: int = 48
    merge_grace: float = 0.10
    sound: SoundConfig = field(default_factory=lambda: SoundConfig(
        # Keep original synthesized effects, with no external sound overrides.
        assets_dir=ROOT / 'assets/space-sounds', max_voices=8,
        wall_gain=.25, ball_gain=.28, merge_gain=.50, final_gain=.61,
        master_gain=1.15, ceiling=.82,
    ))
