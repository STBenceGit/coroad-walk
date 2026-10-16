import math
import random
import sys
import time
import pygame
import numpy as np

# ---------- Setup & Constants ----------
T = 48
COLS = 13
VR = 14
W = T * COLS
H = T * VR
NEED = 10
TETHER = 5

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Critter Crossing")
clock = pygame.time.Clock()

ANIMALS = [
    {'id': 'tiger', 'name': 'Tiger', 'body': (240, 146, 43), 'belly': (255, 226, 184), 'snd': 'roar', 'say': 'ROAR!'},
    {'id': 'cat', 'name': 'House Cat', 'body': (154, 160, 166), 'belly': (255, 255, 255), 'snd': 'meow', 'say': 'MEOW!'},
    {'id': 'lion', 'name': 'Lion', 'body': (232, 194, 90), 'belly': (255, 240, 192), 'snd': 'roar2', 'say': 'RAAWR!'},
    {'id': 'dog', 'name': 'Dog', 'body': (176, 113, 63), 'belly': (241, 211, 176), 'snd': 'bark', 'say': 'WOOF!'},
    {'id': 'frog', 'name': 'Frog', 'body': (92, 194, 78), 'belly': (216, 245, 184), 'snd': 'ribbit', 'say': 'RIBBIT!'}
]

PCOL = [(61, 139, 255), (255, 77, 109)]
POWERS = {'up': 'Speed Up', 'down': 'Double Jump', 'left': 'Extra Life'}
DIRS = {'up': (0, 1), 'down': (0, -1), 'left': (-1, 0), 'right': (1, 0)}
KEYS = {
    pygame.K_w: (0, 'up'), pygame.K_s: (0, 'down'), pygame.K_a: (0, 'left'), pygame.K_d: (0, 'right'),
    pygame.K_UP: (1, 'up'), pygame.K_DOWN: (1, 'down'), pygame.K_LEFT: (1, 'left'), pygame.K_RIGHT: (1, 'right')
}

# ---------- Audio Synthesizer ----------
def generate_tone(wave_type, f0, f1, dur, vol, lp=0):
    sr = 44100
    n_samples = int(sr * dur)
    if n_samples <= 0:
        return None
    t = np.linspace(0, dur, n_samples, False)
    
    # Frequency Sweep
    freqs = np.exp(np.linspace(np.log(f0), np.log(f1), n_samples))
    phases = 2 * np.pi * np.cumsum(freqs) / sr
    
    if wave_type == 'sine':
        wave = np.sin(phases)
    elif wave_type == 'square':
        wave = np.sign(np.sin(phases))
    elif wave_type == 'sawtooth':
        wave = 2 * (phases / (2 * np.pi) - np.floor(0.5 + phases / (2 * np.pi)))
    elif wave_type == 'triangle':
        wave = 2 * np.abs(2 * (phases / (2 * np.pi) - np.floor(0.5 + phases / (2 * np.pi)))) - 1
    else:
        wave = np.sin(phases)

    # Simple Lowpass Simulation
    if lp > 0:
        alpha = min(1.0, 2 * np.pi * lp / sr)
        filtered = np.zeros_like(wave)
        last = 0
        for i in range(n_samples):
            last = last + alpha * (wave[i] - last)
            filtered[i] = last
        wave = filtered

    # Envelope
    env = np.ones(n_samples)
    attack = int(sr * 0.03)
    if attack > 0 and attack < n_samples:
        env[:attack] = np.linspace(0.0001, 1.0, attack)
    env[attack:] = np.linspace(1.0, 0.0001, n_samples - attack)
    
    audio = wave * env * vol * 32767
    audio = audio.astype(np.int16)
    stereo = np.column_stack((audio, audio))
    return pygame.sndarray.make_sound(stereo)

def play_tones(sequence):
    for wave_type, f0, f1, dur, vol, delay, lp in sequence:
        snd = generate_tone(wave_type, f0, f1, dur, vol, lp)
        if snd:
            if delay > 0:
                pygame.time.set_timer(pygame.USEREVENT, int(delay * 1000))
            snd.play()

