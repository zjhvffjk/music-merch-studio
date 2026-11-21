import { encodeProductJpeg, PRODUCT_JPEG_SIZE } from './product-export.js';
import { drawWatermark, loadWatermark, prepareWatermark } from './watermark.js';
import { drawCoverPaper } from './cover-poster-background.js';

const BATCH_COVER_LABEL = '批量专辑封面总览';
const COVERS_PER_POSTER = 8;
const PAPER_INK = '#201d21';
const PAPER_MUTED_INK = '#493f48';
export const SINGLE_COVER_LABEL = '专辑封面商品图';

async function loadPosterAsset(name, type) {
  const response = await fetch(new URL(`./assets/${name}`, import.meta.url));
  if (!response.ok) throw Error('无法加载封面总览素材');
  const url = URL.createObjectURL(new Blob([await response.arrayBuffer()], { type }));
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return image;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function coverGrid(count, size, aspect) {
  const width = size * .91, height = size * .51, top = size * .233;
  const gapX = size * .025, gapY = gapX * .82;
  const columns = count <= 3 ? count : Math.ceil(count / 2);
  const rows = Math.ceil(count / columns);
  const tileWidth = Math.min((width - (columns - 1) * gapX) / columns,
    (height - (rows - 1) * gapY) * aspect / rows);
  const tileHeight = tileWidth / aspect;
  const startY = top + (height - rows * tileHeight - (rows - 1) * gapY) / 2;
  return Array.from({ length: count }, (_, index) => {
    const row = Math.floor(index / columns);
    const inRow = Math.min(columns, count - row * columns);
    const rowWidth = inRow * tileWidth + (inRow - 1) * gapX;
    return {
      x: (size - rowWidth) / 2 + index % columns * (tileWidth + gapX),
      y: startY + row * (tileHeight + gapY),
      width: tileWidth,
      height: tileHeight,
    };
  });
}

function drawPosterHeader(ctx, albums, size, { single, page, totalPages, count }) {
  const first = albums[0];
  const artist = first.artist?.trim();
  const sharedArtist = artist && albums.every(album => album.artist?.trim() === artist);
  const title = single ? first.album?.trim() || '迷你专辑' : (sharedArtist ? artist : '迷你专辑合集');
  const subtitle = single
    ? [artist, 'MINI ALBUM'].filter(Boolean).join('  ·  ')
    : `MINI ALBUM COLLECTION  ·  ${count} 张专辑${totalPages > 1 ? `  ·  ${page}/${totalPages}` : ''}`;
  ctx.fillStyle = PAPER_INK;
  ctx.textAlign = 'center';
  ctx.font = `700 ${size * .104}px Georgia, "Microsoft YaHei", serif`;
  const titleSize = size * .104 * Math.min(1, size * .86 / ctx.measureText(title).width);
  ctx.font = `700 ${titleSize}px Georgia, "Microsoft YaHei", serif`;
  ctx.textBaseline = 'middle';
  ctx.fillText(title, size * .5, size * .115);
  ctx.font = `600 ${size * .022}px "Segoe UI", "Microsoft YaHei", sans-serif`;
  ctx.fillStyle = PAPER_MUTED_INK;
  ctx.fillText(subtitle, size * .5, size * .187, size * .86);
}

function drawPosterFooter(ctx, marks, size) {
  ctx.fillStyle = '#3026323d';
  ctx.fillRect(size * .055, size * .76, size * .89, Math.max(1, size * .00075));
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = PAPER_INK;
  ctx.font = `700 ${size * .043}px "Segoe UI", sans-serif`;
  ctx.fillText('Mini Album', size * .055, size * .826);
  const labelX = size * .072 + ctx.measureText('Mini Album').width;
  ctx.fillStyle = PAPER_MUTED_INK;
  ctx.font = `600 ${size * .022}px "Microsoft YaHei", sans-serif`;
  ctx.fillText('迷你专辑', labelX, size * .826);
  ctx.fillStyle = PAPER_INK;
  ctx.font = `700 ${size * .074}px "Segoe UI", sans-serif`;
  ctx.fillText('NFC', size * .055, size * .927);
  const nfcTextX = size * .080 + ctx.measureText('NFC').width;
  ctx.font = `700 ${size * .025}px "Microsoft YaHei", sans-serif`;
  ctx.fillText('触碰播放', nfcTextX, size * .894);
  ctx.fillStyle = PAPER_MUTED_INK;
  ctx.font = `500 ${size * .020}px "Segoe UI", sans-serif`;
  ctx.fillText('Tap to Play', nfcTextX, size * .922);
  const width = size * .43;
  ctx.save();
  ctx.shadowColor = '#35283a24';
  ctx.shadowBlur = size * .002;
  ctx.shadowOffsetY = size * .0015;
  ctx.drawImage(marks, size * .515, size * .812, width, width * marks.naturalHeight / marks.naturalWidth);
  ctx.restore();
}

function drawCaseShadow(ctx, { x, y, width, height }) {
  ctx.save();
  ctx.translate(x + width / 2, y + height * 1.008);
  ctx.scale(width * .55, height * .024);
  const shadow = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
  shadow.addColorStop(0, 'rgba(13, 9, 7, .48)');
  shadow.addColorStop(1, 'rgba(13, 9, 7, 0)');
  ctx.fillStyle = shadow;
  ctx.fillRect(-1, -1, 2, 2);
  ctx.restore();
}

async function loadPosterLayers(watermark) {
  const [background, marks, stamp] = await Promise.all([
    loadPosterAsset('batch-cover-paper.webp', 'image/webp'),
    loadPosterAsset('batch-cover-platforms.svg', 'image/svg+xml'),
    watermark ?? loadWatermark().catch(() => undefined),
  ]);
  if (stamp?.enabled) await prepareWatermark(stamp);
  return { background, marks, stamp };
}

async function renderCoverPoster(albums, covers, { background, marks, stamp }, header) {
  const canvas = document.createElement('canvas');
  const size = PRODUCT_JPEG_SIZE;
  canvas.width = canvas.height = size;
  try {
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    await drawCoverPaper(ctx, background, covers, size);
    drawPosterHeader(ctx, albums, size, { ...header, count: covers.length });
    drawPosterFooter(ctx, marks, size);

    let positions;
    for (const [index, cover] of covers.entries()) {
      const image = await createImageBitmap(cover);
      try {
        positions ??= coverGrid(covers.length, size, image.width / image.height);
        const position = positions[index];
        drawCaseShadow(ctx, position);
        ctx.drawImage(image, position.x, position.y, position.width, position.height);
      } finally {
        image.close();
      }
    }
    drawWatermark(canvas, stamp);
    const png = await new Promise((resolve, reject) => {
      canvas.toBlob(blob => blob ? resolve(blob) : reject(Error('封面总览合成失败')), 'image/png');
    });
    return await encodeProductJpeg(png);
  } finally {
    canvas.width = canvas.height = 0;
  }
}

export async function exportSingleCoverPoster(album, cover, watermark) {
  if (!cover) throw Error('缺少专辑正视图');
  return renderCoverPoster([album], [cover], await loadPosterLayers(watermark), { single: true });
}

export async function exportBatchCoverPosters(albums, covers) {
  if (!albums.length || albums.length !== covers.length || albums.some((_, i) => !covers[i])) {
    throw Error('缺少专辑正视图');
  }
  const layers = await loadPosterLayers();
  const totalPages = Math.ceil(covers.length / COVERS_PER_POSTER);
  const posters = [];
  for (let page = 1; page <= totalPages; page++) {
    const start = (page - 1) * COVERS_PER_POSTER;
    const pageCovers = covers.slice(start, start + COVERS_PER_POSTER);
    const suffix = totalPages > 1 ? `-${String(page).padStart(2, '0')}` : '';
    const name = `${BATCH_COVER_LABEL}${suffix}.jpg`;
    const label = totalPages > 1 ? `${BATCH_COVER_LABEL} · 第 ${page}/${totalPages} 张` : BATCH_COVER_LABEL;
    const blob = await renderCoverPoster(albums, pageCovers, layers, { page, totalPages });
    posters.push({
      name, label, blob, downloadName: name,
      detail: `${pageCovers.length} 张专辑 · ${PRODUCT_JPEG_SIZE} × ${PRODUCT_JPEG_SIZE}`,
    });
  }
  return posters;
}
