"""60s music bed for the Mirage brag video. Pure stdlib (no numpy on this box).
Tempo 100 BPM, key A minor. Chords: Am (0-21), Fmaj7 (21-36), C (36-47), G (47-55), Am (55-60).
Accents: 0.0 boom, 3.0 pad-in, 20-21 riser -> 21 stab, 35.2-36 riser -> 36 impact,
47 stab, 55 final hit + tail.
"""
import math, wave, array, os

SR = 44100
DUR = 60.0
N = int(SR * DUR)
BPM = 100.0
BEAT = 60.0 / BPM  # 0.6s
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.wav")

L = array.array("f", [0.0] * N)
R = array.array("f", [0.0] * N)

def env(t, attack, hold, release, total):
    """simple AHDR envelope 0..1 at time t"""
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

# ---- note freqs (equal temperament, A4=440) ----
def nt(name):
    base = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}
    p = base[name[0]]
    o = int(name[-1])
    if "#" in name: p += 1
    midi = (o + 1) * 12 + p
    return 440.0 * (2 ** ((midi - 69) / 12))

CHORDS = [  # (start, end, [freqs]) pad voicing
    (3.0, 21.0, [nt("A2"), nt("C3"), nt("E3"), nt("A3")]),           # Am
    (21.0, 36.0, [nt("F2"), nt("A2"), nt("C3"), nt("E3")]),          # Fmaj7
    (36.0, 47.0, [nt("C3"), nt("E3"), nt("G3"), nt("C4")]),          # C
    (47.0, 55.0, [nt("G2"), nt("B2"), nt("D3"), nt("G3")]),          # G
    (55.0, 60.0, [nt("A2"), nt("C3"), nt("E3"), nt("A3")]),          # Am
]

# ---- pad: detuned sine stack, slow attack, gentle stereo spread ----
for (s, e, freqs) in CHORDS:
    total = e - s
    for f_i, f in enumerate(freqs):
        det = 1.0 + (0.0015 * (f_i % 2 * 2 - 1))
        pan = -0.4 + 0.27 * f_i  # spread
        gl = math.sqrt((1 - pan) / 2) * (0.9 if f_i % 2 == 0 else 0.6)
        gr = math.sqrt((1 + pan) / 2) * (0.9 if f_i % 2 == 0 else 0.6)
        i0 = int(s * SR)
        i1 = min(N, int(e * SR))
        w = 2 * math.pi * f / SR
        wd = 2 * math.pi * f * det / SR
        for i in range(i0, i1):
            t = (i - i0) / SR
            a = env(t, 1.2, max(0.0, total - 2.2), 1.0, total)
            v = (math.sin(w * i) + math.sin(wd * i)) * 0.5 * a * 0.055
            add(i, v * gl, v * gr)

# ---- sub bass: root of chord, quiet sine ----
ROOTS = [(0.0, 21.0, nt("A1")), (21.0, 36.0, nt("F1")), (36.0, 47.0, nt("C2")),
         (47.0, 55.0, nt("G1")), (55.0, 60.0, nt("A1"))]
for (s, e, f) in ROOTS:
    i0, i1 = int(s * SR), min(N, int(e * SR))
    w = 2 * math.pi * f / SR
    for i in range(i0, i1):
        t = (i - i0) / SR
        a = env(t, 0.8, max(0.0, (e - s) - 1.6), 0.8, e - s)
        v = math.sin(w * i) * a * 0.09
        add(i, v, v)

# ---- kick: sine sweep 120->45, from 8s to 57s, density per section ----
def kick(i0):
    for k in range(int(0.18 * SR)):
        i = i0 + k
        if i >= N: break
        t = k / SR
        f = 120 * math.exp(-t * 18) + 45
        # integrate phase approximately
        ph = 2 * math.pi * (45 * t + (120 - 45) * (1 - math.exp(-t * 18)) / 18)
        v = math.sin(ph) * math.exp(-t * 16) * 0.5
        add(i, v, v)

t = 8.0
while t < 57.0:
    kick(int(t * SR))
    # half-time feel in outro
    t += BEAT * (2 if t >= 55.0 else (1 if t < 47.0 else 1.5))

# ---- hats: white noise blips, 8ths from 21s, pan alternate ----
import random
random.seed(7)
t = 21.0
hi = 0
while t < 55.0:
    i0 = int(t * SR)
    pan = 0.35 if hi % 2 == 0 else -0.35
    gl, gr = math.sqrt((1 - pan) / 2), math.sqrt((1 + pan) / 2)
    for k in range(int(0.03 * SR)):
        i = i0 + k
        if i >= N: break
        # crude highpass: noise * decay
        v = (random.random() * 2 - 1) * math.exp(-k / SR * 120) * 0.035
        add(i, v * gl, v * gr)
    hi += 1
    t += BEAT / 2

# ---- arp plucks: soft triangle 8ths from 36s on chord tones ----
def pluck(i0, f, gain):
    for k in range(int(0.22 * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        # triangle via arctan-ish approximation: sin with soft clip
        v = math.tanh(math.sin(2 * math.pi * f * tt) * 1.4) * math.exp(-tt * 14) * gain
        add(i, v * 0.85, v)

def chord_at(t):
    for (s, e, freqs) in CHORDS:
        if s <= t < e: return freqs
    return CHORDS[-1][2]

t = 36.0
ai = 0
while t < 55.0:
    freqs = chord_at(t)
    f = freqs[(ai % 3) + 1]
    pluck(int(t * SR), f * (2 if ai % 8 == 7 else 1), 0.05)
    ai += 1
    t += BEAT / 2

# ---- accents ----
def boom(i0, dur, freq, gain):
    for k in range(int(dur * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        v = math.sin(2 * math.pi * freq * tt) * math.exp(-tt * 4) * gain
        add(i, v, v)

def riser(i0, dur, gain):
    for k in range(int(dur * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        f = 200 + 2000 * (tt / dur)
        v = (random.random() * 2 - 1) * (tt / dur) ** 2 * gain
        # tone on top
        v += math.sin(2 * math.pi * f * tt) * (tt / dur) ** 3 * gain * 0.4
        add(i, v, v)

def bell(i0, f, gain):
    for k in range(int(1.6 * SR)):
        i = i0 + k
        if i >= N: break
        tt = k / SR
        v = (math.sin(2 * math.pi * f * tt) * 0.6 + math.sin(2 * math.pi * f * 2.76 * tt) * 0.3) \
            * math.exp(-tt * 2.2) * gain
        add(i, v, v * 0.9)

boom(int(0.0 * SR), 2.5, 40, 0.55)                 # hook hit
riser(int(19.8 * SR), 1.2, 0.16); boom(int(21.0 * SR), 2.0, 42, 0.4)   # guardian entrance
riser(int(35.0 * SR), 1.0, 0.18); boom(int(36.0 * SR), 2.2, 44, 0.45)  # bot/graph impact
boom(int(47.0 * SR), 1.8, 46, 0.35)                # layers
boom(int(55.0 * SR), 3.5, 38, 0.5)                 # outro hit
bell(int(55.05 * SR), nt("A4"), 0.12)
bell(int(55.30 * SR), nt("E5"), 0.08)

# ---- master: soft clip + global fades ----
for i in range(N):
    vL = max(-1.0, min(1.0, math.tanh(L[i] * 1.1)))
    vR = max(-1.0, min(1.0, math.tanh(R[i] * 1.1)))
    t = i / SR
    g = 1.0
    if t < 1.0: g = t / 1.0
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