SND = {
    'meow': lambda: play_tones([('triangle', 500, 900, .18, .25, 0, 0), ('triangle', 900, 450, .35, .25, .17, 0)]),
    'roar': lambda: play_tones([('sawtooth', 140, 60, .9, .35, 0, 500), ('sawtooth', 100, 45, .9, .3, .02, 400)]),
    'roar2': lambda: play_tones([('sawtooth', 200, 80, .8, .3, 0, 700), ('square', 150, 70, .8, .15, .03, 500)]),
    'bark': lambda: play_tones([('square', 420, 200, .12, .2, 0, 1500), ('square', 420, 200, .12, .2, .2, 1500)]),
    'ribbit': lambda: play_tones([('square', 160, 320, .1, .2, 0, 900), ('square', 180, 360, .12, .2, .14, 900)]),
    'hop': lambda: play_tones([('sine', 300, 520, .08, .1, 0, 0)]),
    'coin': lambda: play_tones([('square', 880, 880, .06, .1, 0, 0), ('square', 1320, 1320, .1, .1, .06, 0)]),
    'power': lambda: play_tones([('triangle', f, f, .12, .2, i * .1, 0) for i, f in enumerate([523, 659, 784, 1047])]),
    'nope': lambda: play_tones([('sawtooth', 200, 100, .4, .2, 0, 600)]),
    'gate': lambda: play_tones([('triangle', 200, 420, .3, .2, 0, 0)])
}

# ---------- State Variables ----------
state = 'select'
sel = [0, 1]
ready = [False, False]
g = None
bottom = 0
clock_time = 0

# ---------- World Generation Helpers ----------
def rnd(a, b): return a + random.random() * (b - a)
def ri(a, b): return random.randint(a, b)

def mk(row_type, **kwargs):
    d = {'type': row_type, 'trees': set(), 'coins': set()}
    d.update(kwargs)
    return d

def lane(kind, direction, speed, lenR, gapR):
    items = []
    x = rnd(-4, 0)
    total = 0
    while x < COLS + 4:
        length = rnd(*lenR)
        gap = rnd(*gapR)
        items.append({'x': x, 'len': length, 'c': ri(0, 5)})
        x += length + gap
        total += length + gap
    return {'dir': direction, 'speed': speed, 'items': items, 'period': max(total, COLS + 8)}

def push_row(row):
    g['rows'].append(row)
    return len(g['rows']) - 1

def scatter(row, nT, nC, free=None):
    for _ in range(nT):
        c = ri(0, COLS - 1)
        if not free or c not in free:
            row['trees'].add(c)
    for _ in range(nC):
        c = ri(0, COLS - 1)
        if c not in row['trees']:
            row['coins'].add(c)

def add_grass():
    r = mk('grass')
    scatter(r, ri(2, 4), 1 if random.random() < .5 else 0)
    push_row(r)

def gen_section():
    g['sec'] += 1
    if g['sec'] % 4 == 0:
        c0 = ri(1, 7)
        cols = [c0 + 1, c0 + 3]
        span = [c0, c0 + 4]
        plate1 = mk('grass', plates=cols)
        pi1 = push_row(plate1)
        gate1 = {'cols': cols, 'plateRow': pi1, 'openUntil': 0}
        plate1['gate'] = gate1
        g['gates'].append(gate1)
        push_row(mk('fence', gate=gate1))
        
        for _ in range(4):
            b = mk('bridge', span=span)
            scatter(b, 0, 0)
            if random.random() < .6:
                b['coins'].add(ri(c0, c0 + 4))
            push_row(b)
            
        last = mk('bridge', span=span, plates=cols)
        pi2 = push_row(last)
        gate2 = {'cols': cols, 'plateRow': pi2, 'openUntil': 0}
        last['gate'] = gate2
        g['gates'].append(gate2)
        push_row(mk('fence', gate=gate2))
        add_grass()
        return

    k = random.random()
    if k < .3:
        add_grass()
        if random.random() < .5: add_grass()
    elif k < .65:
        n = ri(2, 4)
        d = 1 if random.random() < .5 else -1
        for _ in range(n):
            push_row(mk('road', lane=lane('car', d, rnd(1.6, 4), [1.3, 2.2], [2.5, 6])))
            d = -d
        add_grass()
    else:
        n = ri(2, 3)
        d = 1 if random.random() < .5 else -1
        for _ in range(n):
            push_row(mk('water', lane=lane('log', d, rnd(1, 2.2), [2, 4], [1.2, 2.6])))
            d = -d
        add_grass()

