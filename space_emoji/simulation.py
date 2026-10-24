"""Space theme on the existing Chipmunk/contact/audio event architecture."""
from collections import Counter
import math

import pymunk

from bouncing_ball.simulation import Event, Simulation
from .geometry import GlassGeometry


class SpaceSimulation(Simulation):
    def __init__(self, cfg):
        self.geometry = GlassGeometry(cfg.geometry)
        self.max_escape = 0.0
        self.deferred_merges = 0
        self.merge_pairs = []
        self.blocked_spawns = 0
        self.merge_separation_passes = 0
        self.max_merge_residual_overlap = 0.0
        super().__init__(cfg)
        self.space.iterations = 40
        self.space.collision_slop = .10

    def _boundaries(self):
        walls = []
        for i, (a, b) in enumerate(self.geometry.segments):
            shape = pymunk.Segment(self.space.static_body, a, b, 1.0)
            if i > 0 and i+2 < len(self.geometry.points):
                shape.set_neighbors(self.geometry.points[i-1], self.geometry.points[i+2])
            shape.friction = self.cfg.friction
            shape.elasticity = self.cfg.elasticity
            shape.collision_type = 2
            walls.append(shape)
        self.space.add(*walls)

    def _merge(self):
        changed = False
        for aid, bid in sorted(self.pending):
            a, b = self.balls.get(aid), self.balls.get(bid)
            if a is None or b is None or a.level != b.level:
                continue
            level = a.level+1
            radius = self.cfg.brands[level].radius
            mass = a.body.mass+b.body.mass
            pos = (a.body.position*a.body.mass+b.body.position*b.body.mass)/mass
            pos = self.geometry.fit(pos, radius, padding=3)
            velocity = (a.body.velocity*a.body.mass+b.body.velocity*b.body.mass)/mass
            angle = (a.body.angle+b.body.angle)*.5
            spin = (a.body.angular_velocity+b.body.angular_velocity)*.5
            for ball in (a, b):
                self.space.remove(ball.body, ball.shape)
                del self.balls[ball.id]
            new = self.add_ball(level, pos, velocity, angle)
            new.body.angular_velocity = max(-5, min(5, spin))
            changed = True
            self.merges += 1
            self.merge_pairs.append((aid, bid))
            kind = 'final' if level == len(self.cfg.brands)-1 else 'merge'
            self.events.append(Event(self.time, kind, pos.x, pos.y, level, pair=(aid, bid)))
            if kind == 'final' and self.first_final is None:
                self.first_final = self.time
        self.pending.clear()
        if changed:
            self._separate_after_merge()

    def _separate_after_merge(self):
        """Release space after growth without rejecting contacts or adding kicks.

        Position-only, inverse-mass corrections propagate through the local pile.
        Reapply the real glass constraint on every pass, so pushing a neighboring
        ball cannot expel it through the wall. Velocities and merge momentum stay
        unchanged; Chipmunk handles subsequent movement and contact sound events.
        """
        balls = list(self.balls.values())
        # A small ball pinned between a heavy upgrade and the curved wall needs
        # more passes than an open pair. Stop as soon as contacts are separated.
        for _ in range(192):
            moved = set()
            for index, a in enumerate(balls):
                for b in balls[index+1:]:
                    delta = b.body.position-a.body.position
                    distance = delta.length
                    overlap = a.shape.radius+b.shape.radius-distance
                    if overlap <= .12:
                        continue
                    normal = delta/distance if distance > 1e-8 else pymunk.Vec2d(1, 0)
                    inverse_a, inverse_b = 1/a.body.mass, 1/b.body.mass
                    correction = normal*(overlap+.02)/(inverse_a+inverse_b)
                    a.body.position -= correction*inverse_a
                    b.body.position += correction*inverse_b
                    moved.update((a.id, b.id))
            if not moved:
                break
            self.merge_separation_passes += 1
            for ball in balls:
                if ball.id not in moved:
                    continue
                if self.geometry.clearance(ball.body.position) < ball.shape.radius+1:
                    ball.body.position = self.geometry.fit(ball.body.position, ball.shape.radius, padding=1)
        for ball in balls:
            self.space.reindex_shapes_for_body(ball.body)
        residual = max((a.shape.radius+b.shape.radius-(a.body.position-b.body.position).length
                        for index, a in enumerate(balls) for b in balls[index+1:]), default=0)
        self.max_merge_residual_overlap = max(self.max_merge_residual_overlap, residual)

    def _spawn(self):
        progress = self.time/self.cfg.duration
        # Unlock feeds 1–5 gradually, never Galaxy/Rocket. Every Galaxy and Rocket
        # is a real equal-level merge; all spawned sizes fit through the neck.
        ceiling = min(4, int(progress*5.6))
        counts = Counter(b.level for b in self.balls.values())
        weights = [.65**(ceiling-level) for level in range(ceiling+1)]
        level = self.rng.choices(list(range(ceiling+1)), weights)[0]
        if progress > .45 and self.rng.random() < .52:
            waiting = [k for k in counts if k <= ceiling and counts[k] % 2]
            if waiting:
                level = max(waiting)
        radius = self.cfg.brands[level].radius
        left, right = self.geometry.points[0].x, self.geometry.points[-1].x
        x = self.rng.uniform(left+radius+5, right-radius-5)
        pos = pymunk.Vec2d(x, -radius-6)
        if any((ball.body.position-pos).length < radius+ball.shape.radius+4 for ball in self.balls.values()):
            self.blocked_spawns += 1
            return
        ball = self.add_ball(level, pos, (self.rng.uniform(-48, 48), 125), self.rng.uniform(-.25, .25))
        ball.body.angular_velocity = self.rng.uniform(-1.6, 1.6)
        self.spawned += 1

    def _contain(self):
        for ball in self.balls.values():
            body = ball.body
            if body.velocity.length > 1400:
                body.velocity = body.velocity.normalized()*1400
            body.angular_velocity = max(-7, min(7, body.angular_velocity))
            # The open end above the picture is intentionally not a closed lid.
            if body.position.y < -100:
                continue
            clearance = self.geometry.clearance(body.position)
            penetration = ball.shape.radius+1-clearance
            self.max_escape = max(self.max_escape, penetration)
            if penetration > 2:
                old_velocity = body.velocity
                _, _, normal = self.geometry.closest(body.position)
                body.position = self.geometry.fit(body.position, ball.shape.radius, padding=1)
                outward = old_velocity.dot(normal)
                if outward < 0:
                    body.velocity -= normal*outward*(1+self.cfg.elasticity)
                self.space.reindex_shapes_for_body(body)
                self.boundary_corrections += 1

    def step_frame(self):
        dt = 1/self.cfg.physics_hz
        for _ in range(self.cfg.physics_hz//self.cfg.fps):
            # Continue feeding until the end, including after the first Rocket.
            if self.time+1e-9 >= self.next_spawn and self.time < self.cfg.duration-.8:
                if len(self.balls) < self.cfg.max_balls:
                    self._spawn()
                self.next_spawn += self.cfg.spawn_interval
            self.space.step(dt)
            self.time += dt
            self._merge()
            self._contain()
            self.peak_balls = max(self.peak_balls, len(self.balls))

    def report(self):
        return {**super().report(), 'theme': 'Space Emoji Merge',
                'levels': [b.name for b in self.cfg.brands],
                'max_pre_correction_wall_penetration_px': round(self.max_escape, 4),
                'deferred_crowded_merges': self.deferred_merges,
                'merge_separation_passes': self.merge_separation_passes,
                'max_merge_residual_overlap_px': round(self.max_merge_residual_overlap, 4),
                'blocked_spawns': self.blocked_spawns,
                'physics_hz': self.cfg.physics_hz,
                'geometry_registration': self.geometry.spec['reference_registration']}
