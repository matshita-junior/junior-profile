(() => {
  const DURATION = 30;
  const BPM = 100;
  const BEAT = 60 / BPM;
  const BAR = BEAT * 4;
  const MASTER = 1.25;

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
  const ASSETS = '../assets/';
  const SPRITE_W = {
    jaga: { front: 345, smile: 345 },
    sakura: { front: 347, smile: 347 },
    manju: { front: 337, smile: 337 }
  };
  const SPRITE_H = 440;
  const COSTUME_H = 300; // costumes are drawn for a 300px-tall sprite

  // A character plus the costume layers drawn behind and in front of it.
  function makeChar(id, name) {
    const g = $(id), back = $(`${id}-back`), front = $(`${id}-front`);
    g.textContent = '';
    const imgs = {};
    for (const [key, w] of Object.entries(SPRITE_W[name])) {
      const im = document.createElementNS(NS, 'image');
      im.setAttribute('href', `${ASSETS}${name}-${key}.png`);
      im.dataset.w = w;
      im.setAttribute('visibility', 'hidden');
      g.appendChild(im);
      imgs[key] = im;
    }
    let shown = null, lastH = 0;
    return function set({ sprite, x, y, h, rot = 0, sx = 1, sy = 1, cape = 1 }) {
      if (shown !== sprite) {
        if (shown) imgs[shown].setAttribute('visibility', 'hidden');
        imgs[sprite].setAttribute('visibility', 'visible');
        shown = sprite;
      }
      if (lastH !== h) {
        for (const im of Object.values(imgs)) {
          const w = h * im.dataset.w / SPRITE_H;
          im.setAttribute('width', w); im.setAttribute('height', h);
          im.setAttribute('x', -w / 2); im.setAttribute('y', -h);
        }
        lastH = h;
      }
      const base = `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${rot.toFixed(2)}) scale(${sx.toFixed(4)} ${sy.toFixed(4)})`;
      const k = (h / COSTUME_H).toFixed(4);
      g.setAttribute('transform', base);
      front.setAttribute('transform', `${base} scale(${k})`);
      back.setAttribute('transform', `${base} scale(${k}) scale(${cape.toFixed(3)} 1)`);
    };
  }

  const jagaA = makeChar('jaga-a', 'jaga'), sakuraA = makeChar('sakura-a', 'sakura'), manjuA = makeChar('manju-a', 'manju');
  const jagaB = makeChar('jaga-b', 'jaga'), sakuraB = makeChar('sakura-b', 'sakura'), manjuB = makeChar('manju-b', 'manju');

  const el = {
    sceneA: $('scene-a'), sceneB: $('scene-b'), camA: $('cam-a'), camB: $('cam-b'),
    batsA: $('bats-a'), batsB: $('bats-b'), knock: $('knock'), door: $('door-b'), boo: $('boo'),
    blush: [$('blush-manju'), $('blush-jaga'), $('blush-sakura')], candies: $('candies'),
    tea: $('tea'), steamTea: $('steam-tea'), teaBubble: $('tea-bubble'),
    jolGlow: document.querySelector('#jol .jol-glow'), bucketGlow: document.querySelector('#cos-jaga-bucket .bucket-glow'),
    bucketFace: document.querySelector('#cos-jaga-bucket .bucket-face'),
    title: $('title'), lyric: $('lyric'), endText: $('end-text'), fade: $('fade')
  };

  const breath = (t, ph) => [1 - .006 * Math.sin(t * 2.2 + ph), 1 + .014 * Math.sin(t * 2.2 + ph)];
  const blink = (t, times) => times.some(b => t >= b && t < b + .14);
  const place = (node, x, y, s = 1, r = 0) => node.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${r.toFixed(2)}) scale(${s.toFixed(3)})`);
  const cam = (g, [cx, cy, s]) => g.setAttribute('transform', `translate(450 800) scale(${s.toFixed(4)}) translate(${-cx} ${-cy})`);

  function bats(group, t, spanX, y0) {
    [...group.children].forEach((b, i) => {
      const x = ((i * 430 + t * (70 + i * 18)) % spanX) - 300;
      const y = y0 + i * 90 + Math.sin(t * 2 + i * 1.7) * 30;
      b.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${(1 + i * .15).toFixed(2)} ${(.45 + .55 * Math.abs(Math.sin(t * 11 + i))).toFixed(3)})`);
    });
  }
  function steam(group, t, intensity) {
    [...group.children].forEach((w, i) => {
      const ph = (t * .3 + i / 3) % 1;
      const x = Math.sin(t * 1.1 + i * 2.1) * 6 + (i - 1) * 10;
      w.setAttribute('transform', `translate(${x.toFixed(1)} ${(-74 - ph * 85).toFixed(1)}) scale(${(.55 + ph * .5).toFixed(3)})`);
      w.setAttribute('opacity', (Math.sin(Math.PI * ph) * intensity * .55).toFixed(3));
    });
  }

  // ---------- Scene A: walking down the dusk street to your door (0–14.4s) ----------
  const HA = 230, BASE_A = 1330;
  function renderA(t) {
    const walk = ease(lin(t, .5, 9.4)), lead = mix(-100, 1740, walk), walking = t > .5 && t < 9.4;
    let [cx, cy, s] = [Math.min(Math.max(lead - 120, 450), 1620), 1090, 1.25];
    const close = seg(t, 11.4, 13.0);
    cx = mix(cx, 1580, close); cy = mix(cy, 1130, close); s = mix(s, 1.45, close);
    cam(el.camA, [cx, cy, s]);
    bats(el.batsA, t, 2600, 300);

    const knockP = t >= 10 && t < 11.6 ? Math.abs(Math.sin((t - 10) * Math.PI * 2.5)) : 0;
    const nervous = seg(t, 11.6, 12.0) * Math.sin(t * 38) * 2.5;
    const hop = ph => walking ? Math.abs(Math.sin(t * Math.PI * 2.4 + ph)) * 24 : 0;
    const lean = walking ? 5 : 0;
    const CH = [[manjuA, -340, 0], [sakuraA, -170, 1.1], [jagaA, 0, 2.2]];
    CH.forEach(([set, off, ph]) => {
      const [bx, by] = breath(t, ph);
      const isJaga = set === jagaA;
      const smile = walking ? Math.sin(t * 1.3 + ph) > .2 : blink(t, [12.6 + ph * .3]) || (t >= 13.4);
      set({ sprite: smile ? 'smile' : 'front', x: lead + off + nervous, y: BASE_A - hop(ph), h: HA, rot: lean + (isJaga ? 10 * knockP : 0), sx: bx, sy: by,
        cape: 1 + (walking ? .08 * Math.sin(t * 7 + ph) : 0) });
    });
    [...el.knock.children].forEach((k, i) => k.setAttribute('opacity', (seg(t, 10.2 + i * .6, 10.35 + i * .6) * (1 - seg(t, 11.4, 11.8))).toFixed(3)));
  }

  // ---------- Scene B: you open the door — "boo!" (14.4–30s) ----------
  const HB = 330, BASE_B = 1440, XB = [270, 630, 450]; // manju, sakura, jaga
  function renderB(t) {
    cam(el.camB, [450, mix(1090, 1060, lin(t, 14.4, 30)), mix(1.25, 1.3, lin(t, 14.4, 30))]);
    bats(el.batsB, t, 1600, 300);
    const open = seg(t, 14.6, 15.4);
    el.door.setAttribute('transform', `translate(130 0) scale(${mix(1, .04, open).toFixed(4)} 1) translate(-130 0)`);
    el.door.setAttribute('opacity', open > .99 ? 0 : 1);

    const boo = Math.sin(Math.PI * lin(t, 16.6, 17.3));
    const shy = seg(t, 19.2, 19.7);
    const swirl = t >= 15.6 && t < 16.8 ? Math.cos((t - 15.6) * Math.PI * 4) : 1;
    const wave = seg(t, 26.2, 26.6);
    [[manjuB, 0, .3], [sakuraB, 1, 1.4], [jagaB, 2, 2.5]].forEach(([set, i, ph]) => {
      const [bx, by] = breath(t, ph);
      const sway = shy * Math.sin(t * 3 + ph) * 5 + wave * Math.sin((t - 26.2) * Math.PI * 2.6 + ph) * 6;
      const bounce = shy * Math.abs(Math.sin(t * Math.PI * 1.6 + ph)) * 12;
      const surprised = t >= 16.6 && t < 19.2;
      const sprite = surprised ? 'front' : t >= 19.2 || blink(t, [15.9 + ph * .2]) ? 'smile' : 'front';
      set({ sprite, x: XB[i], y: BASE_B - boo * 70 - bounce, h: HB, rot: sway, sx: bx * (1 + .06 * boo), sy: by * (1 + .06 * boo),
        cape: i === 0 ? swirl : 1 });
    });
    el.blush.forEach(b => b.setAttribute('opacity', (shy * (1 - seg(t, 27, 28))).toFixed(3)));

    const bp = seg(t, 16.6, 16.9) * (1 - seg(t, 18.4, 18.8));
    place(el.boo, 450, 820, Math.max(bp, .001) * (1 + .06 * Math.sin(t * 9)), Math.sin(t * 4) * 4);
    el.boo.setAttribute('opacity', bp > .01 ? 1 : 0);

    // Candy for you, one from each of them.
    const FROM = [270, 450, 630], TO = [[190, 1390], [330, 1350], [710, 1390]];
    [...el.candies.children].forEach((c, i) => {
      const at = 21.6 + i * .6, p = lin(t, at, at + .9);
      if (p <= 0) { c.setAttribute('opacity', 0); return; }
      c.setAttribute('opacity', 1);
      const e = ease(p);
      place(c, mix(FROM[i], TO[i][0], e), mix(1250, TO[i][1], e) - Math.sin(Math.PI * p) * 120 + Math.sin(t * 2 + i) * 6 * (p >= 1),
        mix(.7, 1.3, e), (1 - e) * 540 + Math.sin(t * 1.5 + i) * 6);
    });

    // "Trick or tea!"
    const tp = seg(t, 24.4, 25.4);
    el.tea.setAttribute('opacity', t >= 24.4 ? 1 : 0);
    place(el.tea, mix(270, 530, tp), mix(1300, 1450, tp), mix(1, 1.5, tp));
    steam(el.steamTea, t, tp);
    const bb = seg(t, 24.7, 25.0) * (1 - seg(t, 27.6, 28.0));
    place(el.teaBubble, 450, 800, Math.max(bb, .001));
    el.teaBubble.setAttribute('opacity', bb > .01 ? 1 : 0);
  }

  const LYRICS = [[4.8, 9.6, 'かぼちゃのランタン ともして'], [9.6, 14.4, 'おばけのふり お菓子どうぞ'], [14.4, 19.2, 'マントをひらり ひるがえし'], [19.2, 24, 'こわくないよと わらいあう']];

  function render(t) {
    t = clamp(t, 0, DURATION);
    const cut = lin(t, 14.2, 14.6);
    el.sceneA.setAttribute('display', cut >= 1 ? 'none' : 'inline');
    el.sceneB.setAttribute('display', t < 14.2 ? 'none' : 'inline');
    el.sceneB.setAttribute('opacity', cut.toFixed(3));
    if (t < 14.6) renderA(t);
    if (t >= 14.2) renderB(t);

    // Lanterns flicker; Jaga's pumpkin bucket lights up with the first line.
    el.jolGlow.setAttribute('opacity', (.75 + .25 * Math.sin(t * 13) * Math.sin(t * 7.3)).toFixed(3));
    const lit = seg(t, 4.9, 5.4);
    el.bucketGlow.setAttribute('opacity', (lit * (.8 + .2 * Math.sin(t * 11))).toFixed(3));
    el.bucketFace.setAttribute('fill', lit > .5 ? '#ffd45e' : '#7a3a10');

    el.title.setAttribute('opacity', (seg(t, .5, 1.4) * (1 - seg(t, 3.6, 4.5))).toFixed(3));
    const line = LYRICS.find(([a, b]) => t >= a && t < b);
    if (line) {
      if (el.lyric.textContent !== line[2]) el.lyric.textContent = line[2];
      el.lyric.setAttribute('opacity', (seg(t, line[0], line[0] + .35) * (1 - seg(t, line[1] - .35, line[1]))).toFixed(3));
    } else el.lyric.setAttribute('opacity', 0);
    el.endText.setAttribute('opacity', seg(t, 26.4, 27.2).toFixed(3));
    el.fade.setAttribute('opacity', seg(t, 29.0, 30.0).toFixed(3));
  }

  // ---------- Music: spooky-cute swing, 100 BPM, 12 bars ----------
  const CH = {
    Am: [45, [45, 48, 52, 57]], F: [41, [45, 48, 53, 57]], Dm: [38, [45, 50, 53, 57]],
    E: [40, [44, 47, 50, 52]], A: [45, [45, 49, 52, 57]]
  };
  // 2-bar intro, 8-bar chorus (one lyric line per 2 bars), instrumental, and a happy A-major ending.
  const BARS = [
    [['Am', 0, 4]], [['E', 0, 4]],
    [['Am', 0, 4]], [['F', 0, 4]], [['Dm', 0, 4]], [['E', 0, 4]], [['Am', 0, 4]], [['F', 0, 4]], [['Dm', 0, 2], ['E', 2, 2]], [['Am', 0, 4]],
    [['F', 0, 4]], [['A', 0, 6]]
  ];
  const BELL = {
    0: [[0, 81, .5], [.5, 80, .5], [1, 81, .5], [1.5, 76, .5], [2, 72, 1], [3, 69, 1]],
    1: [[0, 80, .5], [.5, 83, .5], [1, 86, 1], [2, 83, .5], [2.5, 80, .5], [3, 76, 1]],
    10: [[0, 81, .5], [.5, 77, .5], [1, 72, .5], [1.5, 77, .5], [2, 81, 1], [3, 84, 1]],
    11: [[0, 81, 1], [1, 85, 1], [2, 88, 3]]
  };
  const HUM = {
    2: [[0, 69, .5], [.5, 72, .5], [1, 76, .5], [1.5, 76, .5], [2, 77, .5], [2.5, 76, .5], [3, 74, .5], [3.5, 72, .5]], // かぼちゃのランタン
    3: [[0, 72, 1], [1, 74, 1], [2, 72, 1], [3, 69, 1]],                                                                // ともして
    4: [[0, 74, .5], [.5, 74, .5], [1, 77, .5], [1.5, 81, .5], [2, 79, 1], [3, 77, 1]],                                 // おばけのふり
    5: [[0, 76, .5], [.5, 76, .5], [1, 80, .5], [1.5, 76, .5], [2, 74, 1], [3, 71, 1]],                                 // お菓子どうぞ
    6: [[0, 76, .5], [.5, 76, .5], [1, 77, .5], [1.5, 76, .5], [2, 81, .5], [2.5, 79, .5], [3, 76, 1]],                 // マントをひらり
    7: [[0, 77, .5], [.5, 76, .5], [1, 74, 1], [2, 72, 1], [3, 69, 1]],                                                 // ひるがえし
    8: [[0, 74, .5], [.5, 74, .5], [1, 77, .5], [1.5, 76, .5], [2, 74, .5], [2.5, 71, .5], [3, 68, 1]],                 // こわくないよと
    9: [[0, 69, .5], [.5, 72, .5], [1, 76, 1], [2, 74, 1], [3, 69, 1]]                                                  // わらいあう
  };
  const SWING = .16; // push offbeat eighths late for a swing feel

  const events = [];
  const add = (bar, beat, type, note = 0, len = 1, vel = 1) =>
    events.push({ t: bar * BAR + beat * BEAT, type, note, dur: len * BEAT, vel });
  BARS.forEach((chords, bar) => {
    const groove = bar >= 2 && bar <= 10;
    chords.forEach(([name, at, len]) => {
      const [root, voicing] = CH[name];
      voicing.forEach((n, i) => add(bar, at + i * .04, 'piano', n, Math.min(len, 4) + 1, (groove ? .4 : .55) - i * .04));
      if (groove) {
        for (let b = 0; b < len; b++) {
          if (b % 2 === 0) add(bar, at + b, 'bass', b === 0 ? root : root + 7, .8, .9);
          else voicing.slice(1).forEach(n => add(bar, at + b, 'pizz', n + 12, .3, .8));
        }
        add(bar, at + len - .5 + SWING, 'pizz', voicing[3] + 12, .25, .55);
      }
    });
    if (groove) {
      add(bar, 0, 'kick', 0, 1, .8); add(bar, 2, 'kick', 0, 1, .7);
      add(bar, 1, 'snap'); add(bar, 3, 'snap');
      for (let s = 0; s < 8; s++) add(bar, s / 2 + (s % 2 ? SWING : 0), 'hat', 0, 1, s % 2 ? .6 : 1);
    }
    if (bar === 11) add(bar, 0, 'kick', 0, 1, .7);
    (BELL[bar] || []).forEach(([b, n, l]) => add(bar, b, 'bell', n, l));
    (HUM[bar] || []).forEach(([b, n, l]) => add(bar, b, 'hum', n, l));
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
        const f = filter('lowpass', 3200), g = envelope(.04 * v, .004, 0, .45);
        f.connect(g); g.connect(out);
        osc('sawtooth', hz(ev.note), f, at + .65, .6); osc('sine', hz(ev.note), f, at + .65);
        break;
      }
      case 'bass': {
        const f = filter('lowpass', 420), g = envelope(.045 * v, .02, ev.dur * .8, .18);
        f.connect(g); g.connect(out);
        const end = at + ev.dur + .3;
        osc('sine', hz(ev.note), f, end); osc('triangle', hz(ev.note), f, end, .45);
        break;
      }
      case 'hum': {
        const f = filter('lowpass', 2400), g = envelope(.055 * v, .05, ev.dur * .9, .2);
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
      case 'bell': {
        const g = envelope(.1 * v, .002, 0, 1.3); g.connect(out);
        const end = at + 1.4;
        osc('sine', hz(ev.note), g, end); osc('sine', hz(ev.note) * 2.76, g, end, .25);
        break;
      }
      case 'pizz': {
        const f = filter('lowpass', 2400), g = envelope(.07 * v, .003, 0, .16); f.connect(g); g.connect(out);
        osc('triangle', hz(ev.note), f, at + .22); osc('sawtooth', hz(ev.note), f, at + .22, .25);
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
    const warm = ctx.createBiquadFilter(); warm.type = 'lowpass'; warm.frequency.value = 11000;
    const comp = ctx.createDynamicsCompressor();
    const master = ctx.createGain(); master.gain.value = MASTER;
    // A fast limiter after the master gain keeps stacked notes from clipping.
    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -6; limiter.knee.value = 0; limiter.ratio.value = 20; limiter.attack.value = .002; limiter.release.value = .1;
    input.connect(warm); warm.connect(comp); comp.connect(master); master.connect(limiter); limiter.connect(ctx.destination);
    return { input, master };
  }

  function scheduleSong(ctx, chain, from, t0) {
    for (const ev of events) if (ev.t >= from - .005) voice(ctx, chain.input, ev, t0 + ev.t - from);
    const vinyl = ctx.createBufferSource(); vinyl.buffer = buffers(ctx).crackle;
    const vf = ctx.createBiquadFilter(); vf.type = 'bandpass'; vf.frequency.value = 2600; vf.Q.value = .5;
    const vg = ctx.createGain(); vg.gain.value = .1;
    vinyl.connect(vf); vf.connect(vg); vg.connect(chain.input); vinyl.start(t0, from);
    const g = chain.master.gain, fadeAt = 28.6;
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