def gen_more():
    while len(g['rows']) < g['maxRow'] + 26:
        gen_section()

# ---------- Game Logic ----------
def start_game():
    global g, state
    g = {
        'rows': [], 'gates': [], 'sec': 0, 'coins': 0, 'lives': 3, 'maxRow': 0, 'cam': 3, 'time': 0, 'state': 'play',
        'power': {'up': 0, 'down': 0}, 'bubbles': [], 'msg': '', 'msgT': 0, 'votes': [None, None], 'phase': '', 'vt': 0, 'shownGate': False,
        'players': [
            {'i': i, 'kind': ANIMALS[sel[i]], 'x': 5.5 + i * 2, 'row': 0, 'fx': 0, 'frow': 0, 'hopT': 1, 'hopping': False,
             'queue': None, 'invuln': 0, 'safe': {'x': 5.5 + i * 2, 'row': 0}} for i in range(2)
        ]
    }
    for _ in range(3): push_row(mk('grass'))
    gen_more()
    state = 'play'
    say('Reach the far side together!')

def say(m):
    g['msg'] = m
    g['msgT'] = 3

def to_select():
    global state, ready
    state = 'select'
    ready = [False, False]

def handle_key(pi, direction):
    if state == 'select':
        if direction in ('left', 'right'):
            ready[pi] = False
            sel[pi] = (sel[pi] + (-1 if direction == 'left' else 1) + len(ANIMALS)) % len(ANIMALS)
        elif direction == 'up':
            ready[pi] = (sel[0] != sel[1])
        else:
            ready[pi] = False
        if ready[0] and ready[1] and sel[0] != sel[1]:
            start_game()
    elif state == 'play':
        if g['state'] == 'play':
            g['players'][pi]['queue'] = direction
            try_move(g['players'][pi])
        elif g['state'] == 'vote' and g['phase'] == 'choose' and direction in POWERS and g['votes'][pi] is None:
            g['votes'][pi] = direction
            SND['hop']()
            if g['votes'][0] and g['votes'][1]:
                g['phase'] = 'reveal'
                g['vt'] = 2

def col_of(x): return math.floor(x)

def blocked(row, x):
    c = col_of(x)
    if c in row['trees']: return True
    if row['type'] == 'fence':
        return not (c in row['gate']['cols'] and g['time'] < row['gate']['openUntil'])
    return False

def can_enter(p, nx, nr, dy, steps, other):
    if nr < 0 or nr < math.floor(g['cam'] - 5): return False
    if nx < 0.5 or nx > COLS - 0.5: return False
    if dy > 0 and nr - other['row'] > TETHER:
        say('Wait for your partner!')
        return False
    if nr >= len(g['rows']): return False
    row = g['rows'][nr]
    if steps == 2 and dy != 0 and g['rows'][p['row'] + dy]['type'] == 'fence': return False
    return not blocked(row, nx)

def try_move(p):
    if p['hopping'] or not p['queue'] or g['state'] != 'play': return
    dx, dy = DIRS[p['queue']]
    p['queue'] = None
    other = g['players'][1 - p['i']]
    steps_list = [2, 1] if g['power']['down'] > 0 else [1]
    
    for s in steps_list:
        nr = p['row'] + dy * s
        nx = p['x'] + dx * s
        if 0 <= nr < len(g['rows']):
            row = g['rows'][nr]
            if row['type'] != 'water': nx = col_of(nx) + 0.5
            if can_enter(p, nx, nr, dy, s, other):
                p['fx'] = p['x']
                p['frow'] = p['row']
                p['x'] = nx
                p['row'] = nr
                p['hopping'] = True
                p['hopT'] = 0
                SND['hop']()
                return

def eff_row(p): return p['frow'] if (p['hopping'] and p['hopT'] < 0.5) else p['row']
def eff_x(p): return p['fx'] if (p['hopping'] and p['hopT'] < 0.5) else p['x']

