import { frontRetainerPhotoRegions } from '../front-shell.js';

// The mounting points are measured on open-outer-reference.png.
const centers = [1063, 1480];
const rails = [
  { y: 204, clearTop: 165, clearBottom: 272 },
  { y: 807, clearTop: 741, clearBottom: 849 },
];

function feather(distance, width) {
  const t = Math.min(1, distance / width);
  return t * t * (3 - 2 * t);
}

export function replaceFlatCoverRetainers(photo, frontPhoto) {
  const canvas = document.createElement('canvas');
  canvas.width = photo.width;
  canvas.height = photo.height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(photo, 0, 0);

  // Continue the plastic and the rail from either side of each molded tab.
  // The transition follows the original photo so the repair has no seam.
  const halfWidth = 62;
  const width = halfWidth * 2 + 1;
  for (const {clearTop, clearBottom} of rails) for (const center of centers) {
    const left = center - halfWidth;
    const height = clearBottom - clearTop;
    const patch = ctx.getImageData(left, clearTop, width, height);
    const {data} = patch;
    for (let y = 0; y < height; y++) {
      const row = y * width * 4;
      const vertical = feather(Math.min(y, height - 1 - y), 12);
      for (let x = 1; x < width - 1; x++) {
        const mix = x / (width - 1);
        const opacity = vertical * feather(Math.min(x, width - 1 - x), 14);
        const pixel = row + x * 4;
        for (let channel = 0; channel < 3; channel++) {
          const a = data[row + channel];
          const b = data[row + (width - 1) * 4 + channel];
          data[pixel + channel] += ((1 - mix) * a + mix * b - data[pixel + channel]) * opacity;
        }
      }
    }
    ctx.putImageData(patch, left, clearTop);
  }
  const [, lowerReference] = frontRetainerPhotoRegions(frontPhoto);
  const [upperRail, lowerRail] = rails;
  // Match the physical cover width and the distance between the rails.
  const sx = 640 / 1717;
  const sy = 603 / 1643;
  ctx.imageSmoothingQuality = 'high';
  centers.forEach((x, column) => {
    const region = lowerReference[column];
    const patch = blendPhotoEdges(frontPhoto, region);
    const left = x - region.anchorX * sx;
    const anchorY = region.anchorY * sy;
    const patchWidth = region.width * sx;
    const patchHeight = region.height * sy;
    ctx.drawImage(patch, left, lowerRail.y - anchorY, patchWidth, patchHeight);

    // Reflect the same lower tab around the upper rail's mounting line.
    ctx.save();
    ctx.translate(left, upperRail.y + anchorY);
    ctx.scale(1, -1);
    ctx.drawImage(patch, 0, 0, patchWidth, patchHeight);
    ctx.restore();
  });
  return canvas;
}

function blendPhotoEdges(photo, {source, width, height}) {
  const patch = document.createElement('canvas');
  patch.width = width;
  patch.height = height;
  const ctx = patch.getContext('2d');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(photo, ...source, 0, 0, width, height);
  ctx.globalCompositeOperation = 'destination-in';
  for (const gradient of [ctx.createLinearGradient(0, 0, width, 0),
    ctx.createLinearGradient(0, 0, 0, height)]) {
    gradient.addColorStop(0, '#fff0');
    gradient.addColorStop(.13, '#fff');
    gradient.addColorStop(.87, '#fff');
    gradient.addColorStop(1, '#fff0');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  }
  return patch;
}
