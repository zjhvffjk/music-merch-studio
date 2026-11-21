// Coordinates measured on the ruler reference in its 3200 px coordinate space.
// The packaged WebP is the same photograph cropped to this texture rectangle.
const texture = { left: 450, top: 350, right: 2674, bottom: 2570 };
const body = { left: 475, top: 647, split: 817, right: 2657, bottom: 2535 };
export const frontFrame = { destination: [.15, .23, .70, .70 * 45 / 53] };
const [left, top, width, height] = frontFrame.destination;
const millimeter = width / 53;

function frontPoint(x, y, size = 1) {
  const offsetX = x <= body.split
    ? (x - body.left) * 8 / (body.split - body.left)
    : 8 + (x - body.split) * 45 / (body.right - body.split);
  const offsetY = (y - body.top) * 45 / (body.bottom - body.top);
  return [(left + offsetX * millimeter) * size, (top + offsetY * millimeter) * size];
}

export function frontShellContour(size) {
  const p = new Path2D();
  const point = (x, y) => frontPoint(x, y, size);
  p.moveTo(...point(568, 647));
  p.lineTo(...point(1407, 647));
  p.bezierCurveTo(...point(1434, 647), ...point(1448, 629), ...point(1448, 594));
  p.lineTo(...point(1448, 535));
  p.bezierCurveTo(...point(1448, 445), ...point(1516, 373), ...point(1599, 373));
  p.bezierCurveTo(...point(1683, 373), ...point(1752, 445), ...point(1752, 535));
  p.lineTo(...point(1752, 594));
  p.bezierCurveTo(...point(1752, 630), ...point(1766, 647), ...point(1795, 647));
  p.lineTo(...point(2559, 647));
  p.bezierCurveTo(...point(2618, 647), ...point(2657, 685), ...point(2657, 744));
  p.lineTo(...point(2657, 2440));
  p.bezierCurveTo(...point(2657, 2500), ...point(2619, 2535), ...point(2559, 2535));
  p.lineTo(...point(568, 2535));
  p.bezierCurveTo(...point(511, 2535), ...point(475, 2501), ...point(475, 2440));
  p.lineTo(...point(475, 744));
  p.bezierCurveTo(...point(475, 685), ...point(512, 647), ...point(568, 647));
  p.closePath();

  const [x, y] = point(1599, 527);
  const [edgeX, edgeY] = point(1672, 599);
  p.moveTo(edgeX, y);
  p.ellipse(x, y, edgeX - x, edgeY - y, 0, 0, Math.PI * 2);
  p.closePath();
  return p;
}

export function frontShellBounds(size) {
  return { left: left * size, top: frontPoint(body.left, 373, size)[1], width: width * size, bottom: (top + height) * size };
}

export function composeFrontShell(image, size) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const contour = frontShellContour(size);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, size, size);
  ctx.save();
  ctx.shadowColor = 'rgba(27, 28, 32, .24)';
  ctx.shadowBlur = size * .014;
  ctx.shadowOffsetY = size * .008;
  ctx.fill(contour, 'evenodd');
  ctx.restore();

  const [x, y] = frontPoint(texture.left, texture.top, size);
  const [right, bottom] = frontPoint(texture.right, texture.bottom, size);
  const split = Math.round(frontPoint(body.split, body.top, size)[0]);
  const sourceSplit = (body.split - texture.left) / (texture.right - texture.left) * image.width;
  ctx.clip(contour, 'evenodd');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(image, 0, 0, sourceSplit, image.height, x, y, split - x, bottom - y);
  ctx.drawImage(image, sourceSplit, 0, image.width - sourceSplit, image.height,
    split, y, right - split, bottom - y);
  return canvas;
}

