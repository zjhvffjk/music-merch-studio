"""Authorized audio storage and lookup for the workbench player.

Search providers remain metadata-only.  This module only exposes audio that
the operator uploaded or explicitly listed in a local authorization manifest.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any


MAX_UPLOAD_MIB = 200
MAX_UPLOAD_BYTES = MAX_UPLOAD_MIB * 1024 * 1024
_SAFE_SOURCE = re.compile(r"^[a-z0-9_-]{1,32}$")
_SAFE_TRACK_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SAFE_ASSET_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_AUDIO_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


class PlaybackValidationError(ValueError):
    """An audio binding request is invalid and safe to show to the user."""


def track_key(source: str, track_id: object) -> str:
    normalized_source = str(source or "").strip().lower()
    normalized_id = str(track_id if track_id is not None else "").strip()
    if not _SAFE_SOURCE.fullmatch(normalized_source):
        raise PlaybackValidationError("音源标识无效")
    if not _SAFE_TRACK_ID.fullmatch(normalized_id):
        raise PlaybackValidationError("歌曲 ID 无效")
    return f"{normalized_source}:{normalized_id}"


class PlaybackLibrary:
    def __init__(self, root: Path, manifest_path: Path | None = None):
        self.root = Path(root).resolve()
        self.files_dir = self.root / "files"
        self.index_path = self.root / "index.json"
        self.manifest_path = Path(manifest_path).resolve() if manifest_path else None
        self._lock = threading.RLock()
        self._index = self._read_json(self.index_path, {"version": 1, "tracks": {}})
        self._manifest = self._read_json(
            self.manifest_path, {"version": 1, "tracks": {}}
        ) if self.manifest_path else {"version": 1, "tracks": {}}

    @staticmethod
    def _read_json(path: Path | None, fallback: dict) -> dict:
        if not path or not path.is_file():
            return fallback
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or not isinstance(value.get("tracks", {}), dict):
                return fallback
            return value
        except (OSError, UnicodeError, json.JSONDecodeError):
            return fallback

    def _contained_file(self, relative: object) -> Path | None:
        value = str(relative or "").strip()
        if not value:
            return None
        try:
            target = (self.root / value).resolve()
            target.relative_to(self.root)
        except (OSError, ValueError):
            return None
        return target if target.is_file() else None

    @staticmethod
    def _public_asset(key: str, item: dict, asset_id: str) -> dict:
        return {
            "trackKey": key,
            "assetId": asset_id,
            "kind": item.get("kind") if item.get("kind") in ("full", "preview") else "full",
            "mimeType": item.get("mimeType") or "application/octet-stream",
            "provider": item.get("provider") or "upload",
            "durationMs": item.get("durationMs"),
            "expiresAt": item.get("expiresAt"),
        }

    def _manifest_asset_id(self, key: str, item: dict) -> str:
        material = f"{key}\0{item.get('file', '')}".encode("utf-8")
        return "manifest_" + hashlib.sha256(material).hexdigest()[:24]

    def resolve(self, source: str, track_id: object) -> dict | None:
        key = track_key(source, track_id)
        with self._lock:
            uploaded = (self._index.get("tracks") or {}).get(key)
            if isinstance(uploaded, dict):
                asset_id = str(uploaded.get("assetId") or "")
                if _SAFE_ASSET_ID.fullmatch(asset_id) and self._contained_file(uploaded.get("file")):
                    return self._public_asset(key, uploaded, asset_id)

            manifest = (self._manifest.get("tracks") or {}).get(key)
            if isinstance(manifest, dict) and self._contained_file(manifest.get("file")):
                asset_id = self._manifest_asset_id(key, manifest)
                return self._public_asset(key, manifest, asset_id)
        return None

    def state(self, source: str, track_id: object) -> str:
        return "playable" if self.resolve(source, track_id) else "unavailable"

    def bind_upload(
        self, source: str, track_id: object, filename: str, body: bytes
    ) -> dict:
        key = track_key(source, track_id)
        suffix = Path(str(filename or "")).suffix.lower()
        mime_type = _AUDIO_TYPES.get(suffix)
        if not mime_type:
            supported = "、".join(sorted(ext.lstrip(".").upper() for ext in _AUDIO_TYPES))
            raise PlaybackValidationError(f"不支持这种音频格式，请使用 {supported}")
        if not body:
            raise PlaybackValidationError("音频文件为空")
        if len(body) > MAX_UPLOAD_BYTES:
            raise PlaybackValidationError(f"音频文件超过 {MAX_UPLOAD_MIB} MiB")

        with self._lock:
            self.files_dir.mkdir(parents=True, exist_ok=True)
            asset_id = uuid.uuid4().hex
            relative = Path("files") / f"{asset_id}{suffix}"
            target = self.root / relative
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(body)
            os.replace(temporary, target)

            tracks = self._index.setdefault("tracks", {})
            previous = tracks.get(key) if isinstance(tracks.get(key), dict) else None
            item = {
                "assetId": asset_id,
                "file": relative.as_posix(),
                "filename": Path(str(filename)).name,
                "mimeType": mime_type,
                "kind": "full",
                "provider": "upload",
                "size": len(body),
                "createdAt": int(time.time()),
            }
            tracks[key] = item
            try:
                self._write_index()
            except Exception:
                tracks.pop(key, None)
                target.unlink(missing_ok=True)
                raise

            if previous:
                old_path = self._contained_file(previous.get("file"))
                if old_path and old_path != target:
                    old_path.unlink(missing_ok=True)
            return self._public_asset(key, item, asset_id)

    def _write_index(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.index_path)

    def asset_path(self, asset_id: str) -> Path | None:
        value = str(asset_id or "").strip()
        if not _SAFE_ASSET_ID.fullmatch(value):
            return None
        with self._lock:
            for item in (self._index.get("tracks") or {}).values():
                if isinstance(item, dict) and item.get("assetId") == value:
                    return self._contained_file(item.get("file"))
            for key, item in (self._manifest.get("tracks") or {}).items():
                if not isinstance(item, dict):
                    continue
                if self._manifest_asset_id(str(key), item) == value:
                    return self._contained_file(item.get("file"))
        return None

    def asset_mime(self, asset_id: str) -> str:
        with self._lock:
            for item in (self._index.get("tracks") or {}).values():
                if isinstance(item, dict) and item.get("assetId") == asset_id:
                    return item.get("mimeType") or "application/octet-stream"
            for key, item in (self._manifest.get("tracks") or {}).items():
                if isinstance(item, dict) and self._manifest_asset_id(str(key), item) == asset_id:
                    return item.get("mimeType") or mimetypes.guess_type(str(item.get("file") or ""))[0] or "application/octet-stream"
        return "application/octet-stream"
