"""Encode product images as 4K JPEGs."""

from io import BytesIO

from PIL import Image, UnidentifiedImageError


PRODUCT_JPEG_SIZE = 4096
MAX_PRODUCT_SIDE = 8192
MAX_PRODUCT_BYTES = MAX_PRODUCT_SIDE ** 2 * 4 + 2 * 1024 * 1024


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
