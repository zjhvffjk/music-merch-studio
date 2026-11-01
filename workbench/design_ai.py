"""Local image-model profiles and reference-image editing for Mini CD design.

Profiles live under ignored outputs/. API keys are encrypted with Windows DPAPI
for the current Windows user and are never included in HTTP responses.
"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import io
import ipaddress
import json
import os
import re
from pathlib import Path
import threading
import socket
import urllib.request
from urllib.parse import urlsplit, quote
import uuid

import requests
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
PROFILE_FILE = ROOT / "outputs" / "工作台" / "_ai_profiles.json"
UPLOAD_DIR = ROOT / "outputs" / "工作台" / "_uploads"
PROVIDERS = {
    "openai": {"name": "OpenAI Images", "protocol": "openai", "baseUrl": "https://api.openai.com/v1", "model": "gpt-image-2.5-sunburst",
               "models": ["gpt-image-2.5-sunburst", "gpt-image-2.5-flare", "gpt-image-2"]},
    "gemini": {"name": "Google Gemini Images", "protocol": "gemini", "baseUrl": "https://generativelanguage.googleapis.com/v1beta", "model": "gemini-nano-banana-2.1",
               "models": ["gemini-nano-banana-2.1", "gemini-3.1-flash-lite-image",
                          "gemini-3.1-flash-image", "gemini-3-pro-image"]},
    "volcengine": {"name": "豆包 · 火山方舟 Seedream", "protocol": "ark",
        "baseUrl": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-seedream-5-0-flash-260915",
        "models": ["doubao-seedream-5-0-flash-260915", "doubao-seedream-5-0-pro-260628",
                   "doubao-seedream-5-0-lite-260128", "doubao-seedream-4-5-251128", "doubao-seedream-4-0-250828"]},
    "custom": {"name": "自定义图片服务（兼容接口）", "protocol": "openai", "baseUrl": "",
        "model": "", "models": []},
}
TARGETS = {
    "disc": "40mm 迷你 CD 盘面艺术，圆形构图，中心 5mm 圆孔区域不得有脸或重要文字",
    "inside": "41×41mm 封面背面／内页，与正封面同一视觉世界的新场景",
    "back": "49×38mm 盒体封底，保留曲目、时长、版权及条码的清晰排版区域",
    "right-spine": "4.4×38mm 右侧封，竖向窄幅设计",
    "left-spine": "4.4×38mm 左侧封，竖向窄幅设计",
    "left-spine-back": "4.4×38mm 左侧封背面，竖向窄幅设计",
    "tray": "49×38mm 内盘底，封面主题的隐藏主视觉与场景延展",
}
# Provider outputs are design drafts. The print compositor retains the exact
# physical dimensions; image-model APIs cannot produce a 4.4:38 spine directly.
ASPECTS = {
    "disc": ("1024x1024", "1:1"),
    "inside": ("1024x1024", "1:1"),
    "back": ("1536x1024", "4:3"),
    "right-spine": ("1024x1536", "9:16"),
    "left-spine": ("1024x1536", "9:16"),
    "left-spine-back": ("1024x1536", "9:16"),
    "tray": ("1536x1024", "4:3"),
}
_lock = threading.RLock()


def _network_options() -> dict:
    """Honor the user's current Windows proxy, including one enabled after startup."""
    if os.name != "nt":
        return {}
    proxies = urllib.request.getproxies_registry()
    chosen = {scheme: proxies[scheme] for scheme in ("http", "https") if proxies.get(scheme)}
    return {"proxies": chosen} if chosen else {}


class ModelError(ValueError):
    pass


def _crypt(data: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise ModelError("本机密钥保存目前仅支持 Windows")

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    source_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), source_buffer)
    result = Blob()
    crypt32 = ctypes.windll.crypt32
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ModelError("本机密钥加密或解密失败")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        local_free = ctypes.windll.kernel32.LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p
        local_free(ctypes.cast(result.pbData, ctypes.c_void_p))


def _read() -> dict:
    if not PROFILE_FILE.exists():
        return {"default": "", "profiles": []}
    data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
        raise ModelError("本机 AI 配置文件格式错误")
    return data


def _write(data: dict) -> None:
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = PROFILE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, PROFILE_FILE)


def _public(row: dict, default: str) -> dict:
    return {"id": row["id"], "name": row["name"], "provider": row["provider"],
            "model": row["model"], "hasKey": bool(row.get("key")),
            "protocol": row.get("protocol") or PROVIDERS[row["provider"]]["protocol"],
            "baseUrl": row.get("baseUrl") or PROVIDERS[row["provider"]]["baseUrl"],
            "default": row["id"] == default}