def hit(p):
    global state
    if p['invuln'] > 0 or g['state'] != 'play': return
    SND[p['kind']['snd']]()
    g['lives'] -= 1
    g['bubbles'].append({'x': p['x'], 'row': p['row'], 'text': p['kind']['say'], 't': 1.3})
    p['invuln'] = 2
    p['hopping'] = False
    p['hopT'] = 1
    p['queue'] = None
    p['x'] = p['safe']['x']
    p['row'] = p['safe']['row']
    if g['lives'] <= 0:
        state = 'over'

def land(p):
    p['hopping'] = False
    row = g['rows'][p['row']]
    c = col_of(p['x'])
    if c in row['coins']:
        row['coins'].remove(c)
        SND['coin']()
        g['coins'] += 1
        if g['coins'] >= NEED:
            g['state'] = 'vote'
            g['phase'] = 'choose'
            g['votes'] = [None, None]
            
    if p['row'] > g['maxRow']:
        g['maxRow'] = p['row']
        gen_more()
        
    if row['type'] == 'grass' or (row['type'] == 'bridge' and row['span'][0] <= c <= row['span'][1]):
        p['safe'] = {'x': col_of(p['x']) + 0.5, 'row': p['row']}
    if row['type'] == 'bridge' and (c < row['span'][0] or c > row['span'][1]):
        hit(p)
    if not g['shownGate'] and row['type'] == 'grass' and any(0 <= q['plateRow'] - p['row'] < 6 for q in g['gates']):
        g['shownGate'] = True
        say('Gate ahead: stand on a plate each to open it!')

def resolve_vote():
    a, b = g['votes']
    if a == b:
        SND['power']()
        if a == 'left': g['lives'] += 1
        else: g['power'][a] = 20
        say(POWERS[a] + ' activated!')
    else:
        SND['nope']()
        say('Different picks - no power-up!')
    g['coins'] = 0
    g['state'] = 'play'

def update(dt):
    if state != 'play': return
    if g['state'] == 'vote':
        if g['phase'] == 'reveal':
            g['vt'] -= dt
            if g['vt'] <= 0: resolve_vote()
        return

    g['time'] += dt
    if g['msgT'] > 0: g['msgT'] -= dt
    g['power']['up'] = max(0, g['power']['up'] - dt)
    g['power']['down'] = max(0, g['power']['down'] - dt)
    
    lo = g['cam'] - 8
    hi = g['cam'] + 24
    
    for r, row in enumerate(g['rows']):
        if 'lane' not in row or r < lo or r > hi: continue
        L = row['lane']
        for it in L['items']:
            it['x'] += L['dir'] * L['speed'] * dt
            if L['dir'] > 0 and it['x'] > COLS + 4: it['x'] -= L['period']
            if L['dir'] < 0 and it['x'] + it['len'] < -4: it['x'] += L['period']

    for q in g['gates']:
        on = [col_of(p['x']) for p in g['players'] if not p['hopping'] and p['row'] == q['plateRow'] and col_of(p['x']) in q['cols']]
        if len(on) == 2 and on[0] != on[1]:
            if g['time'] >= q['openUntil']: SND['gate']()
            q['openUntil'] = g['time'] + 5

    dur = 0.08 if g['power']['up'] > 0 else 0.14
    for p in g['players']:
        p['invuln'] = max(0, p['invuln'] - dt)
        if p['hopping']:
            p['hopT'] += dt / dur
            if p['hopT'] >= 1:
                p['hopT'] = 1
                land(p)
                if state != 'play': return

        row = g['rows'][eff_row(p)]
        px = eff_x(p)
        if row['type'] == 'road':
            for c in row['lane']['items']:
                if px + 0.3 > c['x'] + 0.05 and px - 0.3 < c['x'] + c['len'] - 0.05:
                    hit(p)
        if not p['hopping'] and row['type'] == 'water':
            log = next((l for l in row['lane']['items'] if l['x'] <= p['x'] <= l['x'] + l['len']), None)
            if log:
                p['x'] += row['lane']['dir'] * row['lane']['speed'] * dt
            else:
                hit(p)
            if p['x'] < 0 or p['x'] > COLS: hit(p)
        if not p['hopping']:
            try_move(p)

    if state != 'play': return
    target = (g['players'][0]['row'] + g['players'][1]['row']) / 2
    g['cam'] += (target - g['cam']) * min(1.0, dt * 5)
    
    for b in g['bubbles']: b['t'] -= dt
    g['bubbles'] = [b for b in g['bubbles'] if b['t'] > 0]

