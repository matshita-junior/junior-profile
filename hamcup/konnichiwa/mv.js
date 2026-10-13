(() => {
  const DURATION = 30;
  const BPM = 110;
  const BEAT = 60 / BPM;
  const BAR = BEAT * 4;
  const MASTER = 1.75;

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
    jaga: { front: 345, smile: 345, side: 343 },
    sakura: { front: 347, smile: 347 },
    manju: { front: 337, smile: 337 }
  };
  const SPRITE_H = 440;

  function makeChar(id, name) {
    const g = $(id);
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
    return function set({ sprite, x, y, h, flip = 1, rot = 0, sx = 1, sy = 1 }) {
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
      g.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${rot.toFixed(2)}) scale(${(flip * sx).toFixed(4)} ${sy.toFixed(4)})`);
    };
  }

  const jaga = makeChar('jaga', 'jaga'), sakura = makeChar('sakura', 'sakura'), manju = makeChar('manju', 'manju');
  const el = {
    cam: $('cam'), clouds: $('clouds'), leaves: $('leaves'), sketch: $('sketch'), sketchBook: $('sketch-book'),
    sketchLine: $('sketch-line'), sketchFlower: $('sketch-flower'), sketchFriends: $('sketch-friends'), pencil: $('pencil'),
    basket: $('basket'), bubble: $('bubble'), glass: $('glass-you'),
    cups: [$('cup-manju'), $('cup-sakura'), $('cup-jaga')], oni: [$('oni1'), $('oni2'), $('oni3')],
    title: $('title'), lyric: $('lyric'), endText: $('end-text'), fade: $('fade')
  };

  const breath = (t, ph) => [1 - .006 * Math.sin(t * 2.2 + ph), 1 + .014 * Math.sin(t * 2.2 + ph)];
  const blink = (t, times) => times.some(b => t >= b && t < b + .14);
  const place = (node, x, y, s = 1, r = 0) => node.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${r.toFixed(2)}) scale(${s.toFixed(3)})`);
  const pop = (t, at) => { const p = lin(t, at, at + .35); return p <= 0 ? 0 : 1 + .25 * Math.sin(Math.PI * p) * (1 - p) + 0 * p; };

  // ---------- The picnic under the tree ----------
  const CAM = [
    [0, 450, 640, 1.15], [3.6, 450, 1120, 1.3], [5, 620, 1110, 1.6], [7.6, 640, 1110, 1.6], [8.4, 820, 1160, 1.4],
    [11.4, 470, 1170, 1.4], [12.6, 380, 1240, 1.6], [15.4, 450, 1260, 1.45], [16.6, 450, 1080, 1.3], [19.2, 450, 1080, 1.3],
    [20.0, 620, 1110, 1.5], [21.6, 620, 1110, 1.5], [22.2, 410, 1260, 1.6], [23.4, 410, 1260, 1.6], [24.6, 450, 1060, 1.2], [30, 450, 990, 1.1]
  ];
  const H = 260;
  const MANJU = [270, 1215], SAKURA = [630, 1200], JAGA = [450, 1180];
  const LYRICS = [[6 * BAR, 8 * BAR, 'こんにちは ひなたの中で'], [8 * BAR, 10 * BAR, 'いっしょに ひと休みしよう'], [10 * BAR, 12 * BAR, 'きみの席も ちゃんとあるよ']];

  function render(t) {
    t = clamp(t, 0, DURATION);
    const [cx, cy, s] = keyed(t, CAM);
    el.cam.setAttribute('transform', `translate(450 800) scale(${s.toFixed(4)}) translate(${-cx} ${-cy})`);
    el.clouds.setAttribute('transform', `translate(${(t * 5).toFixed(1)} 0)`);
    [...el.leaves.children].forEach((lf, i) => {
      const x = ((i * 190 + t * (34 + i * 9)) % 1250) - 175;
      const y = 380 + i * 150 + Math.sin(t * 1.3 + i) * 40 + t * 5;
      place(lf, x, y, 1.4, t * 70 + i * 40);
    });

    const greet = t >= 16.4, wave = seg(t, 24.6, 25.1);
    const waveRot = ph => 7 * Math.sin((t - 24.6) * Math.PI * 2.6 + ph) * wave;

    // SAKURA sketches flowers, then shows a drawing of everyone — including you.
    const [sbx, sby] = breath(t, 2.3);
    sakura({ sprite: greet && !blink(t, [21.0]) || (t >= 8 && t < 8.6) || blink(t, [2.6, 11.8]) ? 'smile' : 'front', x: SAKURA[0], y: SAKURA[1], h: H, sx: sbx, sy: sby, rot: waveRot(1.5) });
    const flipP = lin(t, 19.2, 20.1), raise = seg(t, 19.2, 20.0) - seg(t, 22.8, 23.6);
    el.sketchFlower.setAttribute('visibility', flipP < .5 ? 'visible' : 'hidden');
    el.sketchFriends.setAttribute('visibility', flipP < .5 ? 'hidden' : 'visible');
    el.sketchBook.setAttribute('transform', `scale(${Math.abs(Math.cos(Math.PI * flipP)).toFixed(3)} 1)`);
    place(el.sketch, SAKURA[0], SAKURA[1] - 92 - 60 * raise, .85 + .5 * raise, waveRot(1.5) * .5);
    el.sketchLine.setAttribute('stroke-dashoffset', (260 * (1 - lin(t, 4.4, 8.2))).toFixed(1));
    const drawing = t < 9;
    el.pencil.setAttribute('opacity', drawing ? 1 : 0);
    el.pencil.setAttribute('transform', `translate(${(Math.sin(t * 7) * 22).toFixed(1)} ${(Math.cos(t * 5) * 14 + 6).toFixed(1)})`);

    // JAGA carries the big basket in, then pops out the onigiri.
    const [jbx, jby] = breath(t, 1);
    let bx, by, bs = .8;
    if (t < 11.5) {
      const p = lin(t, 8.2, 11.4), step = Math.abs(Math.sin(p * Math.PI * 6));
      const x = mix(1150, JAGA[0], ease(p)), y = JAGA[1] - step * 16;
      jaga({ sprite: 'side', flip: -1, x, y, h: H, rot: Math.sin(t * 6) * 3 });
      bx = x - 10; by = y - H - 20 + Math.sin(t * 6) * 4;
    } else {
      const hop = Math.abs(Math.sin(Math.PI * 2 * lin(t, 16.8, 17.8))) * 26 + Math.abs(Math.sin((t - 24.6) * Math.PI * 1.3)) * 16 * wave;
      const sprite = (t >= 12.4 && t < 13.8) || greet ? (blink(t, [26.4]) ? 'front' : 'smile') : blink(t, [14.6]) ? 'smile' : 'front';
      jaga({ sprite, x: JAGA[0], y: JAGA[1] - hop, h: H, sx: jbx, sy: jby, rot: waveRot(0) });
      const p = seg(t, 11.5, 12.3);
      bx = mix(JAGA[0] - 10, 350, p); by = mix(JAGA[1] - H - 20, 1268, p); bs = .8;
    }
    place(el.basket, bx, by, bs);

    const ONI = [[300, 1322], [392, 1340], [530, 1332]];
    el.oni.forEach((o, i) => {
      const at = 12.4 + i * .35, p = lin(t, at, at + .6);
      if (p <= 0) { o.setAttribute('opacity', 0); return; }
      o.setAttribute('opacity', 1);
      place(o, mix(350, ONI[i][0], p), mix(1230, ONI[i][1], p) - Math.sin(Math.PI * p) * 90, .9, (1 - p) * 360);
    });

    // MANJU lays out the drinks and slides the iced tea toward you.
    const [mbx, mby] = breath(t, 4.1);
    const lean = Math.max(seg(t, 12.6, 13.2) - seg(t, 14.4, 15.0), seg(t, 21.8, 22.4) - seg(t, 23.0, 23.6));
    manju({ sprite: lean > .3 || greet || blink(t, [3.4, 9.7]) ? 'smile' : 'front', x: MANJU[0] + 40 * lean, y: MANJU[1], h: H, rot: 8 * lean + waveRot(3), sx: mbx, sy: mby });
    const CUP = [[200, 1252, 12.8], [722, 1240, 13.2], [548, 1218, 13.6]];
    el.cups.forEach((c, i) => { const k = pop(t, CUP[i][2]); c.setAttribute('opacity', k > 0 ? 1 : 0); place(c, CUP[i][0], CUP[i][1], Math.max(k, .001)); });
    const g1 = seg(t, 14.4, 15.2), g2 = seg(t, 21.9, 22.8);
    const gk = pop(t, 14.0);
    el.glass.setAttribute('opacity', gk > 0 ? 1 : 0);
    place(el.glass, 450, mix(mix(1290, 1352, g1), 1398, g2), Math.max(gk, .001) * (1 + .25 * g2));

    // "こんにちは！"
    const bub = seg(t, 17.0, 17.3) * (1 - seg(t, 19.8, 20.2));
    place(el.bubble, JAGA[0], 850 + 10 * Math.sin(t * 3), Math.max(bub, .001) * (1 + .08 * Math.sin(Math.PI * lin(t, 17.0, 17.4))));
    el.bubble.setAttribute('opacity', bub > .01 ? 1 : 0);

    el.title.setAttribute('opacity', (seg(t, .4, 1.4) * (1 - seg(t, 3.6, 4.6))).toFixed(3));
    const line = LYRICS.find(([a, b]) => t >= a && t < b);
    if (line) {
      if (el.lyric.textContent !== line[2]) el.lyric.textContent = line[2];
      el.lyric.setAttribute('opacity', (seg(t, line[0], line[0] + .35) * (1 - seg(t, line[1] - .35, line[1]))).toFixed(3));
    } else el.lyric.setAttribute('opacity', 0);
    el.endText.setAttribute('opacity', seg(t, 26.6, 27.4).toFixed(3));
    el.fade.setAttribute('opacity', seg(t, 29.0, 30.0).toFixed(3));
  }

  // ---------- Music: sunny pop, 110 BPM, 13 bars ----------
  const CH = {
    G: [43, [47, 50, 55, 59]], D: [38, [50, 54, 57, 62]], Em: [40, [52, 55, 59, 64]], C: [36, [48, 52, 55, 60]]
  };
  const BARS = [
    [['G', 0, 4]], [['D', 0, 4]], [['Em', 0, 2], ['C', 2, 2]], [['G', 0, 4]], [['D', 0, 4]], [['C', 0, 2], ['D', 2, 2]],
    [['G', 0, 4]], [['D', 0, 4]], [['Em', 0, 4]], [['C', 0, 4]], [['C', 0, 2], ['D', 2, 2]], [['G', 0, 4]], [['G', 0, 6]]
  ];
  const BELL = {
    0: [[0, 79, .5], [.5, 83, .5], [1, 86, 1], [2.5, 83, .5], [3, 86, 1]], 1: [[0, 86, 1], [1, 81, 1], [2, 78, 2]],
    2: [[0, 83, 1], [1, 79, 1], [2, 84, 1], [3, 83, 1]], 12: [[0, 86, 1], [1, 91, 3]]
  };
  const PIANO_LINE = {
    3: [[0, 71, 1], [1, 74, 1], [2, 79, 2]], 4: [[0, 78, 1], [1, 74, 1], [2, 69, 2]], 5: [[0, 72, 1], [1, 76, 1], [2, 74, 1], [3, 78, 1]]
  };
  const HUM = {
    6: [[0, 74, .5], [.5, 74, .5], [1, 76, .5], [1.5, 79, 1], [2.5, 78, .5], [3, 79, 1]],
    7: [[0, 81, 1], [1, 78, .5], [1.5, 76, .5], [2, 74, 2]],
    8: [[0, 76, .5], [.5, 76, .5], [1, 79, .5], [1.5, 83, 1], [2.5, 81, .5], [3, 79, 1]],
    9: [[0, 76, 1], [1, 79, .5], [1.5, 76, .5], [2, 74, 2]],
    10: [[0, 72, .5], [.5, 74, .5], [1, 76, .5], [1.5, 79, .5], [2, 78, 1], [3, 81, 1]],
    11: [[0, 79, 1], [1, 78, .5], [1.5, 76, .5], [2, 79, 2]]
  };

  const events = [];
  const add = (bar, beat, type, note = 0, len = 1, vel = 1) =>
    events.push({ t: bar * BAR + beat * BEAT, type, note, dur: len * BEAT, vel });
  BARS.forEach((chords, bar) => {
    const groove = bar >= 3 && bar <= 11, chorus = bar >= 6 && bar <= 11;
    chords.forEach(([name, at, len]) => {
      const [root, voicing] = CH[name];
      voicing.forEach((n, i) => add(bar, at + i * .04, 'piano', n, Math.min(len, 4) + 1, .6 - i * .05));
      if (bar >= 3) {
        add(bar, at, 'bass', root, Math.min(len, 4) * .45);
        if (len === 4 && bar < 12) { add(bar, at + 1.5, 'bass', root, .4, .7); add(bar, at + 2, 'bass', root + 7, 1.4, .8); }
      }
      if (groove) for (let s = 0; s < Math.min(len, 4) * 2; s++)
        add(bar, at + s / 2, 'guitar', voicing[[0, 2, 1, 3, 2, 1, 3, 2][s % 8]] + 12, .4, s % 2 ? .5 : .75);
    });
    if (groove) {
      add(bar, 0, 'kick'); add(bar, 2, 'kick');
      if (chorus) add(bar, 1.5, 'kick', 0, 1, .55);
      add(bar, 1, 'snap'); add(bar, 3, 'snap');
      if (chorus) add(bar, 3.5, 'snap', 0, 1, .5);
      for (let s = 0; s < 8; s++) add(bar, s / 2, 'hat', 0, 1, s % 2 ? .7 : 1);
    }
    if (bar === 12) add(bar, 0, 'kick', 0, 1, .6);
    (BELL[bar] || []).forEach(([b, n, l]) => add(bar, b, 'bell', n, l));
    (PIANO_LINE[bar] || []).forEach(([b, n, l]) => add(bar, b, 'piano', n, l + .5, .65));
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
    input.connect(warm); warm.connect(comp); comp.connect(master); master.connect(ctx.destination);
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