def _base_url(value):
    value = str(value or "").strip().rstrip("/")
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment \
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and local)):
        raise ModelError("接口地址须为 HTTPS（本机服务可用 HTTP），不要包含密钥、查询参数或账号密码")
    return value


def list_profiles() -> dict:
    with _lock:
        data = _read()
        return {"ok": True, "default": data.get("default", ""),
                "providers": PROVIDERS,
                "profiles": [_public(row, data.get("default", "")) for row in data["profiles"]]}


def save_profile(payload: dict) -> dict:
    provider = str(payload.get("provider") or "").strip()
    if provider not in PROVIDERS:
        raise ModelError("请选择支持图片编辑的服务商")
    name = str(payload.get("name") or PROVIDERS[provider]["name"]).strip()[:60]
    model = str(payload.get("model") or PROVIDERS[provider]["model"]).strip()[:100]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:-]{0,149}", model):
        raise ModelError("模型名称无效")
    key = str(payload.get("apiKey") or "").strip()
    if len(key) > 1000:
        raise ModelError("API Key 太长")
    with _lock:
        data = _read()
        ident = str(payload.get("id") or "")
        existing = next((row for row in data["profiles"] if row["id"] == ident), None)
        if ident and existing is None:
            raise ModelError("配置不存在")
        previous = existing if existing and existing["provider"] == provider else {}
        protocol = str(payload.get("protocol") or previous.get("protocol") or PROVIDERS[provider]["protocol"])
        if protocol not in {"openai", "gemini", "ark"}:
            raise ModelError("请选择图片接口协议")
        base_url = _base_url(payload.get("baseUrl") or previous.get("baseUrl") or PROVIDERS[provider]["baseUrl"])
        if existing and provider != existing["provider"] and not key:
            raise ModelError("切换服务商时请填写该服务商的新 API Key")
        if existing and base_url != (existing.get("baseUrl") or PROVIDERS[existing["provider"]]["baseUrl"]) and not key:
            raise ModelError("切换接口地址时请填写新 API Key，避免将旧密钥发送给其他服务")
        row = existing or {"id": uuid.uuid4().hex[:16]}
        row.update({"name": name, "provider": provider, "model": model, "protocol": protocol, "baseUrl": base_url})
        if key:
            row["key"] = base64.b64encode(_crypt(key.encode("utf-8"))).decode("ascii")
        elif not row.get("key"):
            raise ModelError("请填写 API Key")
        if existing is None:
            data["profiles"].append(row)
        if payload.get("makeDefault") or not data.get("default"):
            data["default"] = row["id"]
        _write(data)
        return {"ok": True, "profile": _public(row, data["default"])}


def delete_profile(ident: str) -> dict:
    with _lock:
        data = _read()
        count = len(data["profiles"])
        data["profiles"] = [row for row in data["profiles"] if row["id"] != ident]
        if len(data["profiles"]) == count:
            raise ModelError("配置不存在")
        if data.get("default") == ident:
            data["default"] = data["profiles"][0]["id"] if data["profiles"] else ""
        _write(data)
        return {"ok": True}


def _profile(ident: str) -> tuple[dict, str]:
    with _lock:
        data = _read()
        ident = ident or data.get("default", "")
        row = next((row.copy() for row in data["profiles"] if row["id"] == ident), None)
    if row is None:
        raise ModelError("请先在 AI 设置中保存图片模型")
    try:
        key = _crypt(base64.b64decode(row["key"]), decrypt=True).decode("utf-8")
    except Exception as exc:
        raise ModelError("无法读取本机 API Key，请重新保存配置") from exc
    return row, key


def _json_response(response: requests.Response) -> dict:
    try:
        body = response.json()
    except ValueError as exc:
        raise ModelError("模型服务返回了非 JSON 响应") from exc
    if not response.ok:
        error = body.get("error") if isinstance(body, dict) else None
        message = str(error.get("message") or "请求失败") if isinstance(error, dict) else str(error or "请求失败")
        request = getattr(response, "request", None)
        headers = getattr(request, "headers", {}) or {}
        for header in ("Authorization", "x-goog-api-key", "x-api-key"):
            secret = str(headers.get(header) or "").removeprefix("Bearer ")
            if len(secret) > 6:
                message = message.replace(secret, "[密钥已隐藏]")
        message = re.sub(r"\b(?:ark-|sk-)[A-Za-z0-9_-]{8,}", "[密钥已隐藏]", message)
        if response.status_code == 429:
            if "limit: 0" in message and "Free Tier" in message:
                raise ModelError("密钥有效，但所属项目对该图片模型的免费生成额度为 0；请选择有图片额度的项目或模型。")
            raise ModelError("图片生成额度不足或已触发限速；请检查此 API Key 所属项目的配额与结算设置，稍后重试。")
        raise ModelError("模型接口 HTTP %s：%s" % (response.status_code, message[:300]))
    return body


