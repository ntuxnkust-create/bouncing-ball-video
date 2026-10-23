"""Fixed-step Chipmunk physics. Only genuine equal-level contacts can merge."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import random

import pymunk

from config import Config


@dataclass
class Ball:
    id: int
    level: int
    body: pymunk.Body
    shape: pymunk.Circle
    born: float


@dataclass(frozen=True)
class Event:
    time: float
    kind: str
    x: float
    y: float
    level: int
    strength: float = 1.0
    pair: tuple[int, ...] = ()
    impact: float = 0.0


class Simulation:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.space = pymunk.Space()
        self.space.gravity = (0, cfg.gravity)
        self.space.damping = 0.997
        self.space.iterations = 30
        self.space.collision_slop = 0.15
        self.balls: dict[int, Ball] = {}
        self.time = 0.0
        self.next_id = 1
        self.next_spawn = 0.15
        self.events: list[Event] = []
        self.pending: set[tuple[int, int]] = set()
        self.last_hit: dict[tuple, float] = {}
        self.spawned = 0
        self.merges = 0
        self.highest = 0
        self.first_final: float | None = None
        self.peak_balls = 0
        self.boundary_corrections = 0
        self._boundaries()
        self.space.on_collision(1, 1, post_solve=self._contact)
        self.space.on_collision(1, 2, post_solve=self._contact)

    def _boundaries(self):
        cx, cy = self.cfg.arena_center
        radius = self.cfg.arena_radius
        gap = self.cfg.entrance_half_angle
        segments = []
        # Open at twelve o'clock; no invisible lid across the falling-ball inlet.
        count = 180
        start, end = -math.pi / 2 + gap, 3 * math.pi / 2 - gap
        for i in range(count):
            a, b = start + (end-start)*i/count, start + (end-start)*(i+1)/count
            segments.append(pymunk.Segment(self.space.static_body,
                (cx+radius*math.cos(a), cy+radius*math.sin(a)),
                (cx+radius*math.cos(b), cy+radius*math.sin(b)), 5))
        opening = radius * math.sin(gap)
        for side in (-1, 1):
            x = cx + side * opening
            segments.append(pymunk.Segment(self.space.static_body, (x, 355),
                (x, cy-radius*math.cos(gap)), 5))
        for shape in segments:
            shape.friction = self.cfg.friction
            shape.elasticity = self.cfg.elasticity
            shape.collision_type = 2
        self.space.add(*segments)

    def add_ball(self, level: int, position, velocity=(0, 0), angle=0.0) -> Ball:
        radius = self.cfg.brands[level].radius
        mass = 2.0 ** level
        body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, radius))
        body.position, body.velocity, body.angle = position, velocity, angle
        shape = pymunk.Circle(body, radius)
        shape.elasticity = self.cfg.elasticity
        shape.friction = self.cfg.friction
        shape.collision_type = 1
        shape.ball_id = self.next_id
        ball = Ball(self.next_id, level, body, shape, self.time)
        self.next_id += 1
        self.balls[ball.id] = ball
        self.space.add(body, shape)
        self.highest = max(self.highest, level)
        return ball

    def _contact(self, arbiter, space, data):
        a, b = arbiter.shapes
        aid, bid = getattr(a, "ball_id", None), getattr(b, "ball_id", None)
        ba, bb = self.balls.get(aid), self.balls.get(bid)
        if (self.cfg.merge_equal_levels and ba and bb and ba.level == bb.level
                and ba.level < len(self.cfg.brands)-1
                and self.time - max(ba.born, bb.born) >= self.cfg.merge_grace):
            self.pending.add(tuple(sorted((aid, bid))))
        # Audio observation only: no impulses, bodies or merge decisions change.
        dynamic = [ball for ball in (ba, bb) if ball is not None]
        inverse_mass = sum(1/ball.body.mass for ball in dynamic)
        impact = arbiter.total_impulse.length * inverse_mass
        if dynamic and impact >= self.cfg.sound.minimum_impact:
            kind = "ball" if ba and bb else "wall"
            pair = tuple(sorted(ball.id for ball in dynamic))
            key = (kind, pair)
            when = self.time + 1/self.cfg.physics_hz
            if when-self.last_hit.get(key, -1) >= self.cfg.sound.pair_cooldown:
                self.last_hit[key] = when
                points = arbiter.contact_point_set.points
                p = ((points[0].point_a + points[0].point_b)/2 if points
                     else dynamic[0].body.position)
                strength = min(1.0, impact/self.cfg.sound.full_impact)
                self.events.append(Event(when, kind, p.x, p.y,
                                         max(ball.level for ball in dynamic), strength, pair, impact))

    def _merge(self):
        for aid, bid in sorted(self.pending):
            a, b = self.balls.get(aid), self.balls.get(bid)
            if not a or not b or a.level != b.level:
                continue
            mass = a.body.mass + b.body.mass
            position = (a.body.position*a.body.mass + b.body.position*b.body.mass) / mass
            velocity = (a.body.velocity*a.body.mass + b.body.velocity*b.body.mass) / mass
            level = a.level + 1
            # Keep the larger new shape inside the wall at its birth.
            center = pymunk.Vec2d(*self.cfg.arena_center)
            relative = position - center
            limit = self.cfg.arena_radius - self.cfg.brands[level].radius - 7
            if relative.length > limit:
                position = center + relative.normalized() * limit
            spin = (a.body.angular_velocity + b.body.angular_velocity) * 0.5
            for ball in (a, b):
                self.space.remove(ball.shape, ball.body)
                del self.balls[ball.id]
                for key in tuple(self.last_hit):
                    if ball.id in key[1]:
                        self.last_hit.pop(key)
            merged = self.add_ball(level, position, velocity, (a.body.angle+b.body.angle)/2)
            merged.body.angular_velocity = spin
            self.merges += 1
            kind = "final" if level == len(self.cfg.brands)-1 else "merge"
            self.events.append(Event(self.time, kind, position.x, position.y, level))
            if kind == "final" and self.first_final is None:
                self.first_final = self.time
        self.pending.clear()

    def _spawn(self):
        progress = self.time / self.cfg.duration
        # Gradually unlock higher feeds to make the late game achievable in 60 s.
        # All upgrades still require equal-level contact in the physics engine.
        ceiling = min(len(self.cfg.brands)-2, int(progress*self.cfg.feed_unlock_rate))
        levels = list(range(ceiling+1))
        weights = [self.cfg.lower_level_weight ** (ceiling-level) for level in levels]
        level = self.rng.choices(levels, weights)[0]
        # Late feeds favor the highest waiting pair, never spawn the final form.
        counts = Counter(b.level for b in self.balls.values())
        if progress > self.cfg.late_pairing_start and self.rng.random() < self.cfg.late_pairing_bias:
            candidates = [k for k in counts if k <= ceiling]
            if candidates:
                level = max(candidates)
        opening = self.cfg.arena_radius * math.sin(self.cfg.entrance_half_angle)
        # Custom oversized feeds are delivered just inside the inlet if they
        # cannot fit through the guides. Default feed radii all fit the inlet.
        radius = self.cfg.brands[level].radius
        x = self.cfg.arena_center[0] + self.rng.uniform(-1, 1)*max(0, opening-radius-12)
        y = 390 if radius < opening-8 else self.cfg.arena_center[1]-self.cfg.arena_radius+radius+12
        ball = self.add_ball(level, (x, y), (self.rng.uniform(-90, 90), 100),
                             self.rng.uniform(-0.4, 0.4))
        ball.body.angular_velocity = self.rng.uniform(-2.4, 2.4)
        self.spawned += 1

    def step_frame(self):
        dt = 1 / self.cfg.physics_hz
        for _ in range(self.cfg.physics_hz // self.cfg.fps):
            # Leave a breathing space at the end for the final reveal.
            if (self.time >= self.next_spawn and self.time < self.cfg.duration-min(3, self.cfg.duration*.1)
                    and self.first_final is None):
                if len(self.balls) < self.cfg.max_balls:
                    self._spawn()
                self.next_spawn += self.cfg.spawn_interval
            self.space.step(dt)
            self.time += dt
            self._merge()
            self._contain()
            self.peak_balls = max(self.peak_balls, len(self.balls))

    def _contain(self):
        # Continuous circular contact safety for deep overlaps after a merge.
        # Chipmunk handles normal contacts; this prevents discrete tunneling.
        center = pymunk.Vec2d(*self.cfg.arena_center)
        for ball in self.balls.values():
            body = ball.body
            if body.velocity.length > 1250:
                body.velocity = body.velocity.normalized()*1250
            relative = body.position-center
            limit = self.cfg.arena_radius-ball.shape.radius-6
            if body.position.y > center.y-self.cfg.arena_radius+150 and relative.length > limit+2:
                normal = relative.normalized()
                body.position = center+normal*limit
                outward = body.velocity.dot(normal)
                if outward > 0:
                    body.velocity -= normal*outward*(1+self.cfg.elasticity)
                self.space.reindex_shapes_for_body(body)
                self.boundary_corrections += 1

    def report(self):
        return {"seed": self.cfg.seed, "duration": self.cfg.frames/self.cfg.fps,
                "frames": self.cfg.frames, "spawned": self.spawned,
                "merges": self.merges, "highest_level": self.highest+1,
                "final_form_time": self.first_final, "peak_balls": self.peak_balls,
                "remaining_balls": len(self.balls), "events": len(self.events),
                "boundary_corrections": self.boundary_corrections,
                "level_counts": dict(sorted(Counter(b.level+1 for b in self.balls.values()).items()))}
