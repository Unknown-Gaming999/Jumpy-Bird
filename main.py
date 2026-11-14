
# -*- coding: utf-8 -*-
"""
Jumpy Bird - Made by Mahin
Kivy (Python) game for Android.

Data (coins, best score, owned skins, selected skin, difficulty) is stored with
Kivy JsonStore in the app private storage:
    os.path.join(self.user_data_dir, "jumpy_data.json")
and is saved on every change, on_pause() and on_stop().
"""
import os
import math
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (Color, Rectangle, Ellipse, RoundedRectangle,
                           Triangle, Quad, Line, PushMatrix, PopMatrix,
                           Rotate, Translate)
from kivy.graphics.texture import Texture
from kivy.storage.jsonstore import JsonStore
from kivy.uix.widget import Widget

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
SKINS = [
    ('classic', 'Classic', 0),
    ('blue', 'Blue', 100),
    ('red', 'Red', 300),
    ('golden', 'Golden', 500),
]

SKIN_STYLE = {
    'classic': dict(body=(1.00, 0.84, 0.18), belly=(1.00, 0.96, 0.66),
                    wing=(1.00, 0.62, 0.12), outline=(0.62, 0.40, 0.06)),
    'blue': dict(body=(0.28, 0.64, 1.00), belly=(0.82, 0.94, 1.00),
                 wing=(0.12, 0.38, 0.88), outline=(0.08, 0.24, 0.58)),
    'red': dict(body=(0.95, 0.24, 0.24), belly=(1.00, 0.86, 0.80),
                wing=(0.68, 0.08, 0.14), outline=(0.46, 0.05, 0.09)),
    'golden': dict(body=(1.00, 0.76, 0.10), belly=(1.00, 0.95, 0.55),
                   wing=(0.92, 0.52, 0.04), outline=(0.55, 0.34, 0.00)),
}

DIFFS = {
    'easy': dict(label='Easy', gap=192, speed=140, spacing=255),
    'normal': dict(label='Normal', gap=172, speed=165, spacing=240),
    'hard': dict(label='Hard', gap=152, speed=195, spacing=225),
}
DIFF_ORDER = ['easy', 'normal', 'hard']

GREEN = (0.30, 0.74, 0.24)
ORANGE = (1.00, 0.58, 0.14)
BLUE = (0.22, 0.56, 0.95)
RED = (0.90, 0.26, 0.26)
GOLD = (1.00, 0.80, 0.16)
GREY = (0.45, 0.55, 0.68)

GRAVITY = 1500.0
FLAP_V = 440.0
MAX_FALL = 780.0


def clamp(v, a, b):
    if v < a:
        return a
    if v > b:
        return b
    return v


def ease_out(t):
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def E(x, y, w, h, seg=28):
    return Ellipse(pos=(x, y), size=(w, h), segments=seg)


def R(x, y, w, h):
    return Rectangle(pos=(x, y), size=(w, h))


def RR(x, y, w, h, r):
    return RoundedRectangle(pos=(x, y), size=(w, h), radius=[r])


def make_sky_texture():
    stops = [(0.0, (206, 238, 250)), (0.40, (130, 200, 245)),
             (1.0, (38, 112, 214))]
    rows = 128
    buf = bytearray()
    for i in range(rows):
        f = i / float(rows - 1)
        col = stops[-1][1]
        for k in range(len(stops) - 1):
            if f <= stops[k + 1][0]:
                f0, c0 = stops[k]
                f1, c1 = stops[k + 1]
                tt = (f - f0) / (f1 - f0)
                col = [int(c0[j] + (c1[j] - c0[j]) * tt) for j in range(3)]
                break
        buf.extend([col[0], col[1], col[2], 255])
    tex = Texture.create(size=(1, rows), colorfmt='rgba')
    tex.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
    tex.mag_filter = 'linear'
    tex.min_filter = 'linear'
    tex.wrap = 'clamp_to_edge'
    return tex


