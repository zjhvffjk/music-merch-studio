(function () {
  "use strict";

  const STORAGE_KEY = "fold-workbench-player-v1";
  const contexts = new Map();
  const state = {queue: [], index: -1, mode: "loop", volume: 0.8, status: "paused"};
  let audio, bar, cover, title, artist, toggleButton, progress, elapsed, duration, volume, modeButton, statusBox;

  function trackKey(track) {
    if (track && track.trackKey) return String(track.trackKey);
    if (!track || !track.source || track.id === undefined || track.id === null) return "";
    return String(track.source).toLowerCase() + ":" + String(track.id);
  }

  function cleanTrack(track) {
    if (!track || !trackKey(track)) return null;
    return {
      id: track.id, source: String(track.source).toLowerCase(), trackKey: trackKey(track),
      name: track.name || "未命名歌曲", artist: track.artist || "未知歌手",
      album: track.album || "", dur: track.dur || "", pic: track.pic || "",
      albummid: track.albummid || "", playbackState: track.playbackState || "unknown"
    };
  }

  function loadSaved() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      state.queue = Array.isArray(saved.queue) ? saved.queue.map(cleanTrack).filter(Boolean).slice(0, 200) : [];
      state.index = Math.min(Math.max(Number(saved.index) || 0, 0), Math.max(0, state.queue.length - 1));
      state.mode = ["loop", "single", "random"].includes(saved.mode) ? saved.mode : "loop";
      state.volume = Math.min(1, Math.max(0, Number(saved.volume ?? 0.8)));
    } catch (_) {}
  }

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({queue: state.queue, index: state.index, mode: state.mode, volume: state.volume})); } catch (_) {}
  }

  function current() { return state.queue[state.index] || null; }
  function assetUrl(url) { return typeof window.asset === "function" ? window.asset(url) : url; }
  function apiUrl(url) { return assetUrl(url); }
  function formatTime(value) {
    if (!Number.isFinite(value) || value < 0) return "00:00";
    const mins = Math.floor(value / 60), secs = Math.floor(value % 60);
    return String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
  }

  async function getJson(url) {
    if (typeof window.jget === "function") return window.jget(url, 10000);
    const response = await fetch(apiUrl(url));
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "播放请求失败");
    return data;
  }

  function notify(message) {
    statusBox.textContent = message || "";
    if (message) setTimeout(() => { if (statusBox.textContent === message) statusBox.textContent = ""; }, 3600);
  }

  function emit() {
    document.dispatchEvent(new CustomEvent("workbench-player-change", {detail: {track: current(), state: state.status, index: state.index, queue: state.queue.slice()}}));
    document.querySelectorAll("[data-play-track]").forEach(button => {
      const queue = contexts.get(button.dataset.playContext || "default") || [];
      const track = queue[Number(button.dataset.playTrack)];
      const active = track && current() && trackKey(track) === trackKey(current());
      button.classList.toggle("is-current", !!active);
      button.textContent = active && !audio.paused ? "Ⅱ" : "▶";
      button.setAttribute("aria-label", active && !audio.paused ? "暂停" : "播放" + (track ? "《" + track.name + "》" : "歌曲"));
    });
  }

  function paint() {
    const track = current();
    const visible = !!track;
    bar.hidden = !visible;
    document.body.classList.toggle("player-visible", visible);
    if (!track) return emit();
    cover.src = track.pic ? assetUrl(track.pic) : "";
    cover.alt = track.name ? "《" + track.name + "》封面" : "歌曲封面";
    title.textContent = track.name;
    artist.textContent = [track.artist, track.album].filter(Boolean).join(" · ");
    toggleButton.textContent = audio.paused ? "▶" : "Ⅱ";
    toggleButton.setAttribute("aria-label", audio.paused ? "播放" : "暂停");
    progress.max = Number.isFinite(audio.duration) && audio.duration > 0 ? String(audio.duration) : "100";
    progress.value = Number.isFinite(audio.currentTime) ? String(audio.currentTime) : "0";
    elapsed.textContent = formatTime(audio.currentTime);
    duration.textContent = Number.isFinite(audio.duration) ? formatTime(audio.duration) : (track.dur || "--:--");
    volume.value = String(state.volume);
    modeButton.textContent = state.mode === "single" ? "单曲" : state.mode === "random" ? "随机" : "循环";
    modeButton.setAttribute("aria-label", "播放模式：" + modeButton.textContent);
    emit();
  }

  function setQueue(tracks, startIndex) {
    state.queue = (Array.isArray(tracks) ? tracks : []).map(cleanTrack).filter(Boolean).slice(0, 200);
    state.index = Math.min(Math.max(Number(startIndex) || 0, 0), Math.max(0, state.queue.length - 1));
    save(); paint();
  }

  function unavailable(track, response) {
    state.status = "unavailable"; paint();
    document.dispatchEvent(new CustomEvent("workbench-player-unavailable", {detail: {track, response}}));
    notify((response && response.reason) || "当前歌曲没有可播放音源");
  }

  async function loadCurrent(userRequested, remaining) {
    const track = current();
    if (!track) return false;
    state.status = "loading"; paint();
    try {
      const response = await getJson("/api/playback?source=" + encodeURIComponent(track.source) + "&id=" + encodeURIComponent(track.id));
      if (!response.playable) {
        if (userRequested) unavailable(track, response);
        else if (remaining > 0) return advance(1, false, remaining - 1);
        return false;
      }
      audio.src = assetUrl(response.asset.url);
      audio.load();
      audio.volume = state.volume;
      await audio.play();
      state.status = "playing"; save(); paint();
      return true;
    } catch (error) {
      state.status = "paused"; paint();
      notify(error && error.name === "NotAllowedError" ? "浏览器已阻止自动播放，请再点一次播放" : (error.message || "播放失败"));
      return false;
    }
  }

  function playTrack(track, queue) {
    const normalized = cleanTrack(track);
    if (!normalized) return Promise.resolve(false);
    if (Array.isArray(queue)) {
      const cleaned = queue.map(cleanTrack).filter(Boolean);
      const index = Math.max(0, cleaned.findIndex(item => item.trackKey === normalized.trackKey));
      setQueue(cleaned, index);
    } else {
      const found = state.queue.findIndex(item => item.trackKey === normalized.trackKey);
      if (found < 0) setQueue([normalized], 0); else state.index = found;
    }
    if (audio.src && current() && current().trackKey === normalized.trackKey && audio.paused && state.status !== "unavailable") {
      return audio.play().then(() => { state.status = "playing"; paint(); return true; });
    }
    return loadCurrent(true, state.queue.length);
  }

  function toggle(key) {
    if (key && current() && key !== current().trackKey) return false;
    if (!current()) return false;
    if (!audio.src || state.status === "unavailable") return loadCurrent(true, state.queue.length);
    if (audio.paused) return audio.play().then(() => { state.status = "playing"; paint(); return true; });
    audio.pause(); state.status = "paused"; paint(); return true;
  }

  function nextIndex(direction) {
    if (!state.queue.length) return -1;
    if (state.mode === "random" && state.queue.length > 1) {
      let next = state.index;
      while (next === state.index) next = Math.floor(Math.random() * state.queue.length);
      return next;
    }
    return (state.index + direction + state.queue.length) % state.queue.length;
  }

  function advance(direction, userRequested, remaining) {
    if (!state.queue.length || remaining <= 0) return Promise.resolve(false);
    state.index = nextIndex(direction); save(); paint();
    return loadCurrent(userRequested, remaining);
  }

  function registerContext(name, tracks) { contexts.set(name || "default", Array.isArray(tracks) ? tracks : []); emit(); }

  function init() {
    audio = document.getElementById("workbenchAudio");
    bar = document.getElementById("workbenchPlayer");
    cover = document.getElementById("playerCoverImage");
    title = document.getElementById("playerTitle"); artist = document.getElementById("playerArtist");
    toggleButton = document.getElementById("playerToggle"); progress = document.getElementById("playerProgress");
    elapsed = document.getElementById("playerElapsed"); duration = document.getElementById("playerDuration");
    volume = document.getElementById("playerVolume"); modeButton = document.getElementById("playerMode");
    statusBox = document.getElementById("playerStatus");
    if (!audio || !bar) return;
    loadSaved(); audio.volume = state.volume; paint();

    toggleButton.addEventListener("click", () => toggle());
    document.getElementById("playerPrevious").addEventListener("click", () => advance(-1, true, state.queue.length));
    document.getElementById("playerNext").addEventListener("click", () => advance(1, true, state.queue.length));
    progress.addEventListener("input", () => { if (Number.isFinite(audio.duration)) audio.currentTime = Number(progress.value); });
    volume.addEventListener("input", () => { state.volume = Number(volume.value); audio.volume = state.volume; save(); });
    modeButton.addEventListener("click", () => { state.mode = state.mode === "loop" ? "single" : state.mode === "single" ? "random" : "loop"; save(); paint(); });
    audio.addEventListener("play", () => { state.status = "playing"; paint(); });
    audio.addEventListener("pause", () => { if (state.status !== "unavailable") state.status = "paused"; paint(); });
    audio.addEventListener("timeupdate", paint); audio.addEventListener("loadedmetadata", paint);
    audio.addEventListener("ended", () => {
      if (state.mode === "single") { audio.currentTime = 0; audio.play(); }
      else advance(1, false, state.queue.length);
    });
    audio.addEventListener("error", () => { state.status = "paused"; notify("音频加载失败，请重新绑定音源"); paint(); });

    document.addEventListener("click", event => {
      const button = event.target.closest("[data-play-track]");
      if (!button) return;
      event.preventDefault(); event.stopPropagation();
      const queue = contexts.get(button.dataset.playContext || "default") || [];
      const track = queue[Number(button.dataset.playTrack)];
      if (!track) return;
      if (current() && trackKey(track) === trackKey(current()) && state.status !== "unavailable") toggle();
      else playTrack(track, queue);
    });
  }

  window.WorkbenchPlayer = {setQueue, playTrack, toggle, registerContext, current: current, state: () => ({...state, queue: state.queue.slice()})};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
