import { render } from './renderer.js';
import { frontShellBounds, frontShellContour } from './front-shell.js';

export async function exportBatchCoverTile(state, size = 1536) {
  if (!state.assets.front?.src) throw Error('正视图缺少封面素材');
  const source = document.createElement('canvas');
  const tile = document.createElement('canvas');
  const bounds = frontShellBounds(size);
  const left = Math.floor(bounds.left) - 1;
  const top = Math.floor(bounds.top) - 1;

  try {
    render(source, { ...state, showDesign: true, background: '#ffffff' }, 0, size);
    tile.width = Math.ceil(bounds.left + bounds.width) - left + 1;
    tile.height = Math.ceil(bounds.bottom) - top + 1;
    const ctx = tile.getContext('2d');
    ctx.translate(-left, -top);
    ctx.clip(frontShellContour(size), 'evenodd');
    ctx.drawImage(source, 0, 0);
    return await new Promise((resolve, reject) => {
      tile.toBlob(blob => blob ? resolve(blob) : reject(Error('正视图合成失败')), 'image/png');
    });
  } finally {
    source.width = source.height = 0;
    tile.width = tile.height = 0;
  }
}