def test_profile(ident: str) -> dict:
    row, key = _profile(ident)
    public = _public(row, ident)
    protocol, base_url = public["protocol"], public["baseUrl"]
    try:
        if protocol != "gemini":
            url = base_url + ("/models" if protocol == "ark" else "/models/" + quote(row["model"], safe=""))
            response = requests.get(url, headers={"Authorization": "Bearer " + key},
                                    timeout=(5, 12), **_network_options())
        else:
            url = base_url + "/models/" + quote(row["model"], safe="")
            response = requests.get(url, headers={"x-goog-api-key": key},
                                    timeout=(5, 12), **_network_options())
        body = _json_response(response)
        if protocol == "gemini" and "generateContent" not in body.get("supportedGenerationMethods", []):
            raise ModelError("此模型没有开放图片生成接口，请在配置里选择可用的图片模型")
        if protocol == "gemini" and not any(word in row["model"].lower() for word in ("image", "banana")):
            raise ModelError("这是文本模型名称；请选择 Gemini 图片模型（名称通常含 image 或 banana）")
    except requests.RequestException as exc:
        raise ModelError("无法连接模型接口，请检查本机网络或代理设置（%s）" % type(exc).__name__) from exc
    return {"ok": True, "message": "接口和密钥验证通过。未执行图片生成；模型权限与额度以出图测试为准。"}


def list_models(ident: str) -> dict:
    row, key = _profile(ident)
    profile = _public(row, ident)
    headers = {"x-goog-api-key": key} if profile["protocol"] == "gemini" else {"Authorization": "Bearer " + key}
    try:
        body = _json_response(requests.get(profile["baseUrl"] + "/models", headers=headers,
                                           timeout=(5, 15), **_network_options()))
    except requests.RequestException as exc:
        raise ModelError("读取模型列表失败，请检查接口地址与网络") from exc
    models = []
    for item in (body.get("models") or body.get("data") or []):
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or item.get("name") or "").removeprefix("models/")
        if re.search(r"image|seedream|seededit|banana|flux|kolors|cogview", ident, re.I):
            models.append(ident)
    return {"ok": True, "models": sorted(set(models)),
            "message": "已读取图片模型候选，能否调用以账号开通权限及出图测试为准。" if models else
                       "服务商未返回可识别的图片模型列表；可按其控制台手动填写模型 ID。"}


def _normalized_png(image_bytes: bytes) -> bytes:
    if len(image_bytes) > 30_000_000:
        raise ModelError("生成图片超过 30MB")
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        if image.width < 256 or image.height < 256:
            raise ModelError("模型返回的图片分辨率过低")
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()
    except (OSError, ValueError) as exc:
        if isinstance(exc, ModelError):
            raise
        raise ModelError("模型没有返回有效图片") from exc


def _image_result(item):
    """Normalize common image API responses; never send credentials to image hosts."""
    encoded = item.get("b64_json")
    if encoded:
        try:
            return _normalized_png(base64.b64decode(str(encoded).split("base64,", 1)[-1], validate=True))
        except (ValueError, base64.binascii.Error) as exc:
            raise ModelError("模型返回的图片编码无效") from exc
    url = str(item.get("url") or "")
    if not url:
        error = item.get("error") or {}
        raise ModelError("模型未返回图片：" + str(error.get("code") or "请检查模型能力与生成额度"))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ModelError("模型返回了无效图片地址")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
            raise ModelError("模型返回的图片地址指向本机或私有网络")
        with requests.get(url, timeout=(8, 60), stream=True, allow_redirects=False, **_network_options()) as response:
            if response.status_code != 200:
                raise ModelError("生成成功，但下载图片失败（HTTP %s）" % response.status_code)
            chunks, total = [], 0
            for chunk in response.iter_content(65536):
                total += len(chunk)
                if total > 30_000_000:
                    raise ModelError("生成图片超过30MB")
                chunks.append(chunk)
        return _normalized_png(b"".join(chunks))
    except (requests.RequestException, OSError) as exc:
        raise ModelError("生成成功，但下载图片失败，请检查网络") from exc