# ---------- Drawing Helpers ----------
def row_y(r): return H - (r - bottom + 1) * T

def draw_text(s, x, y, size, col=(255, 255, 255), align='center', stroke=True):
    font = pygame.font.SysFont('sans-serif', int(size), bold=True)
    surf = font.render(s, True, col)
    rect = surf.get_rect()
    
    if align == 'center': rect.center = (x, y)
    elif align == 'left': rect.midleft = (x, y)
    elif align == 'right': rect.midright = (x, y)

    if stroke:
        stroke_surf = font.render(s, True, (0, 0, 0))
        for dx, dy in [(-2,0), (2,0), (0,-2), (0,2)]:
            s_rect = stroke_surf.get_rect(center=(rect.centerx + dx, rect.centery + dy))
            screen.blit(stroke_surf, s_rect)
            
    screen.blit(surf, rect)

def draw_tree(c, y):
    pygame.draw.rect(screen, (122, 74, 34), (c * T + 20, y + 28, 8, 16))
    pygame.draw.circle(screen, (47, 143, 58), (c * T + 24, y + 22), 17)
    pygame.draw.circle(screen, (63, 174, 74), (c * T + 19, y + 17), 8)

def draw_row(row, r):
    y = row_y(r)
    if row['type'] == 'road':
        pygame.draw.rect(screen, (75, 79, 88), (0, y, W, T))
        if r + 1 < len(g['rows']) and g['rows'][r + 1]['type'] == 'road':
            for x in range(0, W, 40):
                pygame.draw.rect(screen, (231, 226, 192), (x + 6, y - 2, 24, 4))
    elif row['type'] in ('water', 'bridge'):
        pygame.draw.rect(screen, (58, 165, 230), (0, y, W, T))
        for i in range(6):
            wx = ((i * 107 + r * 31 + int(clock_time * 12)) % (W + 20)) - 10
            wy = y + 12 + (i % 3) * 10
            s = pygame.Surface((18, 3), pygame.SRCALPHA)
            s.fill((255, 255, 255, 64))
            screen.blit(s, (wx, wy))
        if row['type'] == 'bridge':
            x0 = row['span'][0] * T
            w = (row['span'][1] - row['span'][0] + 1) * T
            pygame.draw.rect(screen, (185, 130, 74), (x0, y, w, T))
            for x in range(int(x0), int(x0 + w), 16):
                pygame.draw.rect(screen, (138, 90, 43), (x, y, 2, T))
            pygame.draw.rect(screen, (138, 90, 43), (x0, y, w, 4))
            pygame.draw.rect(screen, (138, 90, 43), (x0, y + T - 4, w, 4))
    else:
        col = (124, 207, 90) if r % 2 else (114, 196, 80)
        pygame.draw.rect(screen, col, (0, y, W, T))

    if 'plates' in row:
        for c in row['plates']:
            q = row['gate']
            is_open = g['time'] < q['openUntil']
            color = (88, 224, 122) if is_open else (255, 210, 74)
            pygame.draw.circle(screen, color, (c * T + 24, y + 24), 17)
            pygame.draw.circle(screen, (122, 90, 16), (c * T + 24, y + 24), 17, 3)

    if row['type'] == 'fence':
        q = row['gate']
        is_open = g['time'] < q['openUntil']
        for c in range(COLS):
            if c in q['cols']:
                pygame.draw.rect(screen, (90, 58, 26), (c * T, y + 6, 6, 36))
                pygame.draw.rect(screen, (90, 58, 26), (c * T + 42, y + 6, 6, 36))
                if not is_open:
                    pygame.draw.rect(screen, (192, 57, 43), (c * T + 6, y + 12, 36, 6))
                    pygame.draw.rect(screen, (192, 57, 43), (c * T + 6, y + 28, 36, 6))
            else:
                pygame.draw.rect(screen, (165, 115, 47), (c * T, y + 14, T, 6))
                pygame.draw.rect(screen, (165, 115, 47), (c * T, y + 30, T, 6))
                pygame.draw.rect(screen, (122, 74, 34), (c * T + 4, y + 6, 8, 36))
                pygame.draw.rect(screen, (122, 74, 34), (c * T + 36, y + 6, 8, 36))

    for c in row['trees']: draw_tree(c, y)
    for c in row['coins']:
        b = math.sin(clock_time * 5 + c) * 3
        rect = pygame.Rect(c * T + 15, y + 13 + b, 18, 22)
        pygame.draw.ellipse(screen, (255, 207, 51), rect)
        pygame.draw.ellipse(screen, (184, 134, 11), rect, 2)

    if 'lane' in row:
        for it in row['lane']['items']:
            x = it['x'] * T
            w = it['len'] * T
            if row['type'] == 'road':
                colors = [(231, 76, 60), (241, 196, 15), (155, 89, 182), (236, 240, 241), (26, 188, 156), (230, 126, 34)]
                pygame.draw.rect(screen, colors[it['c']], (x, y + 8, w, 32), border_radius=7)
                wx = x + w * 0.55 if row['lane']['dir'] > 0 else x + w * 0.1
                s = pygame.Surface((w * 0.35, 24), pygame.SRCALPHA)
                s.fill((30, 40, 60, 190))
                screen.blit(s, (wx, y + 12))
            else:
                pygame.draw.rect(screen, (141, 90, 43), (x, y + 8, w, 32), border_radius=14)
                pygame.draw.rect(screen, (168, 113, 58), (x + 4, y + 12, w - 8, 8), border_radius=4)

