(() => {
  const DURATION = 30;
  const BPM = 100;
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
  const ASSETS = '../assets/';
  const SPRITE_W = {
    jaga: { front: 345, smile: 345, yawn: 345, side: 343 },
    sakura: { front: 347, smile: 347, side: 349 },
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
  const jagaA = makeChar('jaga-a', 'jaga'), sakuraA = makeChar('sakura-a', 'sakura'), manjuA = makeChar('manju-a', 'manju');

  const el = {
    sceneA: $('scene-a'), sceneB: $('scene-b'), camA: $('cam-a'), camB: $('cam-b'),
    vcupB: $('vcup-b'), steamB: $('steam-b'), can: $('can'), canBody: $('can-body'), drops: $('drops'),
    sillFlowers: $('sill-flowers'), clouds: $('clouds'), door: $('door'), spill: $('spill'), hanky: $('hanky'),
    title: $('title'), lyric: $('lyric'), endText: $('end-text'), fade: $('fade')
  };

  const breath = (t, ph) => [1 - .006 * Math.sin(t * 2.2 + ph), 1 + .014 * Math.sin(t * 2.2 + ph)];
  const blink = (t, times) => times.some(b => t >= b && t < b + .14);
  const cam = (g, [cx, cy, s]) => g.setAttribute('transform', `translate(450 800) scale(${s.toFixed(4)}) translate(${-cx} ${-cy})`);

  function steam(group, t, intensity) {
    [...group.children].forEach((w, i) => {
      const ph = (t * .3 + i / 3) % 1;
      const x = Math.sin(t * 1.1 + i * 2.1) * 6 + (i - 1) * 10;
      w.setAttribute('transform', `translate(${x.toFixed(1)} ${(-74 - ph * 85).toFixed(1)}) scale(${(.55 + ph * .5).toFixed(3)})`);
      w.setAttribute('opacity', (Math.sin(Math.PI * ph) * intensity * .55).toFixed(3));
    });
  }

  // ---------- Scene B: the morning living room (0–16s) ----------
  const CAM_B = [
    [0, 760, 1220, 1.4], [3.6, 690, 1250, 1.5], [7.4, 620, 1250, 1.5], [8.4, 420, 1160, 1.6], [10.6, 450, 1170, 1.7],
    [11.6, 690, 1040, 1.5], [14.6, 650, 1080, 1.4], [16.2, 450, 1100, 1.25]
  ];
  const H = 260;

  function renderB(t) {
    cam(el.camB, keyed(t, CAM_B));
    el.clouds.setAttribute('transform', `translate(${(t * 4).toFixed(1)} 0)`);

    // JAGA shuffles in half asleep, then a big yawn.
    const [jbx, jby] = breath(t, 1);
    if (t < 4) {
      const p = lin(t, .4, 3.8), step = Math.abs(Math.sin(p * Math.PI * 5));
      jaga({ sprite: 'side', flip: -1, x: mix(1150, 690, ease(p)), y: 1440 - step * 14, h: H, rot: Math.sin(t * 2.4) * 5, sy: 1 - .03 * step });
    } else {
      const y = lin(t, 4.1, 6.3), yawning = t >= 4.25 && t < 6.1;
      const sprite = yawning ? 'yawn' : (t >= 6.1 && t < 7.4) || (t >= 10.6 && t < 12) || blink(t, [8.9, 13.6, 15.1]) ? 'smile' : 'front';
      jaga({ sprite, x: 690, y: 1440, h: H, sx: jbx - .03 * Math.sin(Math.PI * y), sy: jby + .09 * Math.sin(Math.PI * y), rot: -3 * Math.sin(Math.PI * y) });
    }

    // MANJU offers a steaming cup.
    const [mbx, mby] = breath(t, 4.1);
    const lean = seg(t, 8.6, 9.3) - seg(t, 10.6, 11.3);
    manju({ sprite: lean > .3 || t >= 11.3 || blink(t, [2.2, 5.6]) ? 'smile' : 'front', x: 300 + 50 * lean, y: 1150, h: H, rot: 8 * lean, sx: mbx, sy: mby });
    const vp = seg(t, 9.0, 10.0);
    el.vcupB.setAttribute('transform', `translate(${mix(430, 450, vp).toFixed(1)} ${mix(1160, 1212, vp).toFixed(1)}) scale(${(1 + .15 * vp).toFixed(3)})`);
    steam(el.steamB, t, 1);

    // SAKURA waters the flowers on the windowsill.
    const [sbx, sby] = breath(t, 2.3);
    if (t < 8.2) {
      sakura({ sprite: blink(t, [3.1, 6.4]) ? 'smile' : 'front', x: 600, y: 1150, h: H, sx: sbx, sy: sby });
    } else if (t < 9.4) {
      const p = lin(t, 8.2, 9.4);
      sakura({ sprite: 'side', x: mix(600, 700, ease(p)), y: mix(1150, 958, ease(p)) - Math.abs(Math.sin(2 * Math.PI * p)) * 38, h: H });
    } else {
      sakura({ sprite: (t >= 10.2 && t < 13.8) || t >= 14.6 ? 'smile' : 'front', x: 700, y: 958, h: H, sx: sbx, sy: sby });
    }
    const tilt = 28 * (seg(t, 10.0, 10.6) - seg(t, 13.6, 14.2));
    el.can.setAttribute('opacity', (seg(t, 9.4, 9.7) * (1 - seg(t, 14.6, 15.0))).toFixed(3));
    el.can.setAttribute('transform', 'translate(735 862)');
    el.canBody.setAttribute('transform', `rotate(${tilt.toFixed(2)})`);
    const a = tilt * Math.PI / 180, tipX = 60 * Math.cos(a) + 35 * Math.sin(a), tipY = 60 * Math.sin(a) - 35 * Math.cos(a);
    [...el.drops.children].forEach((d, i) => {
      const ph = (t * 1.8 + i / 4) % 1;
      d.setAttribute('cx', (tipX + 6 * ph + (i % 2) * 4).toFixed(1));
      d.setAttribute('cy', (tipY + ph * ph * 48).toFixed(1));
      d.setAttribute('opacity', tilt > 18 ? (1 - ph * .6).toFixed(2) : 0);
    });
    const perk = 1 + .07 * seg(t, 11.0, 12.6), sway = Math.sin(t * 1.8) * 2;
    el.sillFlowers.setAttribute('transform', `translate(816 952) rotate(${sway.toFixed(2)}) scale(1 ${perk.toFixed(3)}) translate(-816 -952)`);
  }

  // ---------- Scene A: seeing you off at the front door (16–30s) ----------
  const CAM_A = [[15.6, 450, 1150, 1.3], [18.4, 450, 1150, 1.3], [19.6, 420, 1180, 1.35], [22.6, 450, 1150, 1.35], [24.2, 450, 1020, 1.12], [30, 450, 1000, 1.1]];
  const HA = 300;

  function renderA(t) {
    cam(el.camA, keyed(t, CAM_A));
    const wave = seg(t, 25.4, 25.9), wv = Math.sin((t - 25.4) * Math.PI * 2.8);

    const [mbx, mby] = breath(t, .7);
    manjuA({ sprite: (t >= 17.4 && t < 18.2) || t >= 21 || blink(t, [19.3]) ? 'smile' : 'front', x: 200, y: 1330, h: HA, sx: mbx, sy: mby, rot: 7 * wv * wave });

    const [sbx, sby] = breath(t, 2.9);
    const looking = t >= 18.0 && t < 19.8;
    sakuraA({ sprite: looking ? 'side' : t >= 21 || blink(t, [16.9]) ? 'smile' : 'front', flip: looking ? -1 : 1, x: 700, y: 1330, h: HA, sx: sbx, sy: sby, rot: -7 * wv * wave });

    // JAGA runs in with the forgotten handkerchief.
    let hx = -400, hy = 0, hs = 1, hr = 0, ho = 0;
    if (t < 20.4) {
      const p = lin(t, 18.8, 20.4);
      const x = mix(-180, 450, ease(p)), y = 1340 - Math.abs(Math.sin(p * Math.PI * 6)) * 26;
      jagaA({ sprite: 'side', x, y, h: HA, rot: 6 });
      hx = x + 50; hy = y - HA - 10; hr = Math.sin(t * 12) * 14; ho = t >= 18.8 ? 1 : 0;
    } else {
      const hop = Math.sin(Math.PI * lin(t, 20.6, 21.0)) * 30 + (t >= 25.4 ? Math.abs(Math.sin((t - 25.4) * Math.PI * 1.4)) * 14 * wave : 0);
      const [jbx, jby] = breath(t, 1.6);
      jagaA({ sprite: t >= 20.4 && t < 21.2 || t >= 22.4 ? 'smile' : 'front', x: 450, y: 1340 - hop, h: HA, sx: jbx, sy: jby });
      const fly = seg(t, 21.2, 22.6);
      hx = 450; hy = mix(1340 - HA - 30 - hop, 900, fly); hs = mix(1, 7, fly * fly); hr = Math.sin(t * 10) * 10 * (1 - fly);
      ho = 1 - lin(t, 22.0, 22.6);
    }
    el.hanky.setAttribute('transform', `translate(${hx.toFixed(1)} ${hy.toFixed(1)}) rotate(${hr.toFixed(2)}) scale(${hs.toFixed(3)})`);
    el.hanky.setAttribute('opacity', ho.toFixed(3));

    // The door opens onto the morning.
    const open = seg(t, 24.0, 25.6);
    el.door.setAttribute('transform', `translate(314 0) scale(${mix(1, .06, open).toFixed(4)} 1) translate(-314 0)`);
    el.spill.setAttribute('opacity', seg(t, 24.2, 25.8).toFixed(3));
  }

  const LYRICS = [[14.4, 19.2, 'ねぼけた顔でも いいよ'], [19.2, 24, 'ひとくち飲んだら 歩き出そう'], [24, 26.6, 'いってらっしゃい ここで待ってる']];

  function render(t) {
    t = clamp(t, 0, DURATION);
    const crossfade = lin(t, 15.6, 16.2);
    el.sceneB.setAttribute('display', crossfade >= 1 ? 'none' : 'inline');
    el.sceneA.setAttribute('display', t < 15.6 ? 'none' : 'inline');
    el.sceneA.setAttribute('opacity', crossfade.toFixed(3));
    if (t < 16.2) renderB(t);
    if (t >= 15.6) renderA(t);

    el.title.setAttribute('opacity', (seg(t, .4, 1.4) * (1 - seg(t, 3.6, 4.6))).toFixed(3));
    const line = LYRICS.find(([a, b]) => t >= a && t < b);
    if (line) {
      if (el.lyric.textContent !== line[2]) el.lyric.textContent = line[2];
      el.lyric.setAttribute('opacity', (seg(t, line[0], line[0] + .35) * (1 - seg(t, line[1] - .35, line[1]))).toFixed(3));
    } else el.lyric.setAttribute('opacity', 0);
    el.endText.setAttribute('opacity', seg(t, 26.8, 27.6).toFixed(3));
    el.fade.setAttribute('opacity', seg(t, 29.0, 30.0).toFixed(3));
  }

  // ---------- Music: bright acoustic pop, 100 BPM, 12 bars ----------
  const CH = {
    C: [36, [48, 52, 55, 60]], G: [43, [47, 50, 55, 59]], Am: [45, [45, 48, 52, 57]], F: [41, [45, 48, 53, 57]]
  };
  const BARS = [
    [['C', 0, 4]], [['G', 0, 4]], [['Am', 0, 2], ['F', 2, 2]], [['C', 0, 4]], [['G', 0, 4]], [['F', 0, 2], ['G', 2, 2]],
    [['C', 0, 4]], [['G', 0, 4]], [['Am', 0, 4]], [['F', 0, 4]], [['F', 0, 2], ['G', 2, 2]], [['C', 0, 6]]
  ];
  const BELL = {
    0: [[0, 79, .5], [.5, 84, .5], [1, 88, 1], [3, 86, .5], [3.5, 84, .5]], 1: [[0, 83, 1.5], [2, 79, 1], [3, 81, 1]],
    2: [[0, 84, 2], [2, 81, 2]], 11: [[0, 84, 1], [1, 88, 1], [2, 91, 3]]
  };
  const PIANO_LINE = {
    3: [[0, 72, 1], [1, 76, 1], [2, 79, 2]], 4: [[0, 74, 1], [1, 79, 1], [2, 83, 2]], 5: [[0, 81, 1], [1, 77, 1], [2, 79, 2]]
  };
  const HUM = {
    6: [[0, 76, .5], [.5, 76, .5], [1, 77, .5], [1.5, 79, 1.5], [3, 76, 1]],
    7: [[0, 74, 1], [1, 74, .5], [1.5, 76, .5], [2, 74, 2]],
    8: [[0, 72, .5], [.5, 74, .5], [1, 76, .5], [1.5, 79, .5], [2, 81, 1], [3, 79, 1]],
    9: [[0, 77, .5], [.5, 76, .5], [1, 74, 1], [2, 72, 2]],
    10: [[0, 81, .5], [.5, 79, .5], [1, 77, .5], [1.5, 76, .5], [2, 74, 1], [3, 79, 1]],
    11: [[0, 76, 1], [1, 74, .5], [1.5, 74, .5], [2, 72, 2]]
  };

  const events = [];
  const add = (bar, beat, type, note = 0, len = 1, vel = 1) =>
    events.push({ t: bar * BAR + beat * BEAT, type, note, dur: len * BEAT, vel });
  BARS.forEach((chords, bar) => {
    const groove = bar >= 3 && bar <= 10, chorus = bar >= 6 && bar <= 10;
    chords.forEach(([name, at, len]) => {
      const [root, voicing] = CH[name];
      voicing.forEach((n, i) => add(bar, at + i * .04, 'piano', n, Math.min(len, 4) + 1, .7 - i * .05));
      if (len === 4 && groove) voicing.slice(2).forEach(n => add(bar, 2.5, 'piano', n, 1.5, .4));
      if (bar >= 3) {
        add(bar, at, 'bass', root, Math.min(len, 4) * .9);
        if (len === 4 && bar < 11) add(bar, at + 2, 'bass', root, 1.6, .8);
      }
      if (groove) [0, 1, 1.5, 2.5, 3, 3.5].filter(b => b < len).forEach(b =>
        voicing.forEach((n, i) => add(bar, at + b + i * .02, 'guitar', n + 12, .5, b % 1 ? .45 : .65)));
    });
    if (groove) {
      add(bar, 0, 'kick'); add(bar, 2, 'kick');
      if (chorus) add(bar, 2.5, 'kick', 0, 1, .6);
      add(bar, 1, 'snap'); add(bar, 3, 'snap');
      for (let s = 0; s < 8; s++) add(bar, s / 2, 'hat', 0, 1, s % 2 ? .7 : 1);
    }
    if (bar === 11) add(bar, 0, 'kick', 0, 1, .6);
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
