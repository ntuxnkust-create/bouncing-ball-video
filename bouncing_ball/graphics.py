"""Cached native-resolution artwork and time-based effects, with no display."""
from __future__ import annotations

import colorsys
import math
import os
from pathlib import Path
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame as pg

from config import Config


class Renderer:
    def __init__(self, cfg: Config):
        pg.font.init()
        self.cfg = cfg
        self.canvas = pg.Surface((1080, 1920))
        self.fonts = {}
        self.font_path = next((str(p) for p in (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        ) if p.is_file()), None)
        self.bold_path = next((str(p) for p in (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ) if p.is_file()), self.font_path)
        self.base = self._background()
        self.sprites = [self._sprite(i) for i in range(len(cfg.brands))]
        self.icons = [pg.transform.smoothscale(s, (74, 74)) for s in self.sprites]
        self.glows = [self._glow(100, b.color) for b in cfg.brands]
        self.seen_events = 0
        self.effects = []
        self.particles = []
        self.rng = random.Random(cfg.seed+10000)
        self.newest_merge = None

    def font(self, size, bold=False):
        key = (int(size), bold)
        if key not in self.fonts:
            self.fonts[key] = pg.font.Font(self.bold_path if bold else self.font_path, int(size))
        return self.fonts[key]

    def text(self, surface, text, size, color, center, bold=False):
        image = self.font(size, bold).render(text, True, color)
        surface.blit(image, image.get_rect(center=center))

    def _background(self):
        w, h = 1080, 1920
        cx, cy = self.cfg.arena_center
        yy, xx = np.mgrid[0:h, 0:w]
        dist = np.sqrt((xx-cx)**2+(yy-cy)**2)
        theta = np.arctan2(yy-cy, xx-cx)
        hue = ((theta+math.pi/2)/(math.pi*2)) % 1
        # Continuous spectrum with a bright core and a soft additive halo.
        rgb = np.stack([np.clip(np.abs((hue*6+k)%6-3)-1, 0, 1)
                        for k in (0, 4, 2)], axis=-1)
        rgb = 0.17 + 0.83*rgb
        delta = np.abs(dist-self.cfg.arena_radius)
        strength = 0.32*np.exp(-(delta/17)**2) + 0.40*np.exp(-(delta/6)**2)
        strength += 0.8*np.exp(-(delta/2.5)**4)
        opening = (np.abs(theta+math.pi/2) < self.cfg.entrance_half_angle) & (yy < cy)
        strength[opening] = 0
        arr = np.uint8(np.clip(rgb*strength[..., None]*255, 0, 255))
        surface = pg.surfarray.make_surface(arr.transpose(1, 0, 2))
        opening_x = self.cfg.arena_radius*math.sin(self.cfg.entrance_half_angle)
        for side in (-1, 1):
            x = round(cx+side*opening_x)
            end = round(cy-self.cfg.arena_radius*math.cos(self.cfg.entrance_half_angle))
            for width, col in ((24, (4, 11, 16)), (12, (12, 35, 44)),
                               (5, (45, 116, 132)), (2, (170, 234, 246))):
                pg.draw.line(surface, col, (x, 355), (x, end), width)
            pg.draw.circle(surface, (212, 247, 255), (x, 355), 3)
        self.text(surface, "THE MERGE EXPERIMENT", 21, (118, 136, 157), (540, 91), True)
        # Wrap arbitrary configured titles into at most three readable lines.
        words, lines, line = self.cfg.title.split(), [], ""
        for word in words:
            candidate = (line+" "+word).strip()
            if self.font(53, True).size(candidate)[0] > 950 and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        if self.cfg.title == "Will They Merge Into The Final Form?":
            lines = ["Will They Merge Into", "The Final Form?"]
        for i, line in enumerate(lines[:3]):
            self.text(surface, line, 53, (245, 248, 255), (540, 168+i*68), True)
        self.text(surface, "SAME LEVEL.  ONE UPGRADE.", 19, (110, 124, 147), (540, 309))
        pg.draw.line(surface, (28, 33, 44), (100, 1640), (980, 1640), 1)
        self.text(surface, "EVOLUTION", 18, (120, 134, 153), (540, 1684), True)
        return surface

    def _glow(self, radius, color):
        yy, xx = np.mgrid[-radius:radius+1, -radius:radius+1]
        alpha = np.exp(-(xx*xx+yy*yy)/(radius*.44)**2)
        surface = pg.Surface((radius*2+1, radius*2+1), pg.SRCALPHA)
        rgb = pg.surfarray.pixels3d(surface)
        rgb[:] = color
        del rgb
        a = pg.surfarray.pixels_alpha(surface)
        a[:] = np.uint8(alpha.T*165)
        del a
        return surface

    def _sprite(self, level):
        brand = self.cfg.brands[level]
        # Draw emblems at 2× and reduce once for clean small-circle typography.
        r = round(brand.radius*2)
        c = r+40
        n = c*2+1
        yy, xx = np.mgrid[0:n, 0:n]
        dx, dy = (xx-c)/r, (yy-c)/r
        dist = np.sqrt(dx*dx+dy*dy)
        edge = np.clip((1-dist)*r, 0, 1)
        highlight = np.exp(-((dx+.36)**2+(dy+.45)**2)/.36)
        rim = np.exp(-((dist-.96)/.028)**2)
        rgb = np.zeros((n, n, 3))
        color = np.array(brand.color)
        for channel in range(3):
            rgb[:, :, channel] = 7+color[channel]*(.07+.18*highlight+.70*rim)
        surf = pg.Surface((n, n), pg.SRCALPHA)
        pixels = pg.surfarray.pixels3d(surf)
        pixels[:] = np.uint8(np.clip(rgb, 0, 255)).transpose(1, 0, 2)
        del pixels
        alpha = pg.surfarray.pixels_alpha(surf)
        alpha[:] = np.uint8(edge.T*255)
        del alpha
        logo_path = self.cfg.logos_dir / brand.logo
        if logo_path.is_file():
            logo = pg.image.load(str(logo_path))
            bound = r*1.36
            scale = min(bound/logo.get_width(), bound/logo.get_height())
            logo = pg.transform.smoothscale(logo, (max(1, round(logo.get_width()*scale)),
                                                    max(1, round(logo.get_height()*scale))))
            surf.blit(logo, logo.get_rect(center=(c, c)))
        else:
            self._emblem(surf, level, c, r)
        # A small curved-looking specular streak provides a glass finish.
        rect = pg.Rect(c-r+5, c-r+5, r*2-10, r*2-10)
        pg.draw.arc(surf, (*brand.color, 135), rect, .72, 2.20, max(1, r//25))
        return pg.transform.smoothscale(surf, (n//2, n//2))

    def _emblem(self, surf, level, c, r):
        white = (232, 239, 248)
        color = self.cfg.brands[level].color
        def point(x, y):
            return (round(c+x*r), round(c+y*r))
        def poly(points, col, width=0):
            pg.draw.polygon(surf, col, [point(*p) for p in points], width)
        line = max(2, r//16)
        if level == 0:  # Renault-inspired double diamond
            poly([(0, -.65), (.42, 0), (0, .65), (-.42, 0)], color, line)
            poly([(0, -.40), (.25, 0), (0, .40), (-.25, 0)], white, max(1, line//2))
        elif level == 1:
            pg.draw.ellipse(surf, (28, 81, 163), (c-r*.83, c-r*.44, r*1.66, r*.88))
            pg.draw.ellipse(surf, white, (c-r*.83, c-r*.44, r*1.66, r*.88), line)
            font = pg.font.Font(self.bold_path, round(r*.58))
            font.set_italic(True)
            text = font.render("Ford", True, white)
            surf.blit(text, text.get_rect(center=(c, c)))
        elif level == 2:
            pg.draw.circle(surf, white, (c, c), round(r*.69), line)
            for a in (-math.pi/2, math.pi/6, 5*math.pi/6):
                tip = (math.cos(a)*.65, math.sin(a)*.65)
                poly([tip, (math.cos(a+1.6)*.11, math.sin(a+1.6)*.11),
                      (math.cos(a-1.6)*.11, math.sin(a-1.6)*.11)], white)
        elif level == 3:
            pg.draw.circle(surf, white, (c, c), round(r*.68))
            pg.draw.circle(surf, (36, 140, 235), (c, c), round(r*.48))
            for start in (0, math.pi):
                sector = [(0, 0)] + [(.48*math.cos(start+j*math.pi/64),
                                      -.48*math.sin(start+j*math.pi/64)) for j in range(33)]
                poly(sector, white)
            pg.draw.circle(surf, (10, 16, 24), (c, c), round(r*.68), max(4, round(r*.17)))
            self.text(surf, "BMW", round(r*.25), white, (c, c-round(r*.57)), True)
        elif level in (4, 5):
            shield = [(-.56, -.68), (.56, -.68), (.48, .24), (0, .73), (-.48, .24)]
            poly(shield, color)
            poly([(-.47, -.59), (.47, -.59), (.39, .19), (0, .59), (-.39, .19)], (17, 19, 22))
            # Original heraldic monogram rather than a downloaded trademark asset.
            self.text(surf, "SF" if level == 4 else "V12", round(r*.48), color,
                      (c, c-round(r*.05)), True)
            self.text(surf, "FERRARI" if level == 4 else "LAMBO", round(r*.16), color,
                      (c, c+round(r*.33)), True)
        elif level == 6:
            pg.draw.ellipse(surf, (128, 25, 48), (c-r*.80, c-r*.43, r*1.60, r*.86))
            pg.draw.ellipse(surf, white, (c-r*.80, c-r*.43, r*1.60, r*.86), line)
            self.text(surf, "BUGATTI", round(r*.30), white, (c, c), True)
            self.text(surf, "EB", round(r*.17), white, (c, c-round(r*.24)), True)
        else:
            poly([(-.49, -.46), (-.31, -.10), (0, -.60), (.31, -.10), (.49, -.46),
                  (.39, .05), (-.39, .05)], color)
            self.text(surf, "APEX", round(r*.49), color, (c, c+round(r*.33)), True)
            self.text(surf, "FINAL FORM", round(r*.16), white, (c, c+round(r*.62)), True)

    def _ingest(self, sim):
        for event in sim.events[self.seen_events:]:
            if event.kind not in {"merge", "final"}:
                continue
            self.effects.append(event)
            self.newest_merge = event
            count = 110 if event.kind == "final" else 18+event.level*5
            for _ in range(count):
                a = self.rng.uniform(0, math.tau)
                speed = self.rng.uniform(80, 380 if event.kind == "final" else 220)
                life = self.rng.uniform(.45, 1.8 if event.kind == "final" else 1.0)
                self.particles.append((event, math.cos(a)*speed, math.sin(a)*speed,
                                       life, self.rng.uniform(1.5, 4)))
        self.seen_events = len(sim.events)

    def draw(self, sim):
        self._ingest(sim)
        s = self.canvas
        s.blit(self.base, (0, 0))
        t = sim.time
        # Spectrum sparks traveling around the ring, never over the inlet.
        cx, cy = self.cfg.arena_center
        for i in range(3):
            a = (t*.22+i*math.tau/3) % math.tau
            if abs((a+math.pi/2+math.pi) % math.tau-math.pi) > self.cfg.entrance_half_angle:
                p = (round(cx+math.cos(a)*self.cfg.arena_radius),
                     round(cy+math.sin(a)*self.cfg.arena_radius))
                col = tuple(round(v*255) for v in colorsys.hsv_to_rgb((a/math.tau+.25)%1, .55, 1))
                pg.draw.circle(s, col, p, 4)
        self.effects = [e for e in self.effects if t-e.time < 2]
        for e in self.effects:
            age = t-e.time
            life = 1.8 if e.kind == "final" else .7
            if age > life:
                continue
            glow = self.glows[e.level].copy()
            size = round((self.cfg.brands[e.level].radius*3)*(1+age*.7))
            glow = pg.transform.smoothscale(glow, (size, size))
            glow.set_alpha(round(180*(1-age/life)))
            s.blit(glow, glow.get_rect(center=(e.x, e.y)))
            radius = round(self.cfg.brands[e.level].radius+age*160)
            col = tuple(round(v*(1-age/life)) for v in self.cfg.brands[e.level].color)
            pg.draw.circle(s, col, (round(e.x), round(e.y)), radius, 2)
        for ball in sorted(sim.balls.values(), key=lambda b: b.level):
            age = t-ball.born
            # Critically damped visual overshoot; physical collider stays stable.
            scale = 1+.20*math.exp(-age*7)*math.sin(age*18)
            sprite = pg.transform.rotozoom(self.sprites[ball.level],
                                           -math.degrees(ball.body.angle), scale)
            s.blit(sprite, sprite.get_rect(center=ball.body.position))
        self.particles = [p for p in self.particles if t-p[0].time < p[3]]
        for e, vx, vy, life, size in self.particles:
            age = t-e.time
            color = tuple(round(v*(1-age/life)) for v in self.cfg.brands[e.level].color)
            pos = (round(e.x+vx*age), round(e.y+vy*age+90*age*age))
            pg.draw.circle(s, color, pos, max(1, round(size*(1-age/life))))
        # Quiet data panels give context without mimicking a social app interface.
        self.text(s, "MERGES", 18, (112, 129, 150), (205, 394), True)
        self.text(s, f"{sim.merges:02d}", 55, (234, 241, 255), (205, 446), True)
        self.text(s, "HIGHEST LEVEL", 18, (112, 129, 150), (870, 394), True)
        self.text(s, f"{sim.highest+1:02d} / {len(self.cfg.brands):02d}", 38,
                  self.cfg.brands[sim.highest].color, (870, 446), True)
        self.text(s, "DROP ZONE", 15, (91, 118, 132), (540, 359))
        if sim.first_final is not None:
            age = t-sim.first_final
            if age < 4.7:
                opacity = min(1, age*3, (4.7-age)*2)
                banner = pg.Surface((960, 180), pg.SRCALPHA)
                self.text(banner, "FINAL FORM UNLOCKED", 47, (255, 223, 133), (480, 60), True)
                self.text(banner, "A P E X", 25, (255, 247, 224), (480, 118), True)
                banner.set_alpha(round(255*opacity))
                s.blit(banner, (60, 675))
        elif self.newest_merge and t-self.newest_merge.time < 1.1:
            e = self.newest_merge
            brand = self.cfg.brands[e.level]
            self.text(s, f"LEVEL {e.level+1:02d}  /  {brand.name}", 24,
                      brand.color, (540, 617), True)
        # Full evolution ladder including the final form, readable in phone crops.
        count = len(self.cfg.brands)
        for i, brand in enumerate(self.cfg.brands):
            x = round(130+i*820/max(1, count-1))
            if i < count-1:
                pg.draw.line(s, (42, 44, 52), (x+41, 1755), (round(x+820/max(1,count-1)-41), 1755), 2)
            icon = self.icons[i]
            if i > sim.highest:
                icon = icon.copy()
                icon.set_alpha(65)
            s.blit(icon, icon.get_rect(center=(x, 1755)))
            self.text(s, f"{i+1:02d}", 15, brand.color if i <= sim.highest else (65, 68, 81),
                      (x, 1810), True)
        elapsed = min(self.cfg.frames/self.cfg.fps, t)
        self.text(s, f"{int(elapsed)//60:02d}:{int(elapsed)%60:02d}", 18,
                  (135, 149, 169), (126, 1870))
        self.text(s, "BOUNCING BALL MERGE", 17, (105, 120, 143), (540, 1870), True)
        pg.draw.rect(s, (22, 26, 35), (100, 1900, 880, 3), border_radius=2)
        pg.draw.rect(s, (125, 188, 215), (100, 1900, round(880*elapsed/self.cfg.duration), 3), border_radius=2)
        if (self.cfg.width, self.cfg.height) != (1080, 1920):
            return pg.transform.smoothscale(s, (self.cfg.width, self.cfg.height))
        return s