def draw_animal_surface(k, tag=None):
    surf = pygame.Surface((60, 80), pygame.SRCALPHA)
    cx, cy = 30, 40
    
    def o(x, y, rx, ry, col):
        rect = pygame.Rect(cx + x - rx, cy + y - ry, rx * 2, ry * 2)
        pygame.draw.ellipse(surf, col, rect)
        
    def tri(a, b, c, col):
        pts = [(cx + a[0], cy + a[1]), (cx + b[0], cy + b[1]), (cx + c[0], cy + c[1])]
        pygame.draw.polygon(surf, col, pts)

    dark = (43, 32, 24)
    if k['id'] == 'lion': o(0, -8, 20, 20, (168, 102, 31))
    if k['id'] == 'dog':
        o(-15, -9, 6, 11, (107, 63, 28))
        o(15, -9, 6, 11, (107, 63, 28))

    pygame.draw.rect(surf, k['body'], (cx - 15, cy - 4, 30, 22), border_radius=8)
    o(0, 10, 9, 7, k['belly'])
    o(-10, 17, 6, 3.5, k['body'])
    o(10, 17, 6, 3.5, k['body'])
    o(0, -9, 14, 13, k['body'])

    if k['id'] in ('tiger', 'cat'):
        for s in [-1, 1]: tri([s * 13, -15], [s * 11, -30], [s * 3, -21], k['body'])
    if k['id'] == 'tiger':
        for x in [-4, 0, 4]: pygame.draw.rect(surf, dark, (cx + x - 1, cy - 21, 2, 6))
        pygame.draw.rect(surf, dark, (cx - 15, cy + 2, 7, 3))
        pygame.draw.rect(surf, dark, (cx + 8, cy + 2, 7, 3))
        pygame.draw.rect(surf, dark, (cx - 15, cy + 9, 7, 3))
        pygame.draw.rect(surf, dark, (cx + 8, cy + 9, 7, 3))
        o(0, -3, 7, 5, k['belly'])
    if k['id'] == 'cat':
        for s in [-1, 1]:
            pygame.draw.line(surf, (85, 85, 85), (cx + s * 5, cy - 4), (cx + s * 17, cy - 6))
            pygame.draw.line(surf, (85, 85, 85), (cx + s * 5, cy - 3), (cx + s * 17, cy - 1))
        o(0, -3, 6, 4.5, k['belly'])
    if k['id'] == 'lion':
        o(-12, -20, 5, 5, k['body'])
        o(12, -20, 5, 5, k['body'])
        o(0, -9, 12, 11, k['body'])
        o(0, -3, 6, 5, k['belly'])
    if k['id'] == 'dog': o(0, -3, 7, 5, k['belly'])
    if k['id'] == 'frog':
        o(-8, -21, 6, 6, k['body'])
        o(8, -21, 6, 6, k['body'])
        o(-8, -21, 3.5, 3.5, (255, 255, 255))
        o(8, -21, 3.5, 3.5, (255, 255, 255))
        o(-8, -21, 1.8, 1.8, dark)
        o(8, -21, 1.8, 1.8, dark)
        pygame.draw.arc(surf, dark, (cx - 8, cy - 14, 16, 16), 0.2, math.pi - 0.2, 2)
    else:
        o(-5, -10, 3.6, 3.6, (255, 255, 255))
        o(5, -10, 3.6, 3.6, (255, 255, 255))
        o(-5, -10, 1.8, 1.8, dark)
        o(5, -10, 1.8, 1.8, dark)
        o(0, -6, 2.6, 2, (217, 106, 122))

    if tag: tri([-6, -35], [6, -35], [0, -29], tag)
    return surf