export function prepareFrontEyelet(image) {
  const crop = { left: 1381, top: 369, right: 1821, bottom: 685 };
  const resolution = 4096;
  const [x, y] = frontPoint(crop.left, crop.top, resolution);
  const [right, bottom] = frontPoint(crop.right, crop.bottom, resolution);
  const [center, rail] = frontPoint(1599, body.top, resolution);
  const w = right - x, h = bottom - y;
  const canvas = document.createElement('canvas');
  canvas.width = Math.ceil(w);
  canvas.height = Math.ceil(h);
  const ctx = canvas.getContext('2d');
  const sx = image.width / (texture.right - texture.left);
  const sy = image.height / (texture.bottom - texture.top);
  ctx.save();
  ctx.translate(-x, -y);
  ctx.clip(frontShellContour(resolution), 'evenodd');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(image, (crop.left - texture.left) * sx, (crop.top - texture.top) * sy,
    (crop.right - crop.left) * sx, (crop.bottom - crop.top) * sy, x, y, w, h);
  ctx.restore();

  // Blend the few pixels of plastic below the join into each view's own rail.
  ctx.globalCompositeOperation = 'destination-in';
  const baseFade = ctx.createLinearGradient(0, rail - y, 0, h);
  baseFade.addColorStop(0, '#fff');
  baseFade.addColorStop(1, '#fff0');
  ctx.fillStyle = baseFade;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const sideFade = ctx.createLinearGradient(0, 0, w, 0);
  sideFade.addColorStop(0, '#fff0');
  sideFade.addColorStop(.06, '#fff');
  sideFade.addColorStop(.94, '#fff');
  sideFade.addColorStop(1, '#fff0');
  ctx.fillStyle = sideFade;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const pixelsPerMM = millimeter * resolution;
  return {
    canvas,
    x: (x - center) / pixelsPerMM,
    y: (y - rail) / pixelsPerMM,
    width: canvas.width / pixelsPerMM,
    height: canvas.height / pixelsPerMM,
  };
}

function rectQuad(x, y, w, h) {
  return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
}

const paperSide = 41 * millimeter;
const [paperX, paperY] = frontPoint(1698, 1594);
export const frontPaperQuad = rectQuad(paperX - paperSide / 2, paperY - paperSide / 2, paperSide, paperSide);
const [trayX, trayY] = frontPoint(535, 792);
const [trayRight, trayBottom] = frontPoint(738, 2391);
export const frontTrayQuad = rectQuad(trayX, trayY, trayRight - trayX, trayBottom - trayY);

const windows = { front: [841, 772, 2558, 2414], tray: [520, 807, 751, 2376] };
export function frontSlotWindow(id, size) {
  const [x0, y0, x1, y1] = windows[id];
  const [x, y] = frontPoint(x0, y0, size);
  const [right, bottom] = frontPoint(x1, y1, size);
  const path = new Path2D();
  path.roundRect(x, y, right - x, bottom - y, size * .006);
  return path;
}

function frontRetainerPair(size, y) {
  const path = new Path2D();
  for (const x of [1168, 2088]) {
    const [cx, cy] = frontPoint(x, y, size);
    const [right, bottom] = frontPoint(x + 132, y + 145, size);
    path.moveTo(right, cy);
    path.ellipse(cx, cy, right - cx, bottom - cy, 0, 0, Math.PI * 2);
  }
  return path;
}

export function frontUpperRetainerMask(size) {
  return frontRetainerPair(size, 770);
}

export function frontLowerRetainerMask(size) {
  return frontRetainerPair(size, 2413);
}

export function frontRetainerMask(size) {
  const path = frontUpperRetainerMask(size);
  path.addPath(frontLowerRetainerMask(size));
  for (const x of [827, 2499]) for (const y of [939, 1818]) {
    const [left, top] = frontPoint(x, y, size);
    const [right, bottom] = frontPoint(x + 75, y + 384, size);
    path.roundRect(left, top, right - left, bottom - top, size * .009);
  }
  return path;
}

const previousPaper = rectQuad(.5418 - paperSide / 2, .52795 - paperSide / 2, paperSide, paperSide);
const previousTray = [[.1735, .2705], [.224, .2705], [.224, .792], [.1735, .792]];
export function rebaseFrontQuad(id, quad) {
  const oldDefault = id === 'front' ? previousPaper : previousTray;
  const newDefault = id === 'front' ? frontPaperQuad : frontTrayQuad;
  return quad.map((point, index) => point.map((value, axis) =>
    Math.max(0, Math.min(1, value + newDefault[index][axis] - oldDefault[index][axis])),
  ));
}
