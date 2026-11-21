const SAMPLE_SIZE = 40;
const HUE_STEP = 15;
const HUE_BINS = 360 / HUE_STEP;

function coverLightCeiling(pixels) {
  const shadowLimit = 96;
  let shadowPixels = 0;
  let opaquePixels = 0;
  for (let index = 0; index < pixels.length; index += 4) {
    if (pixels[index + 3] < 224) continue;
    opaquePixels++;
    if (Math.max(pixels[index], pixels[index + 1], pixels[index + 2]) <= shadowLimit) shadowPixels++;
  }
  // On a mostly dark cover, bright details should not decide the hue.
  return shadowPixels >= opaquePixels * .75 ? shadowLimit : 255;
}

function colorHue(r, g, b, high, chroma) {
  let sector;
  if (high === r) sector = (g - b) / chroma;
  else if (high === g) sector = 2 + (b - r) / chroma;
  else sector = 4 + (r - g) / chroma;
  return (sector * 60 + 360) % 360;
}

function hueBin(r, g, b, high, chroma) {
  return Math.round(colorHue(r, g, b, high, chroma) / HUE_STEP) % HUE_BINS;
}

async function sampleCover(cover, ctx) {
  const image = await createImageBitmap(cover, { resizeWidth: 64, resizeHeight: 64, resizeQuality: 'high' });
  try {
    ctx.clearRect(0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
    // The exported tile includes the eyelet, frame and spine. Sample its printed face.
    ctx.drawImage(image, image.width * .22, image.height * .24, image.width * .70, image.height * .65,
      0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
    return ctx.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE).data;
  } finally {
    image.close();
  }
}

function smoothBins(scores, neighborWeight) {
  return scores.map((score, bin) => score + neighborWeight * (
    scores[(bin + HUE_BINS - 1) % HUE_BINS] + scores[(bin + 1) % HUE_BINS]
  ));
}

function singleCoverTones(pixels) {
  const scores = new Float32Array(HUE_BINS);
  for (let index = 0; index < pixels.length; index += 4) {
    const r = pixels[index], g = pixels[index + 1], b = pixels[index + 2];
    const high = Math.max(r, g, b), chroma = high - Math.min(r, g, b);
    if (pixels[index + 3] < 224 || high < 43 || chroma < 19) continue;
    scores[hueBin(r, g, b, high, chroma)] += (chroma / 255) ** 2 * (.55 + .45 * high / 255);
  }
  const smoothed = smoothBins(scores, .5);
  const ranked = [...smoothed.keys()].sort((a, b) => smoothed[b] - smoothed[a]);
  const strongest = ranked[0];
  if (smoothed[strongest] < SAMPLE_SIZE ** 2 * .0025) return {};
  const next = ranked.find(bin => {
    const distance = Math.abs(bin - strongest);
    return Math.min(distance, HUE_BINS - distance) >= 3 && smoothed[bin] >= smoothed[strongest] * .5;
  });
  return { primary: strongest * HUE_STEP, secondary: next === undefined ? undefined : next * HUE_STEP };
}

function batchCoverTone(pixels) {
  const maxLight = coverLightCeiling(pixels);
  const counts = new Float32Array(HUE_BINS);
  const votes = new Float32Array(HUE_BINS);
  const colors = Array.from({ length: HUE_BINS }, () => [0, 0, 0]);
  for (let index = 0; index < pixels.length; index += 4) {
    const r = pixels[index], g = pixels[index + 1], b = pixels[index + 2];
    const high = Math.max(r, g, b), chroma = high - Math.min(r, g, b);
    if (pixels[index + 3] < 224 || high < 12 || high > maxLight || chroma < 8) continue;
    const bin = hueBin(r, g, b, high, chroma);
    // Vivid areas get extra weight, but need enough actual coverage to qualify.
    const weight = maxLight === 255 && high >= 96 && chroma / high >= .84 ? 3 : 1;
    counts[bin]++;
    votes[bin] += weight;
    colors[bin][0] += r * weight;
    colors[bin][1] += g * weight;
    colors[bin][2] += b * weight;
  }
  const coverage = smoothBins(counts, .5);
  const scores = smoothBins(votes, .18);
  const strongest = [...scores.keys()].sort((a, b) => scores[b] - scores[a])
    .find(bin => counts[bin] && coverage[bin] >= SAMPLE_SIZE ** 2 * .075);
  if (strongest === undefined) return;

  const [r, g, b] = colors[strongest].map(value => value / votes[strongest]);
  const high = Math.max(r, g, b), low = Math.min(r, g, b), chroma = high - low;
  // Keep the sampled hue and relative depth while lifting the color to a paper tint.
  return {
    hue: Math.round(colorHue(r, g, b, high, chroma)) % 360,
    saturation: Math.round(30 + 46 * chroma / (255 - Math.abs(high + low - 255))),
    lightness: Math.round(77 + 13 * (high + low) / 510),
  };
}

function drawWash(ctx, size, x, y, radius, color) {
  const wash = ctx.createRadialGradient(x * size, y * size, 0, x * size, y * size, radius * size);
  wash.addColorStop(0, color);
  wash.addColorStop(1, 'transparent');
  ctx.fillStyle = wash;
  ctx.fillRect(0, 0, size, size);
}

function drawSinglePaper(ctx, size, { primary, secondary }) {
  const paper = ctx.createLinearGradient(0, 0, size, size);
  paper.addColorStop(0, '#faf7f2');
  paper.addColorStop(.30, primary === undefined ? '#f5f2ed' : `hsl(${primary} 31% 95%)`);
  paper.addColorStop(.65, primary === undefined ? '#e9e7e4' : `hsl(${primary} 54% 86%)`);
  paper.addColorStop(1, primary === undefined ? '#d2d1d3' : `hsl(${primary} 65% 75%)`);
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, size, size);

  if (primary !== undefined) drawWash(ctx, size, .94, .72, .77, `hsl(${primary} 64% 64% / .28)`);
  if (secondary !== undefined) drawWash(ctx, size, .06, .86, .77, `hsl(${secondary} 54% 73% / .35)`);
}

