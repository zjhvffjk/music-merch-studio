import encodeJpeg from './vendor/jpeg-encoder.js';

self.onmessage = async event => {
  const {blob, maxSide} = event.data;
  let bitmap;
  try {
    bitmap = await createImageBitmap(blob);
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext('2d', {alpha:false, willReadFrequently:true});
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, width, height);
    context.imageSmoothingQuality = 'high';
    context.drawImage(bitmap, 0, 0, width, height);
    const image = context.getImageData(0, 0, width, height);
    const jpeg = encodeJpeg(image, 90);
    self.postMessage({blob:new Blob([jpeg.data], {type:'image/jpeg'})});
  } catch {
    self.postMessage({error:'浏览器无法编码 JPEG，请刷新页面后重试'});
  } finally {
    bitmap?.close();
  }
};
