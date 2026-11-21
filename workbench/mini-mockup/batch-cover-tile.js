import { BASE, render } from './renderer.js';

// Outline of the photographed front shell in the renderer's BASE coordinates.
// The second contour opens the eyelet so the poster shows through it.
const frontContour = `M 222 288 H 548
  C 570 288 580 279 580 259 V 236
  C 580 198 606 171 639 171 C 672 171 700 198 700 236 V 259
  C 700 279 708 288 732 288 H 1028 Q 1063 288 1063 321
  L 1065 998 Q 1065 1033 1031 1035 H 223 Q 188 1035 188 1001
  V 322 Q 188 288 222 288 Z
  M 639 201 C 658 201 672 215 672 234 C 672 251 657 267 639 267
  C 620 267 606 252 606 234 C 606 216 620 201 639 201 Z`;
const bounds = { left: 187, top: 170, width: 879, height: 866 };

export async function exportBatchCoverTile(state, size = 1536) {
  if (!state.assets.front?.src) throw Error('正视图缺少封面素材');
  const source = document.createElement('canvas');
  const tile = document.createElement('canvas');
  const scale = size / BASE;

  try {
    render(source, { ...state, showDesign: true, background: '#ffffff' }, 0, size);
    tile.width = Math.ceil(bounds.width * scale);
    tile.height = Math.ceil(bounds.height * scale);
    const ctx = tile.getContext('2d');
    ctx.setTransform(scale, 0, 0, scale, -bounds.left * scale, -bounds.top * scale);
    ctx.clip(new Path2D(frontContour), 'evenodd');
    ctx.drawImage(source, 0, 0, BASE, BASE);
    return await new Promise((resolve, reject) => {
      tile.toBlob(blob => blob ? resolve(blob) : reject(Error('正视图合成失败')), 'image/png');
    });
  } finally {
    source.width = source.height = 0;
    tile.width = tile.height = 0;
  }
}