function orderPaperTones(tones) {
  tones.sort((a, b) => a.hue - b.hue || a.lightness - b.lightness || a.saturation - b.saturation);
  // Open the hue wheel at its largest gap so those two colors don't have to blend.
  let start = 0;
  let largestGap = 0;
  for (const [index, tone] of tones.entries()) {
    const next = (index + 1) % tones.length;
    const gap = tones[next].hue - tone.hue + (next === 0 ? 360 : 0);
    if (gap > largestGap) {
      largestGap = gap;
      start = next;
    }
  }
  return [...tones.slice(start), ...tones.slice(0, start)];
}

async function drawBatchPaper(ctx, size, covers, sampler) {
  const tones = [];
  for (const cover of covers) {
    const tone = batchCoverTone(await sampleCover(cover, sampler));
    if (tone) tones.push(tone);
  }
  const colors = orderPaperTones(tones).map(({ hue, saturation, lightness }) =>
    `hsl(${hue} ${saturation}% ${lightness}%)`);
  while (colors.length < covers.length) colors.unshift('#e9e6e3');
  const paper = ctx.createLinearGradient(0, size * .31, size, size * .67);
  for (const [index, color] of colors.entries()) {
    paper.addColorStop(.08 + .84 * index / (colors.length - 1), color);
  }
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, size, size);

  const light = ctx.createLinearGradient(0, 0, 0, size * .70);
  light.addColorStop(0, 'rgba(255, 253, 249, .86)');
  light.addColorStop(.32, 'rgba(255, 253, 249, .58)');
  light.addColorStop(1, 'rgba(255, 253, 249, 0)');
  ctx.fillStyle = light;
  ctx.fillRect(0, 0, size, size);
}

export async function drawCoverPaper(ctx, texture, covers, size) {
  const sampler = document.createElement('canvas');
  sampler.width = sampler.height = SAMPLE_SIZE;
  const sampleContext = sampler.getContext('2d', { willReadFrequently: true });
  if (covers.length === 1) drawSinglePaper(ctx, size, singleCoverTones(await sampleCover(covers[0], sampleContext)));
  else await drawBatchPaper(ctx, size, covers, sampleContext);

  ctx.save();
  ctx.globalCompositeOperation = 'soft-light';
  ctx.globalAlpha = .66;
  ctx.filter = 'grayscale(1) brightness(2.2) contrast(1.45)';
  ctx.drawImage(texture, 0, 0, size, size);
  ctx.restore();
}
