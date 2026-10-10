"""60s cinematic music bed v2 — story-driven. Pure stdlib (no numpy).
Arc: dark tension 0-20 (Am), emerald SAVE swell 20-28 (F lift), calm hope 28-38,
bridge 38-44 (C), punchy product 44-55 (G), outro swell 55-60 (Am).
Accents: 0.0 sub hit, 3.0 pulse in, 19.5 riser -> 20.0 THE SAVE boom,
28.0 soft bell, 37.8 riser -> 38.0 bridge, 44.0 product kick, 55.0 final hit.
"""
import math, wave, array, os, random

SR = 44100
DUR = 60.0
N = int(SR * DUR)
BPM = 96.0
BEAT = 60.0 / BPM  # 0.625s
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.wav")

L = array.array("f", [0.0] * N)
R = array.array("f", [0.0] * N)

def env(t, attack, hold, release, total):
    if t < 0 or t > total: return 0.0
    if t < attack: return t / attack if attack > 0 else 1.0
    if t < attack + hold: return 1.0
    rt = t - attack - hold
    if rt < release: return 1.0 - rt / release
    return 0.0

def add(i, l, r):
    if 0 <= i < N:
        L[i] += l
        R[i] += r

def nt(name):
    base = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}
    p = base[name[0]]
    o = int(name[-1])
    if "#" in name: p += 1
    midi = (o + 1) * 12 + p
    return 440.0 * (2 ** ((midi - 69) / 12))

# ---- chord plan (start, end, pad voicing, root for sub) ----
CHORDS = [
    (3.0,  20.0, [nt("A2"), nt("C3"), nt("E3"), nt("A3")], nt("A1")),   # Am — tension
    (20.0, 28.0, [nt("F2"), nt("A2"), nt("C3"), nt("F3")], nt("F1")),   # F — the save, lift
    (28.0, 38.0, [nt("C3"), nt("E3"), nt("G3"), nt("C4")], nt("C2")),   # C — calm hope
    (38.0, 44.0, [nt("A2"), nt("C3"), nt("E3"), nt("A3")], nt("A1")),   # Am — bridge tension
    (44.0, 55.0, [nt("G2"), nt("B2"), nt("D3"), nt("G3")], nt("G1")),   # G — product punch
    (55.0, 60.0, [nt("A2"), nt("C3"), nt("E3"), nt("A3")], nt("A1")),   # Am — outro
]

# ---- pad ----
for (s, e, freqs, _root) in CHORDS:
    total = e - s
    for f_i, f in enumerate(freqs):
        det = 1.0 + (0.0015 * (f_i % 2 * 2 - 1))
        pan = -0.4 + 0.27 * f_i
        gl = math.sqrt((1 - pan) / 2) * (0.9 if f_i % 2 == 0 else 0.6)
        gr = math.sqrt((1 + pan) / 2) * (0.9 if f_i % 2 == 0 else 0.6)
        i0 = int(s * SR)
        i1 = min(N, int(e * SR))
        w = 2 * math.pi * f / SR
        wd = 2 * math.pi * f * det / SR
        for i in range(i0, i1):
            t = (i - i0) / SR
            a = env(t, 1.0, max(0.0, total - 2.0), 1.0, total)
            v = (math.sin(w * i) + math.sin(wd * i)) * 0.5 * a * 0.05
            add(i, v * gl, v * gr)

# ---- sub bass ----
for (s, e, _freqs, root) in CHORDS:
    i0, i1 = int(s * SR), min(N, int(e * SR))
    w = 2 * math.pi * root / SR
    for i in range(i0, i1):
        t = (i - i0) / SR
        a = env(t, 0.6, max(0.0, (e - s) - 1.2), 0.6, e - s)
        v = math.sin(w * i) * a * 0.08
        add(i, v, v)

