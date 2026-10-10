// Renders the HamCup MV to a 1080x1920 / 30fps MP4.
// Requires Node.js, Playwright (with Chromium) and ffmpeg (libx264 + aac).
//
//   python3 -m http.server 4173            # from the repository root
//   node hamcup/tools/export-mv.js [output.mp4] [page-url]
//
// The page is opened in its frame-export mode (?export), every frame is drawn
// with window.__mv.render(t), and the soundtrack is rendered offline with
// window.__mv.renderAudio(), so the result does not depend on playback speed.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const FPS = 30;
const out = path.resolve(process.argv[2] || 'hamcup-mv.mp4');
const url = process.argv[3] || 'http://localhost:4173/hamcup/?export';

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hamcup-mv-'));
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 2 });
    await page.goto(url);
    await page.evaluate(() => window.__mv.ready);
    const duration = await page.evaluate(() => window.__mv.duration);

    const wav = await page.evaluate(() => window.__mv.renderAudio());
    fs.writeFileSync(path.join(dir, 'audio.wav'), Buffer.from(wav, 'base64'));

    const frames = Math.round(duration * FPS);
    for (let i = 0; i < frames; i++) {
      await page.evaluate(t => window.__mv.render(t), i / FPS);
      await page.screenshot({ path: path.join(dir, `${String(i).padStart(4, '0')}.png`) });
      if (i % FPS === 0) process.stdout.write(`\rframes ${i}/${frames}`);
    }
    process.stdout.write(`\rframes ${frames}/${frames}\n`);
  } finally {
    await browser.close();
  }

  execFileSync('ffmpeg', [
    '-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(dir, '%04d.png'),
    '-i', path.join(dir, 'audio.wav'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
    '-preset', 'slow', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', out
  ], { stdio: 'inherit' });
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`wrote ${out}`);
})();
