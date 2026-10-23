"""Pillow RGBA sprites above the unmodified supplied glass artwork."""
from functools import lru_cache
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .geometry import load_background


class SpaceRenderer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.background = load_background(cfg.background).convert('RGBA')
        self.textures = []
        for emoji in cfg.brands:
            path = cfg.logos_dir/emoji.logo
            if not path.is_file():
                raise FileNotFoundError(f'Missing full-color emoji: {path}; run scripts/fetch_space_emoji.py')
            with Image.open(path) as original:
                sprite = original.convert('RGBA')
            diameter = round(emoji.radius*1.88)
            sprite.thumbnail((diameter, diameter), Image.Resampling.LANCZOS)
            # thumbnail never upscales; explicitly resize the consistent square assets.
            sprite = sprite.resize((diameter, diameter), Image.Resampling.LANCZOS)
            side = diameter+32
            glow = Image.new('RGBA', (side, side))
            draw = ImageDraw.Draw(glow)
            draw.ellipse((18, 18, side-18, side-18), fill=(*emoji.color, 24))
            glow = glow.filter(ImageFilter.GaussianBlur(9))
            shadow = Image.new('RGBA', (side, side))
            shadow.paste((0, 0, 0, 90), (16, 20), sprite.getchannel('A'))
            shadow = shadow.filter(ImageFilter.GaussianBlur(3))
            glow.alpha_composite(shadow)
            glow.alpha_composite(sprite, (16, 16))
            self.textures.append(glow)
        self.font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
        self.small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
        self.background = self._footer(self.background)

    def _footer(self, image):
        draw = ImageDraw.Draw(image)
        # Original image's inlet runs through the top: title lives below the bulb.
        draw.text((540, 1716), self.cfg.title, font=self.font, anchor='mm', fill=(227, 236, 248),
                  stroke_width=1, stroke_fill=(0, 0, 0))
        draw.text((540, 1666), 'S P A C E   E M O J I   M E R G E', font=self.small,
                  anchor='mm', fill=(131, 174, 202))
        for level, texture in enumerate(self.textures):
            icon = texture.resize((60, 60), Image.Resampling.LANCZOS)
            image.alpha_composite(icon, (264+level*80, 1775))
        return image

    @lru_cache(maxsize=512)
    def rotated(self, level, angle):
        return self.textures[level].rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)

    def draw(self, sim):
        image = self.background.copy()
        for ball in sorted(sim.balls.values(), key=lambda b: (b.level, b.id)):
            # Body angle is clockwise in screen space; PIL rotates counterclockwise.
            angle = round(-math.degrees(ball.body.angle)/3)*3 % 360
            texture = self.rotated(ball.level, angle)
            age = sim.time-ball.born
            if age < .20:
                scale = .83+.17*min(1, age/.14)+.055*math.sin(min(1, age/.20)*math.pi)
                texture = texture.resize((round(texture.width*scale), round(texture.height*scale)),
                                         Image.Resampling.LANCZOS)
            p = ball.body.position
            image.alpha_composite(texture, (round(p.x-texture.width/2), round(p.y-texture.height/2)))
        effects = Image.new('RGBA', image.size)
        draw = ImageDraw.Draw(effects)
        for event in reversed(sim.events):
            age = sim.time-event.time
            if age > 1.8:
                break
            if event.kind not in {'merge', 'final'}:
                continue
            final = event.kind == 'final'
            duration = 1.65 if final else .56
            if age < 0 or age >= duration:
                continue
            fade = (1-age/duration)**1.5
            color = self.cfg.brands[event.level].color
            radius = self.cfg.brands[event.level].radius
            ring = radius+age*(210 if final else 135)
            draw.ellipse((event.x-ring, event.y-ring, event.x+ring, event.y+ring),
                         outline=(*color, round(145*fade)), width=2 if final else 1)
            rng = random.Random(event.pair[0] if event.pair else round(event.time*10000))
            for _ in range(68 if final else 15+event.level*3):
                angle = rng.uniform(0, math.tau)
                velocity = rng.uniform(130, 500 if final else 260)
                x = event.x+math.cos(angle)*(radius*.45+velocity*age)
                y = event.y+math.sin(angle)*(radius*.45+velocity*age)+170*age*age
                size = rng.uniform(2, 5)*fade
                draw.ellipse((x-size, y-size, x+size, y+size), fill=(*color, round(230*fade)))
        image.alpha_composite(effects)
        if sim.first_final is not None and 0 <= sim.time-sim.first_final < 2.1:
            draw = ImageDraw.Draw(image)
            draw.text((540, 1605), 'FINAL FORM UNLOCKED', font=self.font,
                      fill=(255, 224, 155), anchor='mm', stroke_width=2, stroke_fill=(8, 15, 24))
        image = image.convert('RGB')
        if image.size != (self.cfg.width, self.cfg.height):
            image = image.resize((self.cfg.width, self.cfg.height), Image.Resampling.LANCZOS)
        return image
