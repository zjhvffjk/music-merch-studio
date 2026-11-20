export const PRODUCT_JPEG_SIZE = 4096;

let serverEncoder;
export function hasProductJpegEncoder(base = location.origin) {
  return fetch(new URL('/api/ping',base)).then(async response => {
    if (!response.ok) throw Error('无法连接工作台，请刷新后重试');
    const service = await response.json();
    return service.productExportFormats?.includes('4k');
  });
}

function encodeJpegInBrowser(blob) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./product-jpeg-worker.js', import.meta.url), {type:'module'});
    worker.onmessage = ({data}) => {
      worker.terminate();
      if (data.error) reject(Error(data.error));
      else resolve(data.blob);
    };
    worker.onerror = () => {
      worker.terminate();
      reject(Error('浏览器 JPEG 编码器加载失败，请刷新页面后重试'));
    };
    worker.postMessage({blob,maxSide:PRODUCT_JPEG_SIZE});
  });
}

export async function encodeProductJpeg(blob) {
  serverEncoder ??= hasProductJpegEncoder().catch(() => {
    serverEncoder = undefined;
    return false;
  });
  if (!await serverEncoder) return encodeJpegInBrowser(blob);
  const response = await fetch('/api/product-export?format=4k', {method:'POST', body:blob});
  if (!response.ok) {
    if (response.status === 404) return encodeJpegInBrowser(blob);
    const detail = await response.json().catch(() => null);
    throw Error(detail?.error || '商品图编码失败，请重试');
  }
  return response.blob();
}

export function productJpegFilename(name) {
  return name.replace(/\.(png|jpe?g|webp)$/i, '') + '.jpg';
}