# ---- heartbeat pulse during tension (0.5-20s): soft low thud every beat ----
def pulse(i0, gain):
    for k in range(int(0.12 * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        f = 90 * math.exp(-tt * 20) + 50
        ph = 2 * math.pi * (50 * tt + (90 - 50) * (1 - math.exp(-tt * 20)) / 20)
        v = math.sin(ph) * math.exp(-tt * 18) * gain
        add(i, v, v)

t = 0.5
while t < 20.0:
    # denser as it approaches the save
    g = 0.12 + 0.15 * (t / 20.0)
    pulse(int(t * SR), g)
    t += BEAT

# ---- tension ticks (12-20s): high noise blips like a clock ----
random.seed(11)
t = 12.0
while t < 20.0:
    i0 = int(t * SR)
    for k in range(int(0.02 * SR)):
        i = i0 + k
        if i >= N: break
        v = (random.random() * 2 - 1) * math.exp(-k / SR * 200) * 0.03
        add(i, v * 0.7, v)
    t += BEAT / 2

# ---- kick from 38s (product section) ----
def kick(i0):
    for k in range(int(0.18 * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        ph = 2 * math.pi * (45 * tt + (120 - 45) * (1 - math.exp(-tt * 18)) / 18)
        v = math.sin(ph) * math.exp(-tt * 16) * 0.45
        add(i, v, v)

t = 38.0
while t < 55.0:
    kick(int(t * SR))
    t += BEAT * (1 if t < 44.0 else 1.5)

# ---- hats 44-55 ----
t = 44.0
hi = 0
while t < 55.0:
    i0 = int(t * SR)
    pan = 0.35 if hi % 2 == 0 else -0.35
    gl, gr = math.sqrt((1 - pan) / 2), math.sqrt((1 + pan) / 2)
    for k in range(int(0.03 * SR)):
        i = i0 + k
        if i >= N: break
        v = (random.random() * 2 - 1) * math.exp(-k / SR * 120) * 0.03
        add(i, v * gl, v * gr)
    hi += 1
    t += BEAT / 2

# ---- arp plucks 44-55 ----
def pluck(i0, f, gain):
    for k in range(int(0.22 * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        v = math.tanh(math.sin(2 * math.pi * f * tt) * 1.4) * math.exp(-tt * 14) * gain
        add(i, v * 0.85, v)

def chord_at(t):
    for (s, e, freqs, _r) in CHORDS:
        if s <= t < e: return freqs
    return CHORDS[-1][2]

t = 44.0
ai = 0
while t < 55.0:
    freqs = chord_at(t)
    f = freqs[(ai % 3) + 1]
    pluck(int(t * SR), f * (2 if ai % 8 == 7 else 1), 0.045)
    ai += 1
    t += BEAT / 2

# ---- accents ----
def boom(i0, dur, freq, gain):
    for k in range(int(dur * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        v = math.sin(2 * math.pi * freq * tt) * math.exp(-tt * 3.5) * gain
        add(i, v, v)

def riser(i0, dur, gain):
    for k in range(int(dur * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        f = 200 + 2000 * (tt / dur)
        v = (random.random() * 2 - 1) * (tt / dur) ** 2 * gain
        v += math.sin(2 * math.pi * f * tt) * (tt / dur) ** 3 * gain * 0.4
        add(i, v, v)

def bell(i0, f, gain):
    for k in range(int(2.0 * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        v = (math.sin(2 * math.pi * f * tt) * 0.6 + math.sin(2 * math.pi * f * 2.76 * tt) * 0.3) \
            * math.exp(-tt * 1.8) * gain
        add(i, v, v * 0.9)

boom(int(0.0 * SR), 2.5, 38, 0.5)                                # open
riser(int(18.6 * SR), 1.4, 0.2)
boom(int(20.0 * SR), 2.8, 42, 0.55)                              # THE SAVE
bell(int(20.1 * SR), nt("A5"), 0.1)
bell(int(20.4 * SR), nt("C5"), 0.07)
bell(int(28.0 * SR), nt("E5"), 0.06)                             # calm hope
riser(int(36.8 * SR), 1.2, 0.16)
boom(int(38.0 * SR), 2.0, 40, 0.4)                               # bridge
boom(int(44.0 * SR), 1.8, 46, 0.4)                               # product
boom(int(55.0 * SR), 3.8, 38, 0.55)                              # outro hit
bell(int(55.05 * SR), nt("A4"), 0.14)
bell(int(55.30 * SR), nt("E5"), 0.09)
bell(int(55.55 * SR), nt("A5"), 0.06)

# ---- master: soft clip + fades ----
for i in range(N):
    vL = max(-1.0, min(1.0, math.tanh(L[i] * 1.1)))
    vR = max(-1.0, min(1.0, math.tanh(R[i] * 1.1)))
    t = i / SR
    g = 1.0
    if t < 0.8: g = t / 0.8
    if t > 57.5: g = max(0.0, (60.0 - t) / 2.5)
    L[i] = vL * g
    R[i] = vR * g

with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    inter = array.array("h")
    for i in range(N):
        inter.append(int(L[i] * 32000))
        inter.append(int(R[i] * 32000))
    w.writeframes(inter.tobytes())
print("wrote", OUT, round(N / SR, 2), "s")
