(() => {
  const DURATION = 30;
  const BPM = 80;
  const BEAT = 60 / BPM;
  const BAR = BEAT * 4;
  const MASTER = 1.4;

  // ---------- Timeline helpers ----------
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const ease = p => .5 - .5 * Math.cos(Math.PI * clamp(p));
  const lin = (t, a, b) => clamp((t - a) / (b - a));
  const seg = (t, a, b) => ease(lin(t, a, b));
  const mix = (a, b, p) => a + (b - a) * p;
  const pulse = (t, at, w) => Math.max(0, 1 - Math.abs(t - at) / w);
  function keyed(t, keys) {
    if (t <= keys[0][0]) return keys[0].slice(1);
    for (let i = 0; i < keys.length - 1; i++) {
      const [a, ...va] = keys[i], [b, ...vb] = keys[i + 1];
      if (t < b) { const p = ease((t - a) / (b - a)); return va.map((v, j) => mix(v, vb[j], p)); }
    }
    return keys[keys.length - 1].slice(1);
  }

  // ---------- Scene elements ----------
  const $ = id => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const SPRITE_W = {
    jaga: { front: 345, smile: 345, yawn: 345, side: 343 },
    sakura: { front: 347, smile: 347, yawn: 347, side: 349 },
    manju: { front: 337, smile: 337, back: 336 }
  };
  const SPRITE_H = 440;

  function makeChar(id, name) {
    const g = $(id);
    g.textContent = '';
    const imgs = {};
    for (const [key, w] of Object.entries(SPRITE_W[name])) {
      if (id === 'manju-back' ? key !== 'back' : key === 'back') continue;
      const im = document.createElementNS(NS, 'image');
      im.setAttribute('href', `assets/${name}-${key}.png`);
      im.dataset.w = w;
      im.setAttribute('visibility', 'hidden');
      g.appendChild(im);
      imgs[key] = im;
    }
    let shown = null, lastH = 0;
    return function set({ sprite, x, y, h, flip = 1, rot = 0, sx = 1, sy = 1 }) {
      if (shown !== sprite) {
        if (shown) imgs[shown].setAttribute('visibility', 'hidden');
        imgs[sprite].setAttribute('visibility', 'visible');
        shown = sprite; lastH = 0;
      }
      if (lastH !== h) {
        for (const im of Object.values(imgs)) {
          const w = h * im.dataset.w / SPRITE_H;
          im.setAttribute('width', w); im.setAttribute('height', h);
          im.setAttribute('x', -w / 2); im.setAttribute('y', -h);
        }
        lastH = h;
      }
      g.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${rot.toFixed(2)}) scale(${(flip * sx).toFixed(4)} ${sy.toFixed(4)})`);
    };
  }

  const jaga = makeChar('jaga', 'jaga');
  const sakura = makeChar('sakura', 'sakura');
  const manju = makeChar('manju', 'manju');
  const manjuBack = makeChar('manju-back', 'manju');

  const el = {
    sceneA: $('scene-a'), sceneB: $('scene-b'), camA: $('cam-a'), camB: $('cam-b'),
    teapotA: $('teapot-a'), streamA: $('stream-a'), teaA: $('tea-a'), steamA: $('steam-a'), emptySeat: $('empty-seat'),
    cushion: $('cushion'), flower: $('flower-carried'), budVase: $('bud-vase'), card: $('card'),
    vcupB: $('vcup-b'), steamB: $('steam-b'), lampGlow: $('lamp-glow'), stars: $('stars'),
    dim: $('dim'), title: $('title'), lyric: $('lyric'), endText: $('end-text'), fade: $('fade')
  };

  const breath = (t, ph) => [1 - .006 * Math.sin(t * 2.2 + ph), 1 + .014 * Math.sin(t * 2.2 + ph)];
  const blink = (t, times) => times.some(b => t >= b && t < b + .14);

  function steam(group, t, intensity) {
    [...group.children].forEach((w, i) => {
      const ph = (t * .3 + i / 3) % 1;
      const x = Math.sin(t * 1.1 + i * 2.1) * 6 + (i - 1) * 10;
      w.setAttribute('transform', `translate(${x.toFixed(1)} ${(-74 - ph * 85).toFixed(1)}) scale(${(.55 + ph * .5).toFixed(3)})`);
      w.setAttribute('opacity', (Math.sin(Math.PI * ph) * intensity * .55).toFixed(3));
    });
  }

  // ---------- Scene A: pouring tea, seen from behind Manju (0–7s) ----------
  const CAM_A = [[0, 450, 1060, 1], [6.6, 500, 1110, 1.12]];
  function renderA(t) {
    const [cx, cy, s] = keyed(t, CAM_A);
    el.camA.setAttribute('transform', `translate(450 800) scale(${s.toFixed(4)}) translate(${-cx} ${-cy})`);

    const lift = seg(t, .2, .8) - seg(t, 4.8, 5.4);
    const tilt = 38 * (seg(t, .8, 1.4) - seg(t, 4.2, 4.8));
    const px = 395, py = mix(1262, 1150, lift);
    el.teapotA.setAttribute('transform', `translate(${px} ${py.toFixed(1)}) scale(1.25) rotate(${tilt.toFixed(2)} 0 -20)`);

    const a = tilt * Math.PI / 180, dx = 104, dy = -78;
    const tipX = px + 1.25 * (dx * Math.cos(a) - dy * Math.sin(a));
    const tipY = py + 1.25 * (dx * Math.sin(a) + dy * Math.cos(a) - 20);
    const flow = lin(t, 1.25, 1.45) * (1 - lin(t, 4.15, 4.35));
    el.streamA.setAttribute('d', `M${tipX.toFixed(1)} ${tipY.toFixed(1)} Q${(tipX + 22).toFixed(1)} ${(tipY + 6).toFixed(1)} 567 1168`);
    el.streamA.setAttribute('opacity', flow.toFixed(3));
    el.streamA.setAttribute('stroke-dashoffset', (-t * 160).toFixed(1));

    const level = lin(t, 1.4, 4.2);
    el.teaA.setAttribute('transform', `translate(0 -72) scale(${Math.sqrt(level).toFixed(3)}) translate(0 72)`);
    el.teaA.setAttribute('opacity', level > .01 ? 1 : 0);
    steam(el.steamA, t, .25 + .75 * lin(t, 2.2, 3.8));
    el.emptySeat.setAttribute('opacity', (.1 + .04 * Math.sin(t * 1.6)).toFixed(3));

    const [bx, by] = breath(t, 0);
    manjuBack({ sprite: 'back', x: 120, y: 1730, h: 720, rot: 3 * lift, sx: bx, sy: by });
    el.title.setAttribute('opacity', (seg(t, .5, 1.6) * (1 - seg(t, 4.9, 5.9))).toFixed(3));
  }

  // ---------- Scene B: the living room (7–30s) ----------
  const CAM_B = [
    [12.8, 538, 1270, 1.5], [14.8, 560, 1280, 1.45],
    [15.4, 620, 1200, 1.4], [16.6, 690, 1050, 1.5], [18.4, 590, 1110, 1.45], [20.3, 520, 1150, 1.5],
    [21.9, 450, 1150, 1.7], [23.4, 450, 1110, 1.3], [27.8, 450, 1110, 1.3], [29.8, 590, 880, 1.6]
  ];
  const H = 260;
  const CUSHION = 1.25;

  function renderB(t) {
    // JAGA pushes the big cushion to the empty seat, then tidies it.
    const N = 7, P0 = 7.3, P1 = 12.8;
    const u = clamp((t - P0) / (P1 - P0)) * N;
    const k = Math.min(Math.floor(u), N - 1), f = u - k;
    const cushionX = mix(1250, 450, (k + ease(f * 1.6)) / N);

    // The camera follows Jaga while he pushes, then switches to keyframes.
    let [cx, cy, s] = keyed(t, CAM_B);
    if (t < 12.8) {
      cx = clamp(mix(1250, 450, u / N) + 88, 538, 1000); cy = 1270; s = 1.5;
    }
    el.camB.setAttribute('transform', `translate(450 800) scale(${s.toFixed(4)}) translate(${-cx} ${-cy})`);
    const effort = t > P0 && t < P1 ? Math.sin(Math.PI * clamp(f * 1.6)) : 0;
    const squish = .08 * Math.sin(Math.PI * lin(t, 12.8, 13.3)) + .05 * (pulse(t, 14.1, .12) + pulse(t, 14.6, .12));
    const cushionRot = -4 + 2.5 * seg(t, 14.0, 14.15) + 1.5 * seg(t, 14.5, 14.65);
    el.cushion.setAttribute('transform', `translate(${cushionX.toFixed(1)} 1500) rotate(${cushionRot.toFixed(2)}) scale(${(CUSHION * (1 + squish * .5)).toFixed(3)} ${(CUSHION * (1 - squish)).toFixed(3)})`);

    const [jbx, jby] = breath(t, 1);
    if (t < 13.3) {
      jaga({ sprite: 'side', x: cushionX + 262, y: 1500, h: H, flip: -1, rot: -7 * effort, sx: 1 + .05 * effort, sy: 1 - .05 * effort - .03 * Math.abs(Math.sin(Math.PI * f)) });
    } else if (t < 14.7) {
      const hp = lin(t, 13.6, 14.6);
      jaga({ sprite: t < 13.6 ? 'front' : 'smile', x: mix(712, 690, seg(t, 13.5, 14)), y: 1500 - Math.abs(Math.sin(2 * Math.PI * hp)) * 22, h: H, sx: jbx, sy: jby });
    } else if (t < 15.3) {
      const p = lin(t, 14.7, 15.3);
      jaga({ sprite: 'smile', x: mix(690, 690, ease(p)), y: mix(1500, 1440, ease(p)) - Math.sin(Math.PI * p) * 42, h: H });
    } else {
      const y = clamp((t - 24.0) / 1.4);
      const yawning = t >= 24.15 && t < 25.25;
      const sprite = yawning ? 'yawn' : (t >= 21.6 && t < 23) || t >= 27 || blink(t, [17.1, 19.9, 26.2]) ? 'smile' : 'front';
      jaga({ sprite, x: 690, y: 1440, h: H, sx: jbx, sy: jby + .06 * Math.sin(Math.PI * y), rot: -2 * Math.sin(Math.PI * y) });
    }

    // SAKURA brings a flower from the window and a little drawing.
    const [sbx, sby] = breath(t, 2.3);
    let sk, paw = null;
    if (t < 15) {
      sk = { sprite: blink(t, [9.2, 12.4]) ? 'smile' : 'front', x: 600, y: 1150, h: H, sx: sbx, sy: sby };
    } else if (t < 16.3) {
      const p = lin(t, 15, 16.3);
      sk = { sprite: 'side', x: mix(600, 770, ease(p)), y: mix(1150, 958, ease(p)) - Math.abs(Math.sin(2 * Math.PI * p)) * 38, h: H };
    } else if (t < 17) {
      sk = { sprite: 'front', x: 770, y: 958, h: H, sx: sbx, sy: sby };
      paw = [770 + 33, 958 - 116];
    } else if (t < 18.4) {
      const p = lin(t, 17, 18.4);
      sk = { sprite: 'side', flip: -1, x: mix(770, 560, ease(p)), y: mix(958, 1150, ease(p)) - Math.abs(Math.sin(2 * Math.PI * p)) * 38, h: H };
      paw = [sk.x - 66, sk.y - 118];
    } else {
      const y = clamp((t - 25.2) / 1.4);
      const yawning = t >= 25.35 && t < 26.45;
      const sprite = yawning ? 'yawn' : (t >= 19.8 && t < 20.8) || t >= 27.1 || blink(t, [22.4, 24.6]) ? 'smile' : 'front';
      sk = { sprite, x: 560, y: 1150, h: H, sx: sbx, sy: sby + .06 * Math.sin(Math.PI * y), rot: 2 * Math.sin(Math.PI * y) };
      if (t < 18.95) paw = [560 + 33, 1150 - 116];
    }
    sakura(sk);

    let fx = 798, fy = 952, fr = -6, fo = 1;
    if (t >= 16.5 && paw) {
      if (t < 16.9) { const p = seg(t, 16.5, 16.9); fx = mix(798, paw[0], p); fy = mix(952, paw[1] + 70, p); fr = mix(-6, 8, p); }
      else if (t < 18.4) { fx = paw[0]; fy = paw[1] + 70; fr = 8; }
      else { const p = seg(t, 18.45, 18.9); fx = mix(paw[0], 520, p); fy = mix(paw[1] + 70, 1102, p); fr = mix(8, 0, p); }
    }
    if (t >= 18.95) fo = 0;
    el.flower.setAttribute('transform', `translate(${fx.toFixed(1)} ${fy.toFixed(1)}) rotate(${fr.toFixed(2)}) scale(.85)`);
    el.flower.setAttribute('opacity', fo);
    el.budVase.setAttribute('transform', 'translate(520 1128)');
    el.budVase.setAttribute('opacity', t >= 18.9 ? 1 : 0);

    const cp = seg(t, 19.2, 20.2);
    el.card.setAttribute('transform', `translate(${mix(585, 566, cp).toFixed(1)} ${mix(1080, 1186, cp).toFixed(1)}) rotate(${mix(-10, 6, cp).toFixed(2)}) scale(${mix(.5, .9, cp).toFixed(3)} ${mix(.5, .55, cp).toFixed(3)})`);
    el.card.setAttribute('opacity', seg(t, 19.0, 19.3).toFixed(3));

    // MANJU slides the tea toward your seat, then dims the lamp.
    const [mbx, mby] = breath(t, 4.1);
    const lean = seg(t, 20.4, 21.0) - seg(t, 22.0, 22.6);
    let mx = 300 + 50 * lean, my = 1150;
    const toLamp = lin(t, 26.6, 27.1), back = lin(t, 27.4, 27.9);
    if (t >= 26.6) {
      mx = mix(mix(300, 215, ease(toLamp)), 300, ease(back));
      my -= Math.sin(Math.PI * toLamp) * 30 + Math.sin(Math.PI * back) * 30;
    }
    const pull = pulse(t, 27.2, .12);
    const msprite = lean > .3 || t >= 26.3 || blink(t, [8.4, 11.7, 14.9, 18.0, 24.6]) ? 'smile' : 'front';
    manju({ sprite: msprite, x: mx, y: my, h: H, rot: 8 * lean, sx: mbx, sy: mby - .06 * pull });

    const vp = seg(t, 20.9, 21.9);
    el.vcupB.setAttribute('transform', `translate(${mix(430, 450, vp).toFixed(1)} ${mix(1160, 1210, vp).toFixed(1)}) scale(${(1 + .15 * vp).toFixed(3)})`);
    steam(el.steamB, t, .9);

    const dim = seg(t, 27.15, 28.1);
    el.lampGlow.setAttribute('opacity', (1 - .65 * dim).toFixed(3));
    el.dim.setAttribute('opacity', (.42 * dim).toFixed(3));
    [...el.stars.children].forEach((c, i) => c.setAttribute('opacity', (.55 + .45 * Math.sin(t * 1.7 + i * 1.9)).toFixed(3)));
  }

  const LYRICS = [
    [15, 18, 'うまく話せなくても いいよ'], [18, 21, 'ため息ひとつ 置いていこう'],
    [21, 24, '今日も よく帰ってきたね'], [24, 27, 'あたたかい夜を あなたに']
  ];

  function render(t) {
    t = clamp(t, 0, DURATION);
    const crossfade = lin(t, 6.4, 7.0);
    el.sceneA.setAttribute('opacity', (1 - crossfade).toFixed(3));
    el.sceneA.setAttribute('display', crossfade >= 1 ? 'none' : 'inline');
    el.sceneB.setAttribute('display', t < 6.4 ? 'none' : 'inline');
    if (t < 7) renderA(t);
    if (t >= 6.4) renderB(t);
    else el.dim.setAttribute('opacity', 0);

    const line = LYRICS.find(([a, b]) => t >= a && t < b);
    if (line) {
      if (el.lyric.textContent !== line[2]) el.lyric.textContent = line[2];
      el.lyric.setAttribute('opacity', (seg(t, line[0], line[0] + .35) * (1 - seg(t, line[1] - .35, line[1]))).toFixed(3));
    } else el.lyric.setAttribute('opacity', 0);
    el.endText.setAttribute('opacity', seg(t, 28.0, 28.9).toFixed(3));
    el.fade.setAttribute('opacity', seg(t, 29.0, 30.0).toFixed(3));
  }

  // ---------- Music: soft lo-fi pop, 80 BPM, 10 bars ----------
  const CH = {
    F: [41, [53, 57, 60, 64]], Em: [40, [52, 55, 59, 62]], Dm: [38, [50, 53, 57, 60]],
    C: [36, [48, 52, 55, 59]], G: [43, [53, 55, 59, 62]]
  };
  const BARS = [
    [['F', 0, 4]], [['Em', 0, 4]], [['Dm', 0, 4]], [['C', 0, 4]], [['Dm', 0, 2], ['G', 2, 2]],
    [['F', 0, 4]], [['Em', 0, 4]], [['Dm', 0, 2], ['G', 2, 2]], [['C', 0, 4]], [['F', 0, 2], ['C', 2, 6]]
  ];
  const PIANO_LINE = {
    0: [[2.5, 79, .5], [3, 76, 1]], 1: [[2.5, 74, .5], [3, 71, 1]],
    2: [[0, 72, 1], [1, 69, 1], [2, 72, .5], [2.5, 74, 1.5]], 3: [[0, 76, 1.5], [1.5, 74, .5], [2, 71, 2]],
    4: [[0, 74, 1], [1, 72, 1], [2, 71, 1], [3, 74, 1]], 9: [[2, 76, 4]]
  };
  const HUM = {
    5: [[0, 76, .5], [.5, 76, .5], [1, 74, .5], [1.5, 72, .5], [2, 74, .5], [2.5, 76, .5], [3, 79, 1]],
    6: [[0, 79, .5], [.5, 76, .5], [1, 74, .5], [1.5, 76, .5], [2, 71, 2]],
    7: [[0, 77, .5], [.5, 77, .5], [1, 76, .5], [1.5, 74, .5], [2, 74, .5], [2.5, 72, .5], [3, 71, 1]],
    8: [[0, 72, .75], [.75, 74, .25], [1, 76, 1], [2, 74, 1], [3, 72, 1]]
  };

  const events = [];
  const add = (bar, beat, type, note = 0, len = 1, vel = 1) =>
    events.push({ t: bar * BAR + beat * BEAT, type, note, dur: len * BEAT, vel });
  BARS.forEach((chords, bar) => {
    const groove = bar >= 2 && bar <= 8;
    chords.forEach(([name, at, len]) => {
      const [root, voicing] = CH[name];
      voicing.forEach((n, i) => add(bar, at + i * .045, 'piano', n, len + 1, .8 - i * .06));
      if (len === 4 && groove) voicing.slice(2).forEach(n => add(bar, 2.5, 'piano', n, 1.5, .45));
      if (bar >= 2) {
        add(bar, at, 'bass', root, Math.min(len, 4) * .9);
        if (len === 4 && bar < 9) add(bar, at + 2.5, 'bass', root, 1.2, .7);
      }
      if (groove) for (let s = 0; s < len * 2; s++) add(bar, at + s / 2, 'guitar', voicing[[0, 2, 1, 3, 2, 1, 3, 2][s % 8]] + 12, .6, s % 2 ? .5 : .75);
    });
    if (groove) {
      add(bar, 0, 'kick'); add(bar, 2.5, 'kick', 0, 1, .75);
      add(bar, 1, 'snap'); add(bar, 3, 'snap');
      for (let s = 0; s < 8; s++) add(bar, s / 2 + (s % 2 ? .08 : 0), 'hat', 0, 1, s % 2 ? .6 : 1);
    }
    if (bar === 9) add(bar, 0, 'kick', 0, 1, .5);
    (PIANO_LINE[bar] || []).forEach(([b, n, l]) => add(bar, b, 'piano', n, l + .5, .7));
    (HUM[bar] || []).forEach(([b, n, l]) => add(bar, b, 'hum', n - 12, l));
  });
  events.sort((a, b) => a.t - b.t);

  const noiseCache = new WeakMap();
  function buffers(ctx) {
    if (noiseCache.has(ctx)) return noiseCache.get(ctx);
    const sr = ctx.sampleRate;
    const noise = ctx.createBuffer(1, sr, sr);
    const nd = noise.getChannelData(0);
    for (let i = 0; i < nd.length; i++) nd[i] = Math.random() * 2 - 1;
    const crackle = ctx.createBuffer(1, sr * DURATION, sr);
    const cd = crackle.getChannelData(0);
    for (let i = 0; i < cd.length; i++) {
      cd[i] += (Math.random() * 2 - 1) * .012;
      if (Math.random() < 9 / sr) { const a = (.15 + Math.random() * .35) * (Math.random() < .5 ? -1 : 1); for (let j = 0; j < 6 && i + j < cd.length; j++) cd[i + j] += a * Math.pow(.5, j); }
    }
    const b = { noise, crackle };
    noiseCache.set(ctx, b);
    return b;
  }

  const hz = n => 440 * Math.pow(2, (n - 69) / 12);
  function voice(ctx, out, ev, at) {
    const v = ev.vel;
    const envelope = (peak, attack, hold, release) => {
      const g = ctx.createGain();
      g.gain.setValueAtTime(.0001, at);
      g.gain.exponentialRampToValueAtTime(peak, at + attack);
      if (hold > attack) g.gain.setValueAtTime(peak, at + hold);
      g.gain.exponentialRampToValueAtTime(.0001, at + Math.max(attack, hold) + release);
      return g;
    };
    const osc = (type, freq, dest, end, gain = 1) => {
      const o = ctx.createOscillator(); o.type = type; o.frequency.value = freq;
      let node = o;
      if (gain !== 1) { const g = ctx.createGain(); g.gain.value = gain; o.connect(g); node = g; }
      node.connect(dest); o.start(at); o.stop(end);
      return o;
    };
    const filter = (type, freq, q = .7) => { const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q; return f; };
    const hit = (type, freq, peak, decay, q) => {
      const src = ctx.createBufferSource(); src.buffer = buffers(ctx).noise;
      const f = filter(type, freq, q), g = envelope(peak, .002, 0, decay);
      src.connect(f); f.connect(g); g.connect(out); src.start(at); src.stop(at + decay + .05);
    };
    switch (ev.type) {
      case 'piano': {
        const f = filter('lowpass', 2300), g = envelope(.1 * v, .006, 0, ev.dur + 1.2);
        f.connect(g); g.connect(out);
        const end = at + ev.dur + 1.4;
        osc('sine', hz(ev.note), f, end); osc('triangle', hz(ev.note) * 2, f, end, .22);
        break;
      }
      case 'guitar': {
        const f = filter('lowpass', 1700), g = envelope(.045 * v, .004, 0, .55);
        f.connect(g); g.connect(out);
        osc('sawtooth', hz(ev.note), f, at + .65, .6); osc('sine', hz(ev.note), f, at + .65);
        break;
      }
      case 'bass': {
        const f = filter('lowpass', 420), g = envelope(.06 * v, .02, ev.dur * .8, .18);
        f.connect(g); g.connect(out);
        const end = at + ev.dur + .3;
        osc('sine', hz(ev.note), f, end); osc('triangle', hz(ev.note), f, end, .45);
        break;
      }
      case 'hum': {
        const f = filter('lowpass', 1500), g = envelope(.075 * v, .07, ev.dur * .9, .2);
        f.connect(g); g.connect(out);
        const end = at + ev.dur + .3;
        const lfo = ctx.createOscillator(), depth = ctx.createGain();
        lfo.frequency.value = 5.2;
        depth.gain.setValueAtTime(0, at); depth.gain.linearRampToValueAtTime(hz(ev.note) * .006, at + Math.min(.3, ev.dur));
        lfo.connect(depth); lfo.start(at); lfo.stop(end);
        const o1 = osc('sine', hz(ev.note), f, end), o2 = osc('triangle', hz(ev.note), f, end, .45);
        depth.connect(o1.frequency); depth.connect(o2.frequency);
        break;
      }
      case 'kick': {
        const g = envelope(.15 * v, .003, 0, .3); g.connect(out);
        const o = osc('sine', 110, g, at + .35);
        o.frequency.setValueAtTime(110, at); o.frequency.exponentialRampToValueAtTime(45, at + .12);
        break;
      }
      case 'snap': hit('bandpass', 1800, .09 * v, .09, 1.2); break;
      case 'hat': hit('highpass', 8000, .02 * v, .035); break;
    }
  }

  function makeChain(ctx) {
    const input = ctx.createGain();
    const warm = ctx.createBiquadFilter(); warm.type = 'lowpass'; warm.frequency.value = 7000;
    const comp = ctx.createDynamicsCompressor();
    const master = ctx.createGain(); master.gain.value = MASTER;
    input.connect(warm); warm.connect(comp); comp.connect(master); master.connect(ctx.destination);
    return { input, master };
  }

  function scheduleSong(ctx, chain, from, t0) {
    for (const ev of events) if (ev.t >= from - .005) voice(ctx, chain.input, ev, t0 + ev.t - from);
    const vinyl = ctx.createBufferSource(); vinyl.buffer = buffers(ctx).crackle;
    const vf = ctx.createBiquadFilter(); vf.type = 'bandpass'; vf.frequency.value = 2600; vf.Q.value = .5;
    const vg = ctx.createGain(); vg.gain.value = .35;
    vinyl.connect(vf); vf.connect(vg); vg.connect(chain.input); vinyl.start(t0, from);
    const g = chain.master.gain, fadeAt = 28.4;
    g.setValueAtTime(from < fadeAt ? MASTER : MASTER * (DURATION - from) / (DURATION - fadeAt), t0);
    if (from < fadeAt) g.setValueAtTime(MASTER, t0 + fadeAt - from);
    g.linearRampToValueAtTime(0, t0 + DURATION - from);
  }

  // ---------- Playback ----------
  const AC = window.AudioContext || window.webkitAudioContext;
  const stage = $('stage'), toggle = $('toggle'), bigPlay = $('big-play'), seek = $('seek'), timeEl = $('time'), note = $('player-note'), fullscreen = $('fullscreen');
  let ctx = null, chain = null, playing = false, pausedAt = 0, startAt = 0, clockStart = 0;
  const now = () => ctx ? ctx.currentTime : performance.now() / 1000;
  const position = () => playing ? Math.max(0, now() - (ctx ? startAt : clockStart)) : pausedAt;

  function play(from = pausedAt) {
    if (from >= DURATION - .05) from = 0;
    if (!ctx && AC) ctx = new AC();
    if (ctx) {
      ctx.resume();
      chain = makeChain(ctx);
      const t0 = ctx.currentTime + .06;
      scheduleSong(ctx, chain, from, t0);
      startAt = t0 - from;
    } else {
      clockStart = now() - from;
      note.textContent = 'このブラウザでは音声を再生できないため、映像のみ再生します。';
    }
    playing = true;
    stage.dataset.state = 'playing';
    toggle.textContent = '❚❚'; toggle.setAttribute('aria-label', '一時停止');
  }

  function pause(state = 'paused') {
    if (!playing) return;
    pausedAt = Math.min(position(), DURATION);
    playing = false;
    if (chain) {
      const c = chain; chain = null;
      c.master.gain.cancelScheduledValues(ctx.currentTime);
      c.master.gain.setTargetAtTime(0, ctx.currentTime, .02);
      setTimeout(() => c.master.disconnect(), 150);
    }
    stage.dataset.state = state;
    toggle.textContent = '▶'; toggle.setAttribute('aria-label', state === 'ended' ? 'もう一度再生' : '再生');
    bigPlay.lastChild.textContent = state === 'ended' ? ' REPLAY' : ' PLAY';
  }

  const togglePlay = () => playing ? pause() : play();
  toggle.addEventListener('click', togglePlay);
  bigPlay.addEventListener('click', () => play());
  $('mv').addEventListener('click', togglePlay);
  document.addEventListener('keydown', e => {
    if (e.code !== 'Space' || e.target.closest('button, input, a')) return;
    e.preventDefault(); togglePlay();
  });
  seek.max = DURATION;
  seek.addEventListener('input', () => {
    const wasPlaying = playing;
    if (wasPlaying) pause();
    pausedAt = +seek.value;
    if (wasPlaying) play(pausedAt);
    else if (stage.dataset.state !== 'paused') { stage.dataset.state = 'paused'; bigPlay.lastChild.textContent = ' PLAY'; }
  });
  fullscreen.addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (stage.requestFullscreen) stage.requestFullscreen();
  });
  if (!document.fullscreenEnabled) fullscreen.hidden = true;

  const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  function frame() {
    let pos = position();
    if (playing && pos >= DURATION) { pause('ended'); pos = pausedAt = DURATION; }
    render(pos);
    seek.value = pos.toFixed(2);
    timeEl.textContent = `${fmt(pos)} / ${fmt(DURATION)}`;
    requestAnimationFrame(frame);
  }

  // ---------- Export hooks (used by tools/export-mv.mjs) ----------
  function wavBase64(buf) {
    const ch = buf.numberOfChannels, len = buf.length, sr = buf.sampleRate;
    const view = new DataView(new ArrayBuffer(44 + len * ch * 2));
    const str = (o, s) => [...s].forEach((c, i) => view.setUint8(o + i, c.charCodeAt(0)));
    str(0, 'RIFF'); view.setUint32(4, 36 + len * ch * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, ch, true);
    view.setUint32(24, sr, true); view.setUint32(28, sr * ch * 2, true); view.setUint16(32, ch * 2, true);
    view.setUint16(34, 16, true); str(36, 'data'); view.setUint32(40, len * ch * 2, true);
    const data = [...Array(ch)].map((_, c) => buf.getChannelData(c));
    let o = 44;
    for (let i = 0; i < len; i++) for (let c = 0; c < ch; c++) { view.setInt16(o, clamp(data[c][i], -1, 1) * 32767, true); o += 2; }
    let bin = ''; const bytes = new Uint8Array(view.buffer);
    for (let i = 0; i < bytes.length; i += 32768) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
    return btoa(bin);
  }
  const images = [...document.querySelectorAll('#mv image')].map(im => im.getAttribute('href'));
  window.__mv = {
    duration: DURATION,
    render,
    ready: Promise.all([document.fonts.ready, ...images.map(src => new Promise(r => { const i = new Image(); i.onload = i.onerror = r; i.src = src; }))]),
    async renderAudio() {
      const sr = 44100, oc = new OfflineAudioContext(2, sr * DURATION, sr);
      scheduleSong(oc, makeChain(oc), 0, 0);
      return wavBase64(await oc.startRendering());
    }
  };

  if (new URLSearchParams(location.search).has('export')) {
    document.body.classList.add('export');
    render(0);
  } else {
    requestAnimationFrame(frame);
  }
})();
