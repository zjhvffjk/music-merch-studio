"""Real-browser smoke test for the local authorized-audio playback flow."""
from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.request
import uuid
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "workbench")]
import server
from playback_service import PlaybackLibrary


def tone(path: Path, seconds: int = 5) -> None:
    rate = 22050
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        frames = bytearray()
        for sample in range(rate * seconds):
            frames += struct.pack("<h", int(6000 * math.sin(2 * math.pi * 440 * sample / rate)))
        audio.writeframes(frames)


def upload(base: str, source: str, track_id: str, audio_path: Path) -> None:
    request = urllib.request.Request(
        f"{base}/api/audio/upload?source={source}&id={track_id}&name={audio_path.name}",
        data=audio_path.read_bytes(),
        method="POST",
        headers={"Content-Type": "audio/wav"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("playable"):
        raise AssertionError(payload)


def cli(session: str, *args: str) -> str:
    node = shutil.which("node")
    npx_cli = Path(node).parent / "node_modules" / "npm" / "bin" / "npx-cli.js" if node else None
    if not node or not npx_cli or not npx_cli.is_file():
        raise RuntimeError("npx is required for the browser smoke test")
    if args and args[0] == "run-code" and len(args) > 1:
        args = (args[0], " ".join(line.strip() for line in args[1].splitlines()))
    command = [node, str(npx_cli), "--yes", "--package", "@playwright/cli", "playwright-cli", f"-s={session}", *args]
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise AssertionError((result.stdout + "\n" + result.stderr).strip())
    return result.stdout


def main() -> None:
    session = "music-playback-" + uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix="music-playback-e2e-") as temp_dir:
        temp = Path(temp_dir)
        fixture = temp / "test-tone.wav"
        tone(fixture)
        previous_library = server.PLAYBACK
        server.PLAYBACK = PlaybackLibrary(temp / "library", temp / "manifest.json")
        httpd = server.Server(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            upload(base, "local", "e2e-player", fixture)
            cli(session, "open", base + "/")
            open_script = '''async page => {
              const show = async track => page.evaluate(t => {
                renderArtistResultStage({artist:{name:t.artist},source:t.source,songs:[t],albumList:[]});
                showAlbumStage();
              }, track);
              const ready = {id:'e2e-player',source:'local',trackKey:'local:e2e-player',name:'浏览器播放测试',artist:'本地测试',album:'测试专辑',dur:'00:05',pic:'',playbackState:'playable'};
              await show(ready);
              await page.locator('[data-play-context="artist"]').click();
              await page.waitForFunction(() => !document.querySelector('#workbenchPlayer').hidden && document.querySelector('#workbenchAudio').currentTime > .1);
              return {ok:true};
            }'''
            cli(session, "run-code", open_script)
            controls_script = '''async page => {
              const ensure = (value, message) => { if (!value) throw new Error(message); };
              await page.locator('#playerToggle').click();
              ensure(await page.locator('#workbenchAudio').evaluate(a => a.paused), 'pause control failed');
              await page.locator('#playerToggle').click();
              await page.locator('#playerProgress').evaluate(input => { input.value='1.2'; input.dispatchEvent(new Event('input',{bubbles:true})); });
              ensure(await page.locator('#workbenchAudio').evaluate(a => a.currentTime >= 1), 'seek failed');
              return {ok:true};
            }'''
            cli(session, "run-code", controls_script)
            overlay_script = '''async page => {
              const ensure = (value, message) => { if (!value) throw new Error(message); };
              await page.locator('#playerExpand').click();
              ensure(await page.locator('#nowPlayingDialog').isVisible(), 'full player did not open');
              const before = await page.locator('#workbenchAudio').evaluate(a => a.currentTime);
              await page.locator('#nowPlayingClose').click();
              await page.waitForTimeout(250);
              const after = await page.locator('#workbenchAudio').evaluate(a => a.currentTime);
              ensure(after > before, 'closing the full player stopped audio');
              await page.locator('#playerQueue').click();
              ensure(await page.locator('#queueDrawer').isVisible(), 'queue did not open');
              await page.locator('#queueClose').click();
              return {ok:true};
            }'''
            cli(session, "run-code", overlay_script)
            switch_script = '''async page => {
              const ensure = (value, message) => { if (!value) throw new Error(message); };
              const unbound = {id:'e2e-import',source:'local',trackKey:'local:e2e-import',name:'导入测试',artist:'本地测试',album:'本地音频',dur:'00:05',pic:'',playbackState:'unavailable'};
              await page.evaluate(t => { renderArtistResultStage({artist:{name:t.artist},source:t.source,songs:[t],albumList:[]}); showAlbumStage(); }, unbound);
              await page.locator('[data-play-context="artist"]').click();
              await page.waitForFunction(() => !document.querySelector('#audioImportDialog').hidden);
              ensure(await page.locator('#workbenchAudio').evaluate(a => a.currentTime < .25), 'new unavailable track retained the previous track time');
              return {ok:true};
            }'''
            cli(session, "run-code", switch_script)
            import_script = f'''async page => {{
              const ensure = (value, message) => {{ if (!value) throw new Error(message); }};
              await page.locator('#audioImportFile').setInputFiles({json.dumps(str(fixture))});
              await page.locator('#importAudioSubmit').click();
              await page.waitForFunction(() => document.querySelector('#audioImportDialog').hidden && !document.querySelector('#workbenchAudio').paused && document.querySelector('#workbenchAudio').currentTime > .1);
              await page.locator('#playerExpand').click();
              await page.locator('#nowPlayingMaker').click();
              ensure((await page.locator('.song-maker-page h2').textContent()).includes('导入测试'), 'maker handoff changed the current track');
              await page.setViewportSize({{width:390,height:844}});
              ensure(await page.locator('#workbenchPlayer').isVisible(), 'compact player is hidden');
              await page.locator('#playerExpand').click();
              ensure((await page.locator('.now-playing-grid').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length)) === 1, 'mobile full player is not one column');
              return {{ok:true,current:await page.locator('#playerTitle').textContent()}};
            }}'''
            output = cli(session, "run-code", import_script)
            if '"ok":true' not in output.replace(" ", ""):
                raise AssertionError(output)
            print("PASS: real browser playback, import, queue, handoff, and mobile layout")
        finally:
            try:
                cli(session, "close")
            except Exception:
                pass
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=3)
            server.PLAYBACK = previous_library


if __name__ == "__main__":
    main()