def draw_player(p):
    if p['invuln'] > 0 and int(clock_time * 12) % 2: return
    t = p['hopT']
    vx = p['fx'] + (p['x'] - p['fx']) * t
    vr = p['frow'] + (p['row'] - p['frow']) * t
    lift = math.sin(math.pi * t) * T * 0.45 if p['hopping'] else math.sin(clock_time * 4 + p['i']) * 1.2
    sx = vx * T if p['hopping'] else p['x'] * T
    sy = row_y(vr if p['hopping'] else p['row']) + T / 2 - lift

    shadow = pygame.Surface((28, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 64), (0, 0, max(2, 28 - lift / 3), 10))
    screen.blit(shadow, shadow.get_rect(center=(sx, row_y(vr if p['hopping'] else p['row']) + 40)))

    anim_surf = draw_animal_surface(p['kind'], PCOL[p['i']])
    anim_surf = pygame.transform.smoothscale(anim_surf, (int(60 * 0.85), int(80 * 0.85)))
    rect = anim_surf.get_rect(center=(sx, sy))
    screen.blit(anim_surf, rect)

def hud():
    s = pygame.Surface((W, 34), pygame.SRCALPHA)
    s.fill((0, 0, 0, 115))
    screen.blit(s, (0, 0))
    
    lives_cnt = min(g['lives'], 8)
    draw_text('♥' * lives_cnt + ('+' if g['lives'] > 8 else ''), 10, 17, 18, (255, 107, 129), 'left')
    
    pygame.draw.rect(screen, (255, 255, 255, 64), (W / 2 - 80, 10, 160, 14))
    pygame.draw.rect(screen, (255, 207, 51), (W / 2 - 80, 10, 160 * g['coins'] / NEED, 14))
    draw_text(f"{g['coins']}/{NEED}", W / 2, 17, 12)
    draw_text(f"Distance {g['maxRow']}", W - 10, 17, 16, align='right')

    y = 50
    if g['power']['up'] > 0:
        draw_text(f"Speed Up {math.ceil(g['power']['up'])}s", 10, y, 14, (125, 255, 176), 'left')
        y += 18
    if g['power']['down'] > 0:
        draw_text(f"Double Jump {math.ceil(g['power']['down'])}s", 10, y, 14, (125, 208, 255), 'left')

    if g['msgT'] > 0:
        draw_text(g['msg'], W / 2, 70, 18)

def draw_vote():
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 184))
    screen.blit(overlay, (0, 0))
    
    draw_text('POWER-UP TIME', W / 2, 110, 34, (255, 207, 51))
    draw_text('Both players press the SAME key to claim it', W / 2, 150, 17)

    opts = [['up', '↑', 'Speed Up'], ['down', '↓', 'Double Jump'], ['left', '←', 'Extra Life']]
    for i, (d, sym, name) in enumerate(opts):
        x = 60 + i * 180
        picked = [j for j, v in enumerate(g['votes']) if v == d] if g['phase'] == 'reveal' else []
        bg_col = (255, 207, 51, 64) if len(picked) > 0 else (255, 255, 255, 30)
        
        box = pygame.Surface((160, 150), pygame.SRCALPHA)
        pygame.draw.rect(box, bg_col, (0, 0, 160, 150), border_radius=14)
        screen.blit(box, (x, 190))

        draw_text(sym, x + 80, 240, 46)
        draw_text(name, x + 80, 295, 18)
        
        for n, j in enumerate(picked):
            offset = 28 if n else -28 * (len(picked) - 1)
            draw_text(f"P{j + 1}", x + 80 + offset, 322, 15, PCOL[j])

    for i in range(2):
        keys = '↑ ↓ ←' if i else 'W S A'
        v = g['votes'][i]
        status = 'locked in ✓' if v else 'choosing...'
        draw_text(f"P{i + 1} ({keys}): {status}", W / 2, 390 + i * 30, 20, PCOL[i])

    if g['phase'] == 'reveal':
        match = g['votes'][0] == g['votes'][1]
        col = (125, 255, 176) if match else (255, 138, 138)
        draw_text('MATCH!' if match else 'No match - no power-up', W / 2, 480, 30, col)