def generate(ident: str, reference: Image.Image, target: str, instruction: str,
             album: str = "", artist: str = "", tracks: list | None = None,
             company: str = "", source: Image.Image | None = None,
             inner_copy: str = "", barcode: str = "", copyright_text: str = "",
             release_year: str = "") -> dict:
    if target not in TARGETS:
        raise ModelError("未知组件")
    row, key = _profile(ident)
    profile = _public(row, ident)
    protocol, base_url = profile["protocol"], profile["baseUrl"]
    instruction = str(instruction or "").strip()[:1500]
    track_lines = []
    for item in (tracks or [])[:30]:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or "").strip()
            duration = str(item.get("duration") or "").strip()
            if title:
                track_lines.append(title + ("  " + duration if duration else ""))
    facts = "专辑：%s。歌手：%s。厂牌：%s。" % (album or "未提供", artist or "未提供", company or "未提供")
    if track_lines:
        facts += "已核实曲目（不得改写）：" + "；".join(track_lines) + "。"
    if target == "inside" and inner_copy.strip():
        facts += "用户指定内页文案（必须保留原文）：" + inner_copy.strip()[:300] + "。"
    if target == "back":
        facts += "封底固定信息必须预留清晰位置并保持原文："
        if release_year.strip():
            facts += "发行年份 " + release_year.strip()[:20] + "；"
        if barcode.strip():
            facts += "条码编号 " + barcode.strip()[:30] + "；"
        if copyright_text.strip():
            facts += "版权声明 " + copyright_text.strip()[:400] + "；"
        facts += "最终的条码、版权与曲目由现有印刷排版程序校对并覆盖。"
    _, aspect = ASPECTS[target]
    prompt = (
        "以参考专辑封面为唯一视觉母版，为同一张迷你CD制作一个独立组件。"
        "保持人物身份、画风、色彩、光影与主题一致，同时为该组件重新构图和扩展场景。"
        "本次组件：" + TARGETS[target] + "。" + facts +
        "保留用户给定的真实名称和曲目；不要自行编造真实曲目、时长、条码或版权声明。"
        "输出平面印刷设计图，无透视、无产品模型、无白色样机边框。"
        "构图按目标部件形状与安全裁切区设计；当前输出是草图，实际物理尺寸由印刷程序确定。"
        + ("盘面请输出铺满整个正方形画布的平面印刷底图；不要画银色盘沿、塑料环或白色孔洞，裁圆与打孔由程序处理。" if target == "disc" else "")
        + ("用户的具体修改要求：" + instruction if instruction else "")
    )
    def image_png(image: Image.Image) -> bytes:
        buf = io.BytesIO()
        image.convert("RGB").save(buf, "PNG")
        return buf.getvalue()
    refs = [source, reference] if source is not None else [reference]
    try:
        if protocol == "openai":
            response = requests.post(
                base_url + "/images/edits",
                headers={"Authorization": "Bearer " + key},
                data={"model": row["model"], "prompt": prompt, "quality": "high",
                      "size": ASPECTS[target][0], "output_format": "png"},
                files=[("image[]", ("reference-%d.png" % i, image_png(im), "image/png"))
                       for i, im in enumerate(refs)], timeout=240, **_network_options())
            body = _json_response(response)
            item = (body.get("data") or [{}])[0]
            png = _image_result(item)
        elif protocol == "ark":
            image_refs = ["data:image/png;base64," + base64.b64encode(image_png(im)).decode("ascii") for im in refs]
            response = requests.post(base_url + "/images/generations",
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={"model": row["model"], "prompt": prompt + " 输出宽高比：" + aspect + "。",
                      "image": image_refs[0] if len(image_refs) == 1 else image_refs,
                      "size": "2K", "response_format": "b64_json", "stream": False, "watermark": True},
                timeout=(10, 240), **_network_options())
            body = _json_response(response)
            png = _image_result((body.get("data") or [{}])[0])
        else:
            parts = [{"text": prompt}]
            parts.extend({"inline_data": {"mime_type": "image/png",
                                           "data": base64.b64encode(image_png(im)).decode("ascii")}}
                         for im in refs)
            response = requests.post(
                base_url + "/models/" + quote(row["model"], safe="") + ":generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={"contents": [{"parts": parts}],
                      "generationConfig": {"responseModalities": ["TEXT", "IMAGE"],
                                           "imageConfig": {"aspectRatio": aspect,
                                                           "imageSize": "2K"}}},
                timeout=240,
                **_network_options())
            body = _json_response(response)
            encoded = None
            for candidate in body.get("candidates") or []:
                for part in (candidate.get("content") or {}).get("parts") or []:
                    if part.get("thought"):
                        continue
                    inline = part.get("inlineData") or part.get("inline_data") or {}
                    if inline.get("data") and str(inline.get("mimeType") or inline.get("mime_type") or "").startswith("image/"):
                        encoded = inline["data"]
                        break
                if encoded:
                    break
            if not encoded:
                raise ModelError("Gemini 未返回图片；请检查模型额度或换一个图片模型")
            png = _image_result({"b64_json": encoded})
    except requests.RequestException as exc:
        raise ModelError("模型连接失败：%s" % type(exc).__name__) from exc
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:16]
    (UPLOAD_DIR / (uid + ".png")).write_bytes(png)
    return {"ok": True, "upload": uid, "url": "/api/design/ai/asset?uid=" + uid,
            "target": target, "profile": _public(row, row["id"])}