# ----------------------------------------------------------------------------
# Game widget
# ----------------------------------------------------------------------------
class Game(Widget):

    def __init__(self, app, **kw):
        super(Game, self).__init__(**kw)
        self.app = app
        self.u = 1.0
        self.gt = 78.0
        self.pw = 66.0
        self.cap_h = 26.0
        self.t = 0.0
        self.state = 'loading'
        self.state_t = 0.0
        self.scroll = 0.0
        self.tex_cache = {}
        self.buttons = []
        self.new_buttons = []
        self.pressed = None

        self.pipes = []
        self.particles = []
        self.floaters = []
        self.bird_y = 300.0
        self.bird_vy = 0.0
        self.bird_angle = 0.0
        self.wing = 0.0
        self.score = 0
        self.score_pop = 0.0
        self.run_coins = 0
        self.new_best = False
        self.shake = 0.0
        self.flash = 0.0
        self.toast = ''
        self.toast_t = 0.0

        self.sky = make_sky_texture()
        rnd = random.Random(7)
        self.clouds = [dict(fx=rnd.random(), fy=rnd.uniform(0.52, 0.93),
                            s=rnd.uniform(0.7, 1.5), v=rnd.uniform(6, 16))
                       for _ in range(7)]
        Clock.schedule_interval(self.tick, 1.0 / 60.0)

    # ------------------------------------------------------------------ utils
    def diff(self):
        return DIFFS[self.app.data['difficulty']]

    def set_state(self, s):
        self.state = s
        self.state_t = 0.0

    def tex(self, s, size):
        size = max(8, int(size))
        key = (s, size)
        t = self.tex_cache.get(key)
        if t is None:
            if len(self.tex_cache) > 300:
                self.tex_cache.clear()
            lab = CoreLabel(text=s, font_size=size, bold=True,
                            color=(1, 1, 1, 1))
            lab.refresh()
            t = lab.texture
            self.tex_cache[key] = t
        return t

    def text(self, s, x, y, size, color=(1, 1, 1, 1), anchor='c',
             outline=None, shadow=True, scale=1.0, alpha=1.0):
        u = self.u
        px_size = size * u
        t = self.tex(s, px_size)
        w, h = t.size
        w *= scale
        h *= scale
        if anchor == 'c':
            px = x - w / 2.0
        elif anchor == 'l':
            px = x
        else:
            px = x - w
        py = y - h / 2.0
        with self.canvas:
            if outline is not None:
                Color(outline[0], outline[1], outline[2], alpha)
                o = max(1.5, px_size * 0.07)
                for dx, dy in ((-o, 0), (o, 0), (0, -o), (0, o),
                               (-o, -o), (o, o), (-o, o), (o, -o)):
                    Rectangle(texture=t, pos=(px + dx, py + dy), size=(w, h))
            elif shadow:
                Color(0, 0, 0, 0.35 * alpha)
                Rectangle(texture=t, pos=(px + 1.5 * u, py - 1.5 * u),
                          size=(w, h))
            Color(color[0], color[1], color[2],
                  (color[3] if len(color) > 3 else 1.0) * alpha)
            Rectangle(texture=t, pos=(px, py), size=(w, h))
        return w

    def reg(self, key, x, y, w, h, enabled=True):
        if enabled:
            self.new_buttons.append((key, x, y, w, h))

    def hit(self, x, y):
        for key, bx, by, bw, bh in reversed(self.buttons):
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return key
        return None

    def button(self, key, x, y, w, h, label, color, size=22, enabled=True):
        u = self.u
        self.reg(key, x, y, w, h, enabled)
        off = 3 * u if (self.pressed == key and enabled) else 0
        if not enabled:
            color = (0.55, 0.55, 0.55)
        r = h * 0.3
        dark = (color[0] * 0.5, color[1] * 0.5, color[2] * 0.5)
        by = y - off
        with self.canvas:
            Color(dark[0], dark[1], dark[2], 1)
            RR(x - 2 * u, y - 6 * u, w + 4 * u, h + 8 * u, r + 2 * u)
            Color(color[0], color[1], color[2], 1)
            RR(x, by, w, h, r)
            Color(1, 1, 1, 0.30)
            RR(x + 4 * u, by + h * 0.52, w - 8 * u, h * 0.40, r * 0.8)
        self.text(label, x + w / 2.0, by + h / 2.0, size,
                  outline=(dark[0] * 0.7, dark[1] * 0.7, dark[2] * 0.7))

    def pill(self, x, y, w, h):
        with self.canvas:
            Color(0, 0, 0, 0.38)
            RR(x, y, w, h, h / 2.0)

    # --------------------------------------------------------------- touches
    def on_touch_down(self, touch):
        self.pressed = None
        key = self.hit(touch.x, touch.y)
        if key:
            self.pressed = key
            return True
        if self.state == 'ready':
            self.start_play()
        elif self.state == 'play':
            self.flap()
        return True

    def on_touch_up(self, touch):
        key = self.hit(touch.x, touch.y)
        if self.pressed and key == self.pressed:
            self.activate(key)
        self.pressed = None
        return True

    def activate(self, key):
        d = self.app.data
        if key == 'play' or key == 'restart':
            self.reset()
        elif key == 'market':
            self.set_state('market')
        elif key == 'back' or key == 'menu':
            self.go_menu()
        elif key.startswith('diff:'):
            d['difficulty'] = key.split(':', 1)[1]
            self.app.save_data()
        elif key.startswith('skin:'):
            self.tap_skin(key.split(':', 1)[1])

    def go_menu(self):
        self.pipes = []
        self.set_state('menu')
        self.app.save_data()

    def tap_skin(self, sid):
        d = self.app.data
        name, price = sid, 0
        for s, n, p in SKINS:
            if s == sid:
                name, price = n, p
        if sid in d['owned']:
            d['skin'] = sid
            self.show_toast('%s skin selected' % name)
        elif d['coins'] >= price:
            d['coins'] -= price
            d['owned'].append(sid)
            d['skin'] = sid
            self.show_toast('%s unlocked!' % name)
        else:
            self.show_toast('Need %d more coins' % (price - d['coins']))
        self.app.save_data()

    def show_toast(self, s):
        self.toast = s
        self.toast_t = 1.6

    # ------------------------------------------------------------ game logic
    def reset(self):
        self.pipes = []
        self.particles = []
        self.floaters = []
        self.score = 0
        self.run_coins = 0
        self.new_best = False
        self.bird_y = self.height * 0.55
        self.bird_vy = 0.0
        self.bird_angle = 0.0
        self.set_state('ready')

    def start_play(self):
        self.set_state('play')
        self.flap()

    def flap(self):
        self.bird_vy = FLAP_V * self.u

    def spawn_pipe(self, x):
        u = self.u
        gap = self.diff()['gap'] * u
        H = self.height
        lo = self.gt + gap / 2.0 + 40 * u
        hi = H - gap / 2.0 - 50 * u
        if hi < lo:
            hi = lo
        if self.pipes:
            base = self.pipes[-1]['gy'] + random.uniform(-190 * u, 190 * u)
        else:
            base = random.uniform(lo, hi)
        gy = clamp(base, lo, hi)
        coin_y = None
        if random.random() < 0.72:
            coin_y = gy + random.uniform(-gap * 0.22, gap * 0.22)
        self.pipes.append(dict(x=x, gy=gy, scored=False,
                               coin_y=coin_y, got=False))

    def burst(self, x, y, color, n=8, speed=160, size=6):
        u = self.u
        for _ in range(n):
            a = random.uniform(0, 6.2832)
            sp = random.uniform(0.4, 1.0) * speed * u
            self.particles.append(dict(
                x=x, y=y, vx=math.cos(a) * sp, vy=math.sin(a) * sp,
                life=1.0, decay=random.uniform(1.4, 2.4),
                size=random.uniform(0.6, 1.0) * size * u, color=color))

    def circ_rect(self, cx, cy, r, rx, ry, rw, rh):
        nx = max(rx, min(cx, rx + rw))
        ny = max(ry, min(cy, ry + rh))
        return (cx - nx) ** 2 + (cy - ny) ** 2 < r * r

    def die(self, pipe_hit):
        if self.state != 'play':
            return
        d = self.app.data
        u = self.u
        self.set_state('dead')
        self.shake = 0.35
        self.flash = 0.55
        self.bird_vy = 140 * u if pipe_hit else 0.0
        self.new_best = self.score > d['best']
        if self.new_best:
            d['best'] = self.score
        sk = SKIN_STYLE.get(d['skin'], SKIN_STYLE['classic'])
        self.burst(self.width * 0.28, self.bird_y, sk['body'], 12, 220, 7)
        self.burst(self.width * 0.28, self.bird_y, (1, 1, 1), 6, 180, 5)
        self.app.save_data()

    def update(self, dt):
        u = self.u
        W, H = self.width, self.height
        self.pw = 66 * u
        self.cap_h = 26 * u
        self.gt = 78 * u
        st = self.state
        d = self.diff()

        if self.toast_t > 0:
            self.toast_t -= dt
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt)
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt * 1.6)
        if self.score_pop > 0:
            self.score_pop = max(0.0, self.score_pop - dt * 4)

        if st == 'loading':
            self.scroll += 30 * u * dt
            self.wing += dt * 16
            if self.state_t > 3.2:
                self.set_state('menu')
        elif st in ('menu', 'market'):
            self.scroll += 40 * u * dt
            self.wing += dt * 16
        elif st == 'ready':
            self.scroll += d['speed'] * u * dt
            self.wing += dt * 16
            self.bird_y = H * 0.55 + math.sin(self.t * 5) * 7 * u
            self.bird_angle = 0.0
        elif st == 'play':
            self.update_play(dt, d)
        elif st == 'dead':
            self.bird_vy -= GRAVITY * u * dt
            self.bird_y += self.bird_vy * dt
            hr = 12 * u
            if self.bird_y <= self.gt + hr:
                self.bird_y = self.gt + hr
                self.bird_vy = 0.0
            self.bird_angle += (-90 - self.bird_angle) * min(1.0, dt * 8)

        for p in self.particles:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] -= 600 * u * dt
            p['life'] -= dt * p['decay']
        self.particles = [p for p in self.particles if p['life'] > 0]
        for f in self.floaters:
            f['y'] += 55 * u * dt
            f['life'] -= dt
        self.floaters = [f for f in self.floaters if f['life'] > 0]

    def update_play(self, dt, d):
        u = self.u
        W, H = self.width, self.height
        spd = d['speed'] * u
        spacing = d['spacing'] * u
        self.scroll += spd * dt
        self.wing += dt * 22

        self.bird_vy -= GRAVITY * u * dt
        if self.bird_vy < -MAX_FALL * u:
            self.bird_vy = -MAX_FALL * u
        self.bird_y += self.bird_vy * dt
        target = clamp(self.bird_vy / (u * 11.0), -70, 28)
        self.bird_angle += (target - self.bird_angle) * min(1.0, dt * 12)

        hr = 12 * u
        bx = W * 0.28
        if self.bird_y > H - hr:
            self.bird_y = H - hr
            if self.bird_vy > 0:
                self.bird_vy = 0.0

        for p in self.pipes:
            p['x'] -= spd * dt
        self.pipes = [p for p in self.pipes if p['x'] + self.pw + 20 * u > 0]

        if not self.pipes:
            self.spawn_pipe(W + 80 * u)
        guard = 0
        while self.pipes[-1]['x'] < W + 40 * u - spacing and guard < 4:
            self.spawn_pipe(self.pipes[-1]['x'] + spacing)
            guard += 1

        gap = d['gap'] * u
        pw = self.pw
        ch = self.cap_h
        coin_r = 13 * u
        for p in self.pipes:
            if not p['scored'] and p['x'] + pw / 2.0 < bx:
                p['scored'] = True
                self.score += 1
                self.score_pop = 1.0

            if p['coin_y'] is not None and not p['got']:
                cx = p['x'] + pw / 2.0
                cy = p['coin_y']
                if (bx - cx) ** 2 + (self.bird_y - cy) ** 2 < \
                        (hr + coin_r + 5 * u) ** 2:
                    p['got'] = True
                    self.app.data['coins'] += 1
                    self.run_coins += 1
                    self.burst(cx, cy, (1.0, 0.88, 0.25), 10, 170, 6)
                    self.floaters.append(dict(x=cx, y=cy + 10 * u,
                                              life=0.9, text='+1'))
                    self.app.save_data()

            if abs(p['x'] + pw / 2.0 - bx) < pw + 30 * u:
                gy = p['gy']
                bot_top = gy - gap / 2.0
                top_bot = gy + gap / 2.0
                hit = False
                hit = hit or self.circ_rect(bx, self.bird_y, hr, p['x'],
                                            self.gt, pw, bot_top - self.gt)
                hit = hit or self.circ_rect(bx, self.bird_y, hr,
                                            p['x'] - 5 * u, bot_top - ch,
                                            pw + 10 * u, ch)
                hit = hit or self.circ_rect(bx, self.bird_y, hr, p['x'],
                                            top_bot, pw, H - top_bot + 50 * u)
                hit = hit or self.circ_rect(bx, self.bird_y, hr,
                                            p['x'] - 5 * u, top_bot,
                                            pw + 10 * u, ch)
                if hit:
                    self.die(True)
                    return

        if self.bird_y - hr <= self.gt:
            self.bird_y = self.gt + hr
            self.die(False)

    def tick(self, dt):
        dt = min(dt, 1.0 / 30.0)
        if self.width < 10 or self.height < 10:
            return
        self.u = min(self.height / 640.0, self.width / 340.0)
        self.t += dt
        self.state_t += dt
        self.update(dt)
        self.draw()

    # --------------------------------------------------------------- drawing
    def draw(self):
        W, H = self.width, self.height
        u = self.u
        self.canvas.clear()
        self.new_buttons = []
        with self.canvas:
            PushMatrix()
            if self.shake > 0:
                s = self.shake * 14 * u
                Translate(random.uniform(-s, s), random.uniform(-s, s))

        self.draw_background()
        st = self.state
        if st == 'loading':
            self.draw_loading()
        elif st == 'menu':
            self.draw_menu()
        elif st == 'market':
            self.draw_market()
        else:
            self.draw_game()
        self.draw_toast()

        with self.canvas:
            PopMatrix()
            if self.flash > 0:
                Color(1, 1, 1, clamp(self.flash, 0, 1) * 0.7)
                R(0, 0, W, H)
        self.buttons = self.new_buttons

    def draw_background(self):
        W, H, u = self.width, self.height, self.u
        gt = self.gt
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.sky, pos=(-40 * u, -40 * u),
                      size=(W + 80 * u, H + 80 * u))
            sx, sy = W * 0.78, H * 0.86
            for rad, al in ((125, 0.05), (95, 0.08), (68, 0.12), (48, 0.20)):
                Color(1.0, 0.95, 0.70, al)
                E(sx - rad * u, sy - rad * u, 2 * rad * u, 2 * rad * u, 36)
            sh = 0.05 + 0.02 * math.sin(self.t * 0.8)
            Color(1.0, 0.97, 0.75, sh)
            for k in range(3):
                a = 90 + k * 120
                Triangle(points=[sx, sy, sx - a * u, gt, sx - (a + 70) * u, gt])
            Color(1.0, 0.92, 0.45, 1)
            E(sx - 30 * u, sy - 30 * u, 60 * u, 60 * u, 36)
            Color(1.0, 0.98, 0.82, 1)
            E(sx - 23 * u, sy - 23 * u, 46 * u, 46 * u, 36)
            Color(1.0, 0.95, 0.60, 0.38)
            for i in range(14):
                a = self.t * 0.15 + i * (6.2832 / 14.0)
                r1 = 38 * u
                r2 = r1 + (14 + 8 * math.sin(self.t * 2 + i)) * u
                Line(points=[sx + math.cos(a) * r1, sy + math.sin(a) * r1,
                             sx + math.cos(a) * r2, sy + math.sin(a) * r2],
                     width=max(1.0, 1.6 * u))

        span = W + 260 * u
        for c in self.clouds:
            x = ((c['fx'] * span + self.t * c['v'] * u) % span) - 130 * u
            self.draw_cloud(x, H * c['fy'], c['s'] * u)

        self.hills(self.scroll * 0.10, 300 * u, 120 * u, gt + 14 * u,
                   (0.56, 0.80, 0.78), (0.64, 0.86, 0.82))
        self.hills(self.scroll * 0.22, 230 * u, 82 * u, gt + 6 * u,
                   (0.38, 0.72, 0.46), (0.48, 0.80, 0.52))
        self.hills(self.scroll * 0.45, 170 * u, 46 * u, gt,
                   (0.27, 0.62, 0.30), (0.36, 0.72, 0.36))

        per = 190 * u
        sx0 = -((self.scroll * 0.7) % per)
        with self.canvas:
            for i in range(-1, int(W / per) + 3):
                x = sx0 + i * per
                Color(0.18, 0.52, 0.22, 1)
                E(x, gt - 4 * u, 38 * u, 28 * u, 20)
                E(x + 22 * u, gt - 4 * u, 34 * u, 22 * u, 20)
                Color(0.30, 0.68, 0.30, 1)
                E(x + 4 * u, gt + 2 * u, 22 * u, 16 * u, 20)

    def draw_cloud(self, x, y, s):
        with self.canvas:
            Color(0.80, 0.88, 0.97, 0.85)
            E(x, y - 4 * s, 92 * s, 34 * s)
            E(x + 18 * s, y + 6 * s, 58 * s, 38 * s)
            E(x + 50 * s, y, 52 * s, 34 * s)
            Color(1, 1, 1, 0.95)
            E(x, y, 92 * s, 34 * s)
            E(x + 18 * s, y + 12 * s, 58 * s, 38 * s)
            E(x + 50 * s, y + 6 * s, 52 * s, 34 * s)

    def hills(self, offset, period, hh, base, col, col2):
        W = self.width
        n = int(W / period) + 3
        sx = -(offset % period)
        with self.canvas:
            for i in range(-1, n):
                x = sx + i * period
                Color(col[0], col[1], col[2], 1)
                E(x - period * 0.25, base - hh, period * 1.5, hh * 2, 40)
                Color(col2[0], col2[1], col2[2], 1)
                E(x + period * 0.50, base - hh * 0.7, period * 1.0,
                  hh * 1.4, 40)
                Color(1, 1, 1, 0.10)
                E(x + period * 0.05, base + hh * 0.30, period * 0.55,
                  hh * 0.5, 24)

    def draw_ground(self):
        W, u, gt = self.width, self.u, self.gt
        per = 28 * u
        off = self.scroll % per
        with self.canvas:
            Color(0.87, 0.73, 0.45, 1)
            R(0, 0, W, gt - 12 * u)
            Color(0.78, 0.62, 0.36, 1)
            R(0, 0, W, (gt - 12 * u) * 0.35)
            Color(0.93, 0.80, 0.52, 1)
            R(0, (gt - 12 * u) * 0.35, W, 3 * u)
            Color(0.30, 0.70, 0.22, 1)
            R(0, gt - 14 * u, W, 14 * u)
            Color(0.20, 0.55, 0.16, 1)
            x = -per - off
            while x < W + per:
                Quad(points=[x, gt - 14 * u, x + per * 0.5, gt - 14 * u,
                             x + per * 0.5 + 8 * u, gt, x + 8 * u, gt])
                x += per
            Color(0.58, 0.88, 0.38, 1)
            R(0, gt - 3 * u, W, 3 * u)
            Color(0, 0, 0, 0.18)
            R(0, gt - 18 * u, W, 4 * u)

    # ----- pipes / coins / bird
    def pipe_body(self, x, y, w, h):
        u = self.u
        if h <= 0:
            return
        with self.canvas:
            Color(0.12, 0.40, 0.10, 1)
            R(x - 1.5 * u, y, w + 3 * u, h)
            Color(0.38, 0.78, 0.22, 1)
            R(x, y, w, h)
            Color(0.64, 0.93, 0.40, 1)
            R(x + w * 0.10, y, w * 0.16, h)
            Color(0.50, 0.86, 0.30, 1)
            R(x + w * 0.26, y, w * 0.12, h)
            Color(0.22, 0.58, 0.14, 1)
            R(x + w * 0.70, y, w * 0.30, h)
            Color(0.16, 0.47, 0.10, 1)
            R(x + w * 0.86, y, w * 0.14, h)

    def pipe_cap(self, x, y, w, h):
        u = self.u
        with self.canvas:
            Color(0.12, 0.40, 0.10, 1)
            RR(x - 1.5 * u, y - 1.5 * u, w + 3 * u, h + 3 * u, 5 * u)
            Color(0.38, 0.78, 0.22, 1)
            RR(x, y, w, h, 4 * u)
            Color(0.64, 0.93, 0.40, 1)
            R(x + w * 0.09, y + 3 * u, w * 0.15, h - 6 * u)
            Color(0.50, 0.86, 0.30, 1)
            R(x + w * 0.24, y + 3 * u, w * 0.10, h - 6 * u)
            Color(0.22, 0.58, 0.14, 1)
            R(x + w * 0.72, y + 3 * u, w * 0.20, h - 6 * u)
            Color(1, 1, 1, 0.18)
            R(x + 3 * u, y + h - 5 * u, w - 6 * u, 2 * u)

    def draw_pipe(self, x, gy, gap):
        u, H, gt = self.u, self.height, self.gt
        pw, ch = self.pw, self.cap_h
        bot_top = gy - gap / 2.0
        top_bot = gy + gap / 2.0
        self.pipe_body(x, gt - 4 * u, pw, bot_top - ch - (gt - 4 * u))
        with self.canvas:
            Color(0, 0, 0, 0.20)
            R(x, bot_top - ch - 9 * u, pw, 9 * u)
        self.pipe_cap(x - 5 * u, bot_top - ch, pw + 10 * u, ch)
        self.pipe_body(x, top_bot + ch, pw, H - (top_bot + ch) + 12 * u)
        with self.canvas:
            Color(0, 0, 0, 0.20)
            R(x, top_bot + ch, pw, 9 * u)
        self.pipe_cap(x - 5 * u, top_bot, pw + 10 * u, ch)

    def draw_coin(self, cx, cy, r, spin=True, ph=0.0):
        k = abs(math.cos(self.t * 3.5 + ph)) if spin else 1.0
        w = max(r * 0.28, r * k)
        with self.canvas:
            if spin:
                Color(1.0, 0.85, 0.2, 0.18)
                E(cx - r * 1.7, cy - r * 1.7, r * 3.4, r * 3.4, 24)
            Color(0.78, 0.48, 0.04, 1)
            E(cx - w, cy - r, 2 * w, 2 * r)
            Color(1.0, 0.82, 0.15, 1)
            E(cx - w * 0.86, cy - r * 0.88, w * 1.72, r * 1.76)
            Color(1.0, 0.92, 0.45, 1)
            E(cx - w * 0.60, cy - r * 0.62, w * 1.2, r * 1.24)
            Color(1.0, 0.78, 0.10, 1)
            E(cx - w * 0.46, cy - r * 0.48, w * 0.92, r * 0.96)
            if k > 0.4:
                Color(1, 1, 1, 0.65)
                E(cx - w * 0.5, cy + r * 0.15, w * 0.35, r * 0.5, 12)

    def draw_bird(self, cx, cy, r, skin, angle=0.0, flap=0.0):
        sk = SKIN_STYLE.get(skin, SKIN_STYLE['classic'])
        bw, bh = 2.3 * r, 2.0 * r
        with self.canvas:
            if skin == 'golden':
                Color(1, 0.9, 0.3, 0.12 + 0.06 * math.sin(self.t * 4))
                E(cx - r * 2.2, cy - r * 2.2, r * 4.4, r * 4.4, 36)
                Color(1, 0.95, 0.5, 0.18)
                E(cx - r * 1.6, cy - r * 1.6, r * 3.2, r * 3.2, 36)
            PushMatrix()
            Rotate(angle=angle, origin=(cx, cy))
            Color(*sk['outline'])
            Triangle(points=[cx - r * 0.7, cy + r * 0.25,
                             cx - r * 1.75, cy + r * 0.65,
                             cx - r * 1.45, cy - r * 0.2])
            Color(*sk['wing'])
            Triangle(points=[cx - r * 0.75, cy + r * 0.2,
                             cx - r * 1.6, cy + r * 0.55,
                             cx - r * 1.35, cy - r * 0.12])
            Color(*sk['outline'])
            E(cx - bw / 2 - 0.1 * r, cy - bh / 2 - 0.1 * r,
              bw + 0.2 * r, bh + 0.2 * r, 36)
            Color(*sk['body'])
            E(cx - bw / 2, cy - bh / 2, bw, bh, 36)
            Color(1, 1, 1, 0.28)
            E(cx - bw * 0.30, cy + bh * 0.14, bw * 0.5, bh * 0.28, 20)
            Color(*sk['belly'])
            E(cx - bw * 0.36, cy - bh * 0.48, bw * 0.78, bh * 0.50, 28)
            wy = cy - r * 0.05 + math.sin(flap) * r * 0.38
            Color(*sk['outline'])
            E(cx - r * 1.02, wy - r * 0.42, r * 1.40, r * 0.88, 24)
            Color(*sk['wing'])
            E(cx - r * 0.95, wy - r * 0.35, r * 1.26, r * 0.74, 24)
            Color(1, 1, 1, 0.22)
            E(cx - r * 0.80, wy - r * 0.05, r * 0.7, r * 0.28, 14)
            ex, ey = cx + r * 0.52, cy + r * 0.30
            Color(*sk['outline'])
            E(ex - r * 0.40, ey - r * 0.40, r * 0.80, r * 0.80, 20)
            Color(1, 1, 1, 1)
            E(ex - r * 0.35, ey - r * 0.35, r * 0.70, r * 0.70, 20)
            Color(0.08, 0.08, 0.1, 1)
            E(ex - r * 0.10, ey - r * 0.20, r * 0.36, r * 0.38, 16)
            Color(1, 1, 1, 1)
            E(ex + r * 0.02, ey + r * 0.02, r * 0.14, r * 0.14, 10)
            Color(1.0, 0.45, 0.45, 0.45)
            E(cx + r * 0.25, cy - r * 0.38, r * 0.5, r * 0.3, 14)
            Color(0.55, 0.22, 0.05, 1)
            Triangle(points=[cx + r * 0.85, cy + r * 0.22,
                             cx + r * 1.72, cy - r * 0.06,
                             cx + r * 0.85, cy - r * 0.12])
            Color(1.0, 0.58, 0.12, 1)
            Triangle(points=[cx + r * 0.88, cy + r * 0.17,
                             cx + r * 1.60, cy - r * 0.05,
                             cx + r * 0.88, cy - r * 0.08])
            Color(0.92, 0.36, 0.10, 1)
            Triangle(points=[cx + r * 0.88, cy - r * 0.10,
                             cx + r * 1.45, cy - r * 0.08,
                             cx + r * 0.88, cy - r * 0.38])
            if skin == 'golden':
                top = cy + bh * 0.5
                Color(0.55, 0.34, 0.0, 1)
                R(cx - r * 0.42, top - r * 0.14, r * 0.95, r * 0.30)
                Color(1.0, 0.86, 0.12, 1)
                R(cx - r * 0.38, top - r * 0.10, r * 0.87, r * 0.22)
                for k in range(3):
                    px = cx - r * 0.38 + k * r * 0.40
                    Color(0.55, 0.34, 0.0, 1)
                    Triangle(points=[px - r * 0.04, top + r * 0.10,
                                     px + r * 0.25, top + r * 0.10,
                                     px + r * 0.10, top + r * 0.52])
                    Color(1.0, 0.86, 0.12, 1)
                    Triangle(points=[px, top + r * 0.12,
                                     px + r * 0.21, top + r * 0.12,
                                     px + r * 0.10, top + r * 0.44])
            PopMatrix()
            if skin == 'golden':
                for k in range(3):
                    a = self.t * 2.0 + k * 2.1
                    sx = cx + math.cos(a) * r * 1.7
                    sy = cy + math.sin(a) * r * 1.4
                    Color(1, 1, 0.8, 0.5 + 0.4 * math.sin(self.t * 6 + k))
                    E(sx - r * 0.10, sy - r * 0.10, r * 0.2, r * 0.2, 10)

    # ----- state drawings
    def draw_title(self, y):
        W, u = self.width, self.u
        bob = math.sin(self.t * 2.2) * 4 * u
        self.text('JUMPY BIRD', W / 2.0, y + bob, 40,
                  color=(1.0, 0.92, 0.30), outline=(0.45, 0.25, 0.05))

    def draw_stats(self, best=False):
        W, H, u = self.width, self.height, self.u
        d = self.app.data
        h = 36 * u
        y = H - 58 * u
        self.pill(12 * u, y, 110 * u, h)
        self.draw_coin(12 * u + 20 * u, y + h / 2.0, 10 * u, spin=False)
        self.text(str(d['coins']), 12 * u + 38 * u, y + h / 2.0, 19,
                  anchor='l', shadow=False)
        if best:
            self.pill(W - 12 * u - 110 * u, y, 110 * u, h)
            self.text('BEST %d' % d['best'], W - 12 * u - 55 * u,
                      y + h / 2.0, 17, shadow=False)

    def draw_toast(self):
        if self.toast_t <= 0:
            return
        W, H, u = self.width, self.height, self.u
        a = clamp(self.toast_t * 3.0, 0, 1)
        w = min(W * 0.84, 290 * u)
        with self.canvas:
            Color(0, 0, 0, 0.72 * a)
            RR(W / 2.0 - w / 2.0, H * 0.5 - 22 * u, w, 44 * u, 22 * u)
        self.text(self.toast, W / 2.0, H * 0.5, 18, alpha=a, shadow=False)

    def draw_loading(self):
        W, H, u = self.width, self.height, self.u
        t = self.state_t
        self.draw_ground()
        self.draw_title(H * 0.76)
        bob = math.sin(self.t * 4) * 10 * u
        self.draw_bird(W / 2.0, H * 0.56 + bob, 34 * u, self.app.data['skin'],
                       angle=math.sin(self.t * 4) * 10, flap=self.t * 18)
        p = clamp(t / 3.0, 0, 1)
        p = ease_out(p) * 0.35 + p * 0.65
        bw = min(W * 0.62, 240 * u)
        bh = 16 * u
        bx = W / 2.0 - bw / 2.0
        by = H * 0.37
        with self.canvas:
            Color(0, 0, 0, 0.30)
            RR(bx - 3 * u, by - 3 * u, bw + 6 * u, bh + 6 * u, (bh + 6 * u) / 2)
            Color(1, 1, 1, 0.35)
            RR(bx, by, bw, bh, bh / 2)
            if p > 0.02:
                Color(0.95, 0.65, 0.10, 1)
                RR(bx, by, max(bh, bw * p), bh, bh / 2)
                Color(1.0, 0.88, 0.30, 1)
                RR(bx + 2 * u, by + bh * 0.45, max(bh - 4 * u, bw * p - 4 * u),
                   bh * 0.45, bh * 0.22)
        dots = '.' * (int(self.t * 3) % 4)
        self.text('Loading' + dots, W / 2.0, by - 26 * u, 18)
        a = clamp((t - 0.3) / 0.7, 0, 1)
        self.text('Made by Mahin', W / 2.0, 38 * u, 28,
                  color=(1.0, 0.92, 0.45), outline=(0.40, 0.22, 0.05),
                  alpha=a, scale=1.0 + 0.03 * math.sin(self.t * 3))

    def draw_menu(self):
        W, H, u = self.width, self.height, self.u
        d = self.app.data
        cx = W / 2.0
        self.draw_ground()
        self.draw_title(H * 0.80)
        bob = math.sin(self.t * 3) * 8 * u
        self.draw_bird(cx, H * 0.645 + bob, 28 * u, d['skin'],
                       angle=math.sin(self.t * 3) * 8, flap=self.t * 16)
        self.draw_stats(best=True)
        bw = min(W * 0.72, 250 * u)
        self.button('play', cx - bw / 2.0, H * 0.465, bw, 62 * u,
                    'PLAY', GREEN, 32)
        self.button('market', cx - bw / 2.0, H * 0.365, bw, 54 * u,
                    'SKIN MARKET', ORANGE, 22)
        self.text('DIFFICULTY', cx, H * 0.285, 15)
        gap = 8 * u
        sw = (bw - 2 * gap) / 3.0
        for i, key in enumerate(DIFF_ORDER):
            sel = (d['difficulty'] == key)
            self.button('diff:' + key, cx - bw / 2.0 + i * (sw + gap),
                        H * 0.20, sw, 40 * u, DIFFS[key]['label'],
                        GOLD if sel else GREY, 16)
        self.text('Made by Mahin', cx, 38 * u, 24,
                  color=(1.0, 0.92, 0.45), outline=(0.40, 0.22, 0.05))

    def draw_market(self):
        W, H, u = self.width, self.height, self.u
        d = self.app.data
        cx = W / 2.0
        self.draw_ground()
        self.draw_stats(best=False)
        self.text('SKIN MARKET', cx, H - 96 * u, 32,
                  color=(1.0, 0.92, 0.30), outline=(0.45, 0.25, 0.05))
        gap = 12 * u
        cw = min((W - 3 * gap) / 2.0, 170 * u)
        ch = 150 * u
        x0 = (W - (2 * cw + gap)) / 2.0
        top = H - 130 * u
        for i, (sid, name, price) in enumerate(SKINS):
            col, row = i % 2, i // 2
            x = x0 + col * (cw + gap)
            y = top - ch - row * (ch + gap)
            sel = (d['skin'] == sid)
            owned = sid in d['owned']
            key = 'skin:' + sid
            self.reg(key, x, y, cw, ch)
            off = 3 * u if self.pressed == key else 0
            y2 = y - off
            with self.canvas:
                Color(0, 0, 0, 0.28)
                RR(x, y - 5 * u, cw, ch, 16 * u)
                if sel:
                    Color(0.25, 0.80, 0.30, 1)
                else:
                    Color(0.55, 0.38, 0.18, 1)
                RR(x - 2 * u, y2 - 2 * u, cw + 4 * u, ch + 4 * u, 17 * u)
                Color(0.99, 0.94, 0.78, 1)
                RR(x, y2, cw, ch, 15 * u)
                Color(1, 1, 1, 0.55)
                RR(x + 4 * u, y2 + ch * 0.55, cw - 8 * u, ch * 0.40, 12 * u)
            self.draw_bird(x + cw / 2.0, y2 + ch - 54 * u, 23 * u, sid,
                           angle=math.sin(self.t * 3 + i) * 6,
                           flap=self.t * 14 + i)
            self.text(name, x + cw / 2.0, y2 + 50 * u, 18,
                      color=(0.40, 0.25, 0.10), shadow=False)
            sh = 28 * u
            sy = y2 + 10 * u
            sw = cw - 24 * u
            with self.canvas:
                if sel:
                    Color(0.25, 0.75, 0.28, 1)
                elif owned:
                    Color(0.25, 0.55, 0.92, 1)
                else:
                    Color(0.98, 0.72, 0.15, 1)
                RR(x + 12 * u, sy, sw, sh, sh / 2.0)
            if sel:
                self.text('SELECTED', x + cw / 2.0, sy + sh / 2.0, 14,
                          shadow=False)
            elif owned:
                self.text('USE', x + cw / 2.0, sy + sh / 2.0, 15,
                          shadow=False)
            elif price == 0:
                self.text('FREE', x + cw / 2.0, sy + sh / 2.0, 15,
                          shadow=False)
            else:
                afford = d['coins'] >= price
                self.draw_coin(x + 30 * u, sy + sh / 2.0, 9 * u, spin=False)
                self.text(str(price), x + 46 * u, sy + sh / 2.0, 16,
                          color=(1, 1, 1) if afford else (0.45, 0.15, 0.10),
                          anchor='l', shadow=False)
        self.button('back', cx - 90 * u, 100 * u, 180 * u, 50 * u,
                    'BACK', BLUE, 22)

    def draw_game(self):
        W, H, u = self.width, self.height, self.u
        d = self.app.data
        gap = self.diff()['gap'] * u
        pw = self.pw
        for p in self.pipes:
            self.draw_pipe(p['x'], p['gy'], gap)
        for i, p in enumerate(self.pipes):
            if p['coin_y'] is not None and not p['got']:
                self.draw_coin(p['x'] + pw / 2.0, p['coin_y'], 13 * u,
                               spin=True, ph=i * 0.9)
        self.draw_ground()

        bx = W * 0.28
        flap = self.wing if self.state != 'dead' else 0.0
        self.draw_bird(bx, self.bird_y, 17 * u, d['skin'],
                       angle=self.bird_angle, flap=flap)

        with self.canvas:
            for p in self.particles:
                c = p['color']
                Color(c[0], c[1], c[2], clamp(p['life'], 0, 1))
                s = p['size']
                E(p['x'] - s / 2.0, p['y'] - s / 2.0, s, s, 12)
        for f in self.floaters:
            self.text(f['text'], f['x'], f['y'], 22,
                      color=(1.0, 0.92, 0.30), outline=(0.45, 0.25, 0.05),
                      alpha=clamp(f['life'] * 2, 0, 1))

        if self.state == 'ready':
            self.draw_stats(best=False)
            pulse = 1.0 + 0.05 * math.sin(self.t * 5)
            self.text('GET READY', W / 2.0, H * 0.76, 40,
                      color=(1.0, 0.92, 0.30), outline=(0.45, 0.25, 0.05),
                      scale=pulse)
            self.text('Tap to fly', W / 2.0, H * 0.70, 22)
        elif self.state == 'play':
            self.draw_stats(best=False)
            sc = 1.0 + 0.30 * self.score_pop
            self.text(str(self.score), W / 2.0, H - 100 * u, 60,
                      outline=(0.10, 0.18, 0.10), scale=sc)
        elif self.state == 'dead':
            self.draw_gameover()

    def draw_gameover(self):
        W, H, u = self.width, self.height, self.u
        d = self.app.data
        tt = (self.state_t - 0.55) / 0.45
        if tt <= 0:
            return
        e = ease_out(tt)
        pw_ = min(W * 0.88, 310 * u)
        ph = 310 * u
        px = W / 2.0 - pw_ / 2.0
        py = H * 0.5 - ph / 2.0 - (1.0 - e) * H * 0.7
        cx = W / 2.0
        with self.canvas:
            Color(0, 0, 0, 0.30 * e)
            RR(px, py - 6 * u, pw_, ph, 22 * u)
            Color(0.45, 0.30, 0.12, 1)
            RR(px - 3 * u, py - 3 * u, pw_ + 6 * u, ph + 6 * u, 24 * u)
            Color(0.98, 0.93, 0.74, 1)
            RR(px, py, pw_, ph, 21 * u)
            Color(1, 1, 1, 0.5)
            RR(px + 5 * u, py + ph * 0.62, pw_ - 10 * u, ph * 0.34, 16 * u)
        brown = (0.55, 0.35, 0.15)
        self.text('GAME OVER', cx, py + ph - 38 * u, 34,
                  color=(1.0, 0.45, 0.25), outline=(0.45, 0.15, 0.05))
        self.text('SCORE', cx, py + ph - 84 * u, 15, color=brown, shadow=False)
        self.text(str(self.score), cx, py + ph - 114 * u, 40,
                  outline=(0.35, 0.22, 0.08))
        self.text('BEST', cx, py + ph - 158 * u, 15, color=brown, shadow=False)
        bw = self.text(str(d['best']), cx, py + ph - 186 * u, 34,
                       outline=(0.35, 0.22, 0.08))
        if self.new_best and self.score > 0:
            s = 1.0 + 0.08 * math.sin(self.t * 8)
            self.text('NEW!', cx + bw / 2.0 + 30 * u, py + ph - 186 * u, 18,
                      color=(1.0, 0.35, 0.25), outline=(1, 1, 1), scale=s)
        if self.run_coins > 0:
            self.draw_coin(cx - 24 * u, py + ph - 224 * u, 11 * u, spin=True)
            self.text('+%d' % self.run_coins, cx - 6 * u, py + ph - 224 * u,
                      22, color=(1.0, 0.85, 0.2), outline=(0.45, 0.25, 0.05),
                      anchor='l')
        if e > 0.9:
            g = 12 * u
            bwid = (pw_ - 3 * g) / 2.0
            self.button('restart', px + g, py + 16 * u, bwid, 52 * u,
                        'RESTART', GREEN, 18)
            self.button('menu', px + 2 * g + bwid, py + 16 * u, bwid, 52 * u,
                        'MAIN MENU', ORANGE, 16)


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
class JumpyBirdApp(App):
    title = 'Jumpy Bird'

    def build(self):
        self.store = None
        self.store_path = os.path.join(self.user_data_dir, "jumpy_data.json")
        self.data = dict(coins=0, best=0, owned=['classic'], skin='classic',
                         difficulty='normal')
        self.load_data()
        Window.bind(on_keyboard=self.on_key)
        self.game = Game(self)
        return self.game

    # ---- persistent data
    def load_data(self):
        try:
            self.store = JsonStore(self.store_path)
        except Exception:
            try:
                os.replace(self.store_path, self.store_path + '.bak')
            except Exception:
                pass
            try:
                self.store = JsonStore(self.store_path)
            except Exception:
                self.store = None
        try:
            if self.store is not None and self.store.exists('player'):
                p = self.store.get('player')
                d = self.data
                d['coins'] = max(0, int(p.get('coins', 0)))
                d['best'] = max(0, int(p.get('best', 0)))
                owned = p.get('owned', ['classic'])
                valid = [s[0] for s in SKINS]
                owned = [s for s in owned if s in valid]
                if 'classic' not in owned:
                    owned.append('classic')
                d['owned'] = owned
                skin = p.get('skin', 'classic')
                d['skin'] = skin if skin in owned else 'classic'
                diff = p.get('difficulty', 'normal')
                d['difficulty'] = diff if diff in DIFFS else 'normal'
        except Exception:
            pass

    def save_data(self):
        if self.store is None:
            return
        try:
            d = self.data
            self.store.put('player', coins=int(d['coins']),
                           best=int(d['best']), owned=list(d['owned']),
                           skin=d['skin'], difficulty=d['difficulty'])
        except Exception as ex:
            print('Save error:', ex)

    # ---- android lifecycle
    def on_pause(self):
        self.save_data()
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        self.save_data()

    # ---- back button
    def on_key(self, window, key, *args):
        if key == 27:
            g = self.game
            if g.state == 'loading':
                return True
            if g.state in ('market', 'ready', 'play', 'dead'):
                g.go_menu()
                return True
            return False
        return False


if __name__ == '__main__':
    JumpyBirdApp().run()