def draw_select():
    for y_pos in range(H):
        interp = y_pos / H
        r = int(44 * (1 - interp) + 22 * interp)
        g_col = int(94 * (1 - interp) + 48 * interp)
        b = int(58 * (1 - interp) + 31 * interp)
        pygame.draw.line(screen, (r, g_col, b), (0, y_pos), (W, y_pos))

    draw_text('CRITTER CROSSING', W / 2, 70, 40, (255, 207, 51))
    draw_text('2-player co-op hopper', W / 2, 105, 16)

    for i, a in enumerate(ANIMALS):
        x, y = 14 + i * 120, 160
        box = pygame.Surface((108, 150), pygame.SRCALPHA)
        box.fill((255, 255, 255, 25))
        screen.blit(box, (x, y))

        for p in range(2):
            if sel[p] == i:
                pygame.draw.rect(screen, PCOL[p], (x + 2 + p * 4, y + 2 + p * 4, 104 - p * 8, 146 - p * 8), 4, border_radius=10)
                status = ' ✓' if ready[p] else ''
                draw_text(f"P{p + 1}{status}", x + 30 + p * 48, y + 168, 15, PCOL[p])

        anim_surf = draw_animal_surface(a)
        anim_surf = pygame.transform.smoothscale(anim_surf, (int(60 * 1.5), int(80 * 1.5)))
        screen.blit(anim_surf, anim_surf.get_rect(center=(x + 54, y + 85)))
        draw_text(a['name'], x + 54, y + 130, 14)

    lines = [
        'P1: A / D pick, W ready      P2: ← / → pick, ↑ ready',
        'Pick two different animals', '',
        'Hop over roads, logs and bridges. Gates need BOTH of you:',
        'stand on one plate each.', '',
        'Every 10 coins: vote with the SAME key',
        '↑ Speed Up    ↓ Double Jump    ← Extra Life',
        'Different keys = no power-up'
    ]
    for i, l in enumerate(lines):
        draw_text(l, W / 2, 400 + i * 26, 16, (232, 245, 224), stroke=False)

def render():
    screen.fill((0, 0, 0))
    if state == 'select':
        draw_select()
        pygame.display.flip()
        return

    global bottom
    bottom = g['cam'] - 5.5
    min_r = max(0, math.floor(bottom) - 1)
    max_r = min(len(g['rows']), math.floor(bottom + VR + 2))
    
    for r in range(min_r, max_r):
        draw_row(g['rows'][r], r)

    sorted_players = sorted(g['players'], key=lambda p: p['row'], reverse=True)
    for p in sorted_players:
        draw_player(p)

    for b in g['bubbles']:
        bx = b['x'] * T
        by = row_y(b['row']) - 20 - (1.3 - b['t']) * 25
        draw_text(b['text'], bx, by, 22, (255, 240, 77))

    hud()

    if g['state'] == 'vote':
        draw_vote()

    if state == 'over':
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 178))
        screen.blit(overlay, (0, 0))
        draw_text('GAME OVER', W / 2, 250, 44, (255, 107, 129))
        draw_text(f"Distance {g['maxRow']}", W / 2, 310, 24)
        draw_text('Press Enter or Space to play again', W / 2, 360, 18)

    pygame.display.flip()

# ---------- Main Loop ----------
last_time = time.time()
running = True

while running:
    now = time.time()
    dt = min(0.05, now - last_time)
    last_time = now
    clock_time += dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE) and state == 'over':
                to_select()
            elif event.key in KEYS:
                pi, direction = KEYS[event.key]
                handle_key(pi, direction)

    update(dt)
    render()
    clock.tick(60)

pygame.quit()
sys.exit()
