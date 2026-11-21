"""Encode product images as 4K JPEGs."""

from io import BytesIO
from zipfile import is_zipfile

from PIL import Image, UnidentifiedImageError


PRODUCT_JPEG_SIZE = 4096
MAX_PRODUCT_SIDE = 8192
MAX_PRODUCT_BYTES = MAX_PRODUCT_SIDE ** 2 * 4 + 2 * 1024 * 1024
MAX_PRODUCT_ARCHIVE_BYTES = 2**32 - 1


def save_product_archive(size, request, path):
    signature = request.read(4)
    if signature not in (b"PK\x03\x04", b"PK\x05\x06"):
        raise ValueError("下载请求缺少完整的 ZIP")
    remaining = size - len(signature)
    with open(path, "wb") as archive:
        archive.write(signature)
        while remaining:
            chunk = request.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("ZIP 传输中断")
            archive.write(chunk)
            remaining -= len(chunk)
    if not is_zipfile(path):
        raise ValueError("下载请求缺少完整的 ZIP")


def encode_product_jpeg(source):
    try:
        with Image.open(source, formats=("PNG", "JPEG", "WEBP")) as original:
            if max(original.size) > MAX_PRODUCT_SIDE:
                raise ValueError("商品图最长边不能超过 8192 像素")
            if getattr(original, "n_frames", 1) != 1:
                raise ValueError("仅支持静态商品图")
            image = original.convert("RGBA")
            image.thumbnail((PRODUCT_JPEG_SIZE, PRODUCT_JPEG_SIZE), Image.Resampling.LANCZOS)
            rgb = Image.new("RGB", image.size, "white")
            rgb.paste(image, mask=image.getchannel("A"))
            with BytesIO() as output:
                rgb.save(output, "JPEG", quality=90, subsampling=0, optimize=True,
                         icc_profile=original.info.get("icc_profile"))
                return output.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("无法读取或编码商品图") from exc
