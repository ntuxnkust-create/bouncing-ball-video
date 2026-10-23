"""An open continuous wall: left rail → bulb → right rail, no inlet lid."""
import hashlib
import json
from pathlib import Path

import pymunk
from PIL import Image, ImageDraw


class GlassGeometry:
    def __init__(self, path):
        self.spec = json.loads(Path(path).read_text())
        left = self.spec['left_inner_wall']
        center = self.spec.get('mirror_center_x', .5)
        if len(left) < 4 or abs(left[-1][0]-center) > 1e-8:
            raise ValueError('Trace must end at the bottom center')
        self.points = [pymunk.Vec2d(x*1080, y*1920) for x, y in left]
        self.points += [pymunk.Vec2d((2*center-x)*1080, y*1920) for x, y in reversed(left[:-1])]
        # Closed only for point-in-polygon queries; never made into a physics lid.
        self.polygon = self.points
        self.segments = list(zip(self.points, self.points[1:]))

    def contains(self, p):
        x, y = p
        inside = False
        previous = self.polygon[-1]
        for current in self.polygon:
            if (current.y > y) != (previous.y > y):
                cross = (previous.x-current.x)*(y-current.y)/(previous.y-current.y)+current.x
                if x < cross:
                    inside = not inside
            previous = current
        return inside

    def closest(self, p):
        p = pymunk.Vec2d(*p)
        best = None
        for a, b in self.segments:
            ab = b-a
            t = max(0, min(1, (p-a).dot(ab)/ab.length_squared))
            q = a + t*ab
            distance = (p-q).length
            if best is None or distance < best[0]:
                # This directed path winds around the left/bottom/right wall.
                normal = pymunk.Vec2d(ab.y, -ab.x).normalized()
                best = (distance, q, normal)
        return best

    def clearance(self, p):
        distance, _, _ = self.closest(p)
        return distance if self.contains(p) else -distance

    def fit(self, p, radius, padding=2):
        """Local inward projection after radius growth, never snap to a circle."""
        p = pymunk.Vec2d(*p)
        for _ in range(12):
            distance, closest, inward = self.closest(p)
            if self.contains(p) and distance >= radius+padding-.02:
                return p
            if self.contains(p):
                inward = (p-closest).normalized() if distance > 1e-6 else inward
            p = closest + inward*(radius+padding)
        if self.clearance(p) < radius-0.2:
            raise RuntimeError('Cannot safely fit merged ball in open glass geometry')
        return p

    def draw_debug(self, background, destination):
        """Separate calibration artifact; never used as the production background."""
        image = load_background(background)
        draw = ImageDraw.Draw(image)
        draw.line([tuple(p) for p in self.points], fill=(255, 70, 135), width=3)
        for p in self.points:
            draw.ellipse((p.x-3, p.y-3, p.x+3, p.y+3), fill='yellow')
        image.save(destination)


def load_background(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f'Original glass PNG missing: {path}. Attach the original as a downloadable file '
            'or use --background /path/to/original.png. No substitute background is generated.')
    with Image.open(path) as source:
        if source.format != 'PNG':
            raise ValueError('The supplied background must be the original PNG')
        image = source.convert('RGB')
    # Contain, never stretch or crop the supplied artwork. Black letterbox only.
    scale = min(1080/image.width, 1920/image.height)
    size = (round(image.width*scale), round(image.height*scale))
    if abs(size[0]/1080-1) > .012 or abs(size[1]/1920-1) > .012:
        raise ValueError('Reference geometry expects the supplied near-9:16 glass PNG; recalibrate for a different aspect ratio')
    canvas = Image.new('RGB', (1080, 1920), 'black')
    canvas.paste(image.resize(size, Image.Resampling.LANCZOS), ((1080-size[0])//2, (1920-size[1])//2))
    return canvas


def background_identity(path):
    return {'filename': Path(path).name, 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
