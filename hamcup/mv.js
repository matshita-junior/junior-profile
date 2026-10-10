(() => {
  const BPM = 120;
  const BEAT = 60 / BPM;
  const BAR = BEAT * 4;
  const BARS = 32;
  const DURATION = BARS * BAR;

  // Song structure: 4 intro + 8 verse A + 8 verse B + 8 chorus + 4 outro bars.
  const PROG = [
    'C', 'G', 'Am', 'F',
    'C', 'G', 'Am', 'F', 'C', 'G', 'Am', 'F',
    'F', 'G', 'Em', 'Am', 'F', 'G', 'C', 'C',
    'C', 'G', 'Am', 'F', 'F', 'G', 'C', 'C',
    'F', 'G', 'C', 'C'
  ];
  const CHORDS = { C: [48, 4], G: [43, 4], Am: [45, 3], F: [41, 4], Em: [40, 3] };
  const section = bar => bar < 4 ? 'intro' : bar < 12 ? 'verseA' : bar < 20 ? 'verseB' : bar < 28 ? 'chorus' : 'outro';

  // Melody as [beat, midi, length in beats] per bar.
  const M = {
    c1: [[0, 76, .5], [.5, 79, .5], [1, 79, 1], [2, 81, .5], [2.5, 79, .5], [3, 76, 1]],
    g1: [[0, 74, 1], [1, 74, .5], [1.5, 76, .5], [2, 74, 1], [3, 71, 1]],
    a1: [[0, 72, .5], [.5, 76, .5], [1, 81, 1], [2, 79, .5], [2.5, 76, .5], [3, 72, 1]],
    f1: [[0, 74, 1.5], [1.5, 72, .5], [2, 69, 2]],
    f1b: [[0, 74, 1], [1, 76, 1], [2, 79, 2]],
    f2: [[0, 69, .5], [.5, 72, .5], [1, 77, 1], [2, 77, .5], [2.5, 76, .5], [3, 72, 1]],
    g2: [[0, 71, .5], [.5, 74, .5], [1, 79, 1], [2, 79, .5], [2.5, 77, .5], [3, 74, 1]],
    e2: [[0, 79, 1], [1, 76, .5], [1.5, 79, .5], [2, 83, 1], [3, 79, 1]],
    a2: [[0, 81, 2], [2, 76, 1], [3, 72, 1]],
    c2: [[0, 76, 1], [1, 79, 1], [2, 84, 2]],
    pickup: [[2, 79, .5], [2.5, 81, .5], [3, 83, 1]],
    c3: [[0, 84, 1], [1, 84, .5], [1.5, 83, .5], [2, 84, 1], [3, 79, 1]],
    g3: [[0, 83, 1], [1, 81, .5], [1.5, 79, .5], [2, 86, 2]],
    a3: [[0, 84, 1], [1, 83, .5], [1.5, 81, .5], [2, 76, 1], [3, 81, 1]],
    f3: [[0, 81, 1.5], [1.5, 79, .5], [2, 77, 1], [3, 76, 1]],
    f4: [[0, 77, .5], [.5, 81, .5], [1, 84, 1], [2, 84, .5], [2.5, 86, .5], [3, 84, 1]],
    g4: [[0, 83, 1], [1, 81, 1], [2, 83, 1], [3, 86, 1]],
    end: [[0, 84, 4]]
  };
  const MELODY = {
    4: 'c1', 5: 'g1', 6: 'a1', 7: 'f1', 8: 'c1', 9: 'g1', 10: 'a1', 11: 'f1b',
    12: 'f2', 13: 'g2', 14: 'e2', 15: 'a2', 16: 'f2', 17: 'g2', 18: 'c2', 19: 'pickup',
    20: 'c3', 21: 'g3', 22: 'a3', 23: 'f3', 24: 'f4', 25: 'g4', 26: 'end'
  };

  const LYRICS = [
    [4, 'ちいさなカップの中で'], [6, 'まるまる夢を見てた'], [8, 'ふたを開けたら 朝の光'], [10, 'ひげが ぴくっと動いた'],
    [12, 'お城の坂道 ころころと'], [14, '知らない景色へ 転がってく'], [16, 'ほっぺにつめた 好奇心'], [18, '今日もひとつ 挑戦だ'],
    [20, 'ハムカップ！ ぴょんと飛び出せ'], [22, 'ハムカップ！ 世界はひろい'], [24, 'ちいさくたって かまわない'], [26, 'きみも 星になれるさ']
  ];

  const events = [];
  const add = (bar, beat, type, note, len = 1, vel = 1) =>
    events.push({ t: (bar * 4 + beat) * BEAT, type, note, dur: len * BEAT, vel });

  for (let bar = 0; bar < BARS; bar++) {
    const sec = section(bar);
    const [root, third] = CHORDS[PROG[bar]];
    const triad = [root, root + third, root + 7];

    if (bar < 31) {
      const len = bar === 30 ? 8 : 4;
      [triad[1] + 12, triad[2] + 12, root + 24].forEach(n => add(bar, 0, 'pad', n, len));
    }

    if ((sec === 'intro' || sec === 'outro') && bar < 30) {
      const tones = [root + 24, root + 24 + third, root + 31, root + 36];
      [0, 1, 2, 3, 2, 1, 0, 1].forEach((i, step) => add(bar, step / 2, 'pluck', tones[i], .5));
    }

    if (sec === 'verseA' || sec === 'verseB') {
      for (let b = 0; b < 4; b++) add(bar, b, 'bass', root, .9);
    } else if (sec === 'chorus') {
      for (let s = 0; s < 8; s++) add(bar, s / 2, 'bass', s % 2 ? root + 12 : root, .45);
    } else if (sec === 'outro') {
      if (bar < 30) { add(bar, 0, 'bass', root, 2); add(bar, 2, 'bass', root, 2); }
      else if (bar === 30) add(bar, 0, 'bass', root, 8);
    }

    if (sec === 'intro' && bar === 3) {
      for (let s = 4; s < 8; s++) add(bar, s / 2, 'snare', 0, .5, .4 + s * .08);
    }
    if (sec === 'verseA' || sec === 'verseB' || sec === 'chorus') {
      add(bar, 0, 'kick'); add(bar, 2, 'kick');
      if (sec === 'chorus') add(bar, 1.5, 'kick', 0, 1, .7);
      if (sec !== 'verseA') { add(bar, 1, 'snare'); add(bar, 3, 'snare'); }
      for (let s = 0; s < 8; s++) add(bar, s / 2, 'hat', 0, 1, s % 2 ? .6 : 1);
    }
    if (sec === 'outro' && bar < 30) { add(bar, 0, 'kick'); add(bar, 2, 'kick', 0, 1, .7); }
    if (bar === 20 || bar === 28) add(bar, 0, 'crash');
    if (bar === 30) { add(bar, 0, 'kick'); add(bar, 0, 'crash'); }

    if (MELODY[bar]) M[MELODY[bar]].forEach(([beat, note, len]) => add(bar, beat, 'lead', note, len));
  }
  events.sort((a, b) => a.t - b.t);

  // ---------- Audio ----------
  const AC = window.AudioContext || window.webkitAudioContext;
  let ctx = null, out = null, noise = null, bus = null, timer = null, cursor = 0, startAt = 0;
  const hz = n => 440 * Math.pow(2, (n - 69) / 12);

  function initAudio() {
    if (ctx || !AC) return;
    ctx = new AC();
    out = ctx.createDynamicsCompressor();
    out.connect(ctx.destination);
    noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const data = noise.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  }

  function env(t, peak, attack, hold, release) {
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(peak, t + attack);
    g.gain.setValueAtTime(peak, t + Math.max(attack, hold));
    g.gain.exponentialRampToValueAtTime(0.0001, t + Math.max(attack, hold) + release);
    return g;
  }

  function osc(type, freq, t, end, dest, detune = 0) {
    const o = ctx.createOscillator();
    o.type = type; o.frequency.setValueAtTime(freq, t); o.detune.value = detune;
    o.connect(dest); o.start(t); o.stop(end);
    return o;
  }

  function noiseHit(t, freq, peak, decay) {
    const src = ctx.createBufferSource();
    const f = ctx.createBiquadFilter();
    f.type = 'highpass'; f.frequency.value = freq;
    const g = env(t, peak, .002, 0, decay);
    src.buffer = noise; src.connect(f); f.connect(g); g.connect(bus);
    src.start(t); src.stop(t + decay + .05);
  }

  function voice(ev, t) {
    const v = ev.vel;
    switch (ev.type) {
      case 'pad': {
        const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 1300;
        const g = env(t, .035 * v, .12, ev.dur, .4); f.connect(g); g.connect(bus);
        osc('sawtooth', hz(ev.note), t, t + ev.dur + .5, f, -7);
        osc('sawtooth', hz(ev.note), t, t + ev.dur + .5, f, 7);
        break;
      }
      case 'pluck': {
        const g = env(t, .1 * v, .005, 0, .4); g.connect(bus);
        osc('triangle', hz(ev.note), t, t + .5, g);
        break;
      }
      case 'lead': {
        const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 2600;
        const g = env(t, .07 * v, .015, ev.dur * .85, .12); f.connect(g); g.connect(bus);
        osc('square', hz(ev.note), t, t + ev.dur + .2, f);
        osc('triangle', hz(ev.note + 12), t, t + ev.dur + .2, f);
        break;
      }
      case 'bass': {
        const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 520;
        const g = env(t, .22 * v, .01, ev.dur * .8, .1); f.connect(g); g.connect(bus);
        osc('sawtooth', hz(ev.note), t, t + ev.dur + .15, f);
        break;
      }
      case 'kick': {
        const g = env(t, .9 * v, .002, 0, .32); g.connect(bus);
        const o = osc('sine', 140, t, t + .4, g);
        o.frequency.exponentialRampToValueAtTime(42, t + .12);
        break;
      }
      case 'snare': {
        noiseHit(t, 1300, .32 * v, .18);
        const g = env(t, .16 * v, .002, 0, .1); g.connect(bus);
        osc('triangle', 190, t, t + .15, g);
        break;
      }
      case 'hat': noiseHit(t, 7500, .07 * v, .05); break;
      case 'crash': noiseHit(t, 4000, .14 * v, 1.6); break;
    }
  }

  function schedule() {
    const horizon = ctx.currentTime + .25;
    while (cursor < events.length && events[cursor].t + startAt < horizon) {
      voice(events[cursor], events[cursor].t + startAt);
      cursor++;
    }
  }

  // ---------- Playback state ----------
  const stage = document.getElementById('stage');
  const lyricEl = document.getElementById('lyric');
  const bob = document.getElementById('bob');
  const town = document.getElementById('town');
  const toggle = document.getElementById('toggle');
  const bigPlay = document.getElementById('big-play');
  const seek = document.getElementById('seek');
  const timeEl = document.getElementById('time');
  const note = document.getElementById('player-note');
  const fullscreen = document.getElementById('fullscreen');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  let playing = false, pausedAt = 0, clockStart = 0, seeking = false;
  const now = () => ctx ? ctx.currentTime : performance.now() / 1000;
  const position = () => playing ? Math.max(0, now() - (ctx ? startAt : clockStart)) : pausedAt;

  function play(from = pausedAt) {
    if (from >= DURATION) from = 0;
    initAudio();
    if (ctx) {
      ctx.resume();
      bus = ctx.createGain(); bus.gain.value = .8; bus.connect(out);
      startAt = ctx.currentTime + .08 - from;
      cursor = events.findIndex(e => e.t >= from - .001);
      if (cursor < 0) cursor = events.length;
      schedule();
      timer = setInterval(schedule, 25);
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
    clearInterval(timer);
    if (bus) {
      const b = bus;
      b.gain.setTargetAtTime(0, ctx.currentTime, .015);
      setTimeout(() => b.disconnect(), 120);
      bus = null;
    }
    stage.dataset.state = state;
    toggle.textContent = '▶'; toggle.setAttribute('aria-label', state === 'ended' ? 'もう一度再生' : '再生');
    bigPlay.lastChild.textContent = state === 'ended' ? ' REPLAY' : ' PLAY';
  }

  const togglePlay = () => playing ? pause() : play();
  toggle.addEventListener('click', togglePlay);
  bigPlay.addEventListener('click', () => play());
  stage.addEventListener('click', e => { if (e.target === stage || e.target.closest('svg')) togglePlay(); });
  document.addEventListener('keydown', e => {
    if (e.code !== 'Space' || e.target.closest('button, input, a')) return;
    e.preventDefault(); togglePlay();
  });

  seek.max = DURATION;
  seek.addEventListener('input', () => {
    seeking = true;
    const wasPlaying = playing;
    if (wasPlaying) pause();
    pausedAt = +seek.value;
    if (wasPlaying) play(pausedAt);
    else if (stage.dataset.state === 'ended') {
      stage.dataset.state = 'paused';
      toggle.setAttribute('aria-label', '再生');
      bigPlay.lastChild.textContent = ' PLAY';
    }
    seeking = false;
  });

  fullscreen.addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (stage.requestFullscreen) stage.requestFullscreen();
  });
  if (!document.fullscreenEnabled) fullscreen.hidden = true;

  // ---------- Rendering ----------
  const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  let lastLyric = null;

  function render() {
    let pos = position();
    if (playing && pos >= DURATION + .5) { pause('ended'); pos = pausedAt = DURATION; }

    const bar = Math.min(Math.floor(pos / BAR), BARS - 1);
    const sec = section(bar);
    const beat = pos / BEAT;
    const phase = beat % 1;
    const still = reduceMotion.matches || !playing;

    if (stage.dataset.scene !== sec) stage.dataset.scene = sec;
    if (bar >= 30) stage.dataset.ending = ''; else delete stage.dataset.ending;
    stage.style.setProperty('--pulse', still ? 0 : Math.pow(1 - phase, 3).toFixed(3));

    let y = 0, r = 0;
    if (!still) {
      const hop = Math.abs(Math.sin(Math.PI * phase));
      if (sec === 'verseA') y = Math.sin(beat * Math.PI / 2) * 5;
      else if (sec === 'verseB') { y = -hop * 10; r = Math.sin(beat * Math.PI / 2) * 8; }
      else if (sec === 'chorus') { y = -hop * 42; r = Math.sin(beat * Math.PI) * 6; }
    }
    bob.setAttribute('transform', `translate(0 ${y.toFixed(1)}) rotate(${r.toFixed(2)} 0 100)`);
    const drift = Math.min(Math.max(pos - 24, 0), 16);
    town.setAttribute('transform', `translate(${(420 - drift * 17).toFixed(1)} 0)`);

    const line = LYRICS.find(([b]) => pos >= b * BAR && pos < (b + 2) * BAR - .15);
    const text = line ? line[1] : '';
    if (text !== lastLyric) {
      lastLyric = text;
      lyricEl.classList.remove('on');
      if (text) { lyricEl.textContent = text; void lyricEl.offsetWidth; lyricEl.classList.add('on'); }
    }

    if (!seeking) seek.value = Math.min(pos, DURATION).toFixed(1);
    timeEl.textContent = `${fmt(Math.min(pos, DURATION))} / ${fmt(DURATION)}`;
    requestAnimationFrame(render);
  }
  requestAnimationFrame(render);
})();
