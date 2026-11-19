/* Artist discovery belongs to this studio. Production stays in index.html. */
(() => {
  const legacyRender = renderArtistResultStage;
  const states = new Map();
  const roles = ['演唱', '作词', '作曲', '编曲', '制作', '演奏'];
  let active = null;
  const html = value => esc(String(value ?? ''));
  const sourceName = source => source === 'qq' ? 'QQ音乐' : source === 'kugou' ? '酷狗音乐' : '网易云音乐';
  const dateKey = value => String(value || '').split(/\D/).map((n, i) => i ? n.padStart(2, '0') : n).join('');
  const albumsOf = state => (state.base.albumList || []).slice().sort((a, b) => dateKey(b.date).localeCompare(dateKey(a.date)));
  const visible = state => active === state && !!document.querySelector('#albStage:not([hidden]) > .catalog-shell');
  const snapshot = state => ({...state.base, _catalog: {tab: state.tab, role: state.role, offset: state.offset, all: state.all, scrollTop: state.scrollTop || 0}});

  function navigate(state, changes) {
    Object.assign(state, changes, {scrollTop: 0});
    render(state);
    pushAppRoute('artist', {data: snapshot(state)});
  }

  function loadProfile(state) {
    if (state.profile || state.profilePending) return;
    state.profilePending = true;
    state.profileError = '';
    (window.ArtistDiscovery?.profile(state.name) || jget('/api/artist/profile?name=' + encodeURIComponent(state.name), 20000))
      .then(data => { state.profile = data.artist; })
      .catch(error => { state.profileError = error.message || '资料加载失败'; })
      .finally(() => { state.profilePending = false; if (visible(state)) render(state); });
  }

  function pageKey(state) { return `${state.role}:${state.offset}`; }
  function loadWorks(state) {
    if (!state.profile) return;
    const key = pageKey(state);
    if (state.pages.has(key) || state.pending.has(key)) return;
    state.pending.add(key);
    state.errors.delete(key);
    const params = new URLSearchParams({id: state.profile.id, role: state.role, limit: 50, offset: state.offset});
    jget('/api/artist/works?' + params, 22000)
      .then(data => { state.pages.set(key, data); })
      .catch(error => { state.errors.set(key, error.message || '作品加载失败'); })
      .finally(() => {
        state.pending.delete(key);
        if (visible(state) && state.tab === 'songs' && pageKey(state) === key) render(state);
      });
  }

  function albumCards(albums, selection) {
    return albums.map((album, index) => {
      const title = html(album.name || '未命名专辑');
      const cover = `<button class="catalog-album" type="button" data-catalog-album="${index}"><img loading="lazy" src="${html(asset(album.pic || ''))}" alt=""><b>${title}</b><small>${html([album.date, album.type].filter(Boolean).join(' · '))}</small></button>`;
      if (!selection) return cover;
      return `<article class="catalog-album-card">${cover}<label class="catalog-album-select"><input type="checkbox" data-pick-album="${index}" aria-label="选择 ${title}"${album.name && album.pic ? '' : ' disabled'}></label><button type="button" class="catalog-album-design" data-design-album="${index}" aria-label="设计并打印 ${title}">设计并打印</button></article>`;
    }).join('');
  }

  function bindAlbumSelection(box, albums, state) {
    const selection = state.albumSelection;
    const checks = [...box.querySelectorAll('[data-pick-album]')];
    const selectedCount = box.querySelector('[data-album-count]');
    const start = box.querySelector('[data-design-selected]');
    if (!selectedCount || !start) return;
    const sync = () => {
      for (const check of checks) {
        check.checked = !check.disabled && selection.has(albums[Number(check.dataset.pickAlbum)]);
        check.closest('article').classList.toggle('is-picked', check.checked);
      }
      selectedCount.textContent = `已选 ${selection.size} / ${albums.length} 张`;
      start.disabled = !selection.size;
      start.textContent = selection.size ? `批量制作（${selection.size} 张）` : '批量制作';
    };
    for (const check of checks) {
      check.onchange = () => {
        const album = albums[Number(check.dataset.pickAlbum)];
        if (check.checked) selection.add(album);
        else selection.delete(album);
        sync();
      };
    }
    box.querySelector('[data-pick-all]').onclick = () => {
      for (const check of checks) if (!check.disabled) selection.add(albums[Number(check.dataset.pickAlbum)]);
      sync();
    };
    box.querySelector('[data-pick-none]').onclick = () => { selection.clear(); sync(); };
    start.onclick = () => openAlbumBatch(albums.filter(album => selection.has(album)), state.name);
    box.querySelectorAll('[data-design-album]').forEach(button => {
      button.onclick = () => openAlbumStudio(albums[Number(button.dataset.designAlbum)]);
    });
    sync();
  }

  function biography(state, expanded) {
    const text = state.profile?.brief;
    return `<section class="catalog-bio"><div class="catalog-section-title"><h3>歌手简介</h3><span>网易云音乐资料</span></div>${text ? `<p class="${expanded ? 'is-expanded' : ''}">${html(text)}</p>${text.length > 120 ? `<button type="button" class="catalog-link" data-bio-toggle>${expanded ? '收起简介' : '展开全部'}</button>` : ''}` : `<p>${state.profileError ? '歌手资料暂未加载，歌曲与专辑仍可浏览。' : state.profilePending ? '正在加载歌手资料…' : '暂无歌手简介'}</p>${state.profileError ? '<button class="catalog-link" type="button" data-profile-retry>重试资料</button>' : ''}`}</section>`;
  }

  function render(state) {
    active = state;
    const box = document.querySelector('#albStage');
    if (!box) return;
    let legacy = null;
    const page = state.pages.get(pageKey(state));
    const usePopular = state.role === 1 && !state.all;
    const songs = usePopular ? state.base.songs || [] : page?.songs || [];
    if (state.tab === 'songs') {
      const data = {...snapshot(state), songs, source: usePopular ? state.base.source : '163', _noCap: true};
      legacyRender(data);
      legacy = box.querySelector('.music-page');
      legacy?.querySelector('.artist-info')?.remove();
      legacy?.querySelector('.artist-summary')?.remove();
      legacy?.querySelector('#artistSongMode')?.remove();
      const heading = legacy?.querySelector('.track-head h3');
      if (heading) heading.textContent = usePopular ? '热门歌曲' : `全部${roles[state.role - 1]}作品`;
      const count = legacy?.querySelector('.track-head > span');
      if (count) count.textContent = usePopular ? `${songs.length} 首 · ${sourceName(state.base.source)}` : `第 ${Math.floor(state.offset / 50) + 1} 页 · 共 ${page?.total ?? '—'} 首 · 网易云音乐`;
      legacy?.querySelectorAll('.artist-track .no').forEach((el, index) => { el.textContent = state.offset + index + 1; });
    } else {
      LAST_ARTIST_DATA = snapshot(state);
      STAGE_ALBUM_CTX = null;
      hideAppBack();
    }
    const profile = state.profile || {};
    const albums = albumsOf(state);
    const heroPic = profile.pic || state.base.artist?.pic || albums[0]?.pic || '';
    const counts = [profile.musicSize ? `${profile.musicSize} 首歌曲` : '', `${profile.albumSize || albums.length} 张专辑`, profile.mvSize ? `${profile.mvSize} 个视频` : ''].filter(Boolean).join(' · ');
    const selectedAlbums = state.tab === 'home' ? albums.slice(0, 6) : albums;
    const error = state.errors.get(pageKey(state));
    let content = '';
    if (state.tab === 'home') content = biography(state, state.expanded) + `<section><div class="catalog-section-title"><h3>最近专辑</h3><button type="button" class="catalog-link" data-go-albums>查看全部 ${albums.length} 张 →</button></div><div class="catalog-albums">${albumCards(selectedAlbums)}</div>${!albums.length ? '<p class="catalog-empty">暂未取到专辑列表</p>' : ''}</section>`;
    if (state.tab === 'bio') content = biography(state, true);
    if (state.tab === 'albums') content = `<div class="catalog-section-title"><h3>全部专辑</h3><span>按发行时间排序 · ${albums.length} 张</span></div>${albums.length ? `<div class="catalog-album-toolbar"><span data-album-count aria-live="polite"></span><button type="button" data-pick-all>全选</button><button type="button" data-pick-none>清空</button><button type="button" data-design-selected disabled>批量制作</button></div><div class="catalog-albums">${albumCards(selectedAlbums, state.albumSelection)}</div>` : '<p class="catalog-empty">暂未取到专辑列表</p>'}`;
    if (state.tab === 'songs') {
      content = `<div class="catalog-rolebar" role="group" aria-label="作品分类">${roles.map((role, index) => `<button type="button" data-role="${index + 1}" aria-pressed="${state.role === index + 1}">${role}</button>`).join('')}</div><div class="catalog-song-status">${usePopular ? `<span>热门推荐 · 保留多来源补全</span><button class="catalog-link" type="button" data-all-works>查看全部演唱作品 →</button>` : `<span>网易云音乐 · ${html(roles[state.role - 1])}分类 · 按热度排序</span>${state.role === 1 ? '<button class="catalog-link" type="button" data-popular>返回热门推荐</button>' : ''}`}</div><div class="catalog-track-mount"></div>`;
      if (!usePopular) {
        if (!state.profile) content += `<div class="catalog-empty">${state.profileError ? '歌手资料加载失败，请重试后浏览分类。<button type="button" data-profile-retry>重试资料</button>' : '正在匹配歌手资料…'}</div>`;
        else if (error) content += `<div class="catalog-empty">作品加载失败：${html(error)} <button type="button" data-works-retry>重试</button></div>`;
        else if (!page) content += '<p class="catalog-empty" role="status">正在加载作品…</p>';
        else if (!songs.length) content += `<p class="catalog-empty">数据源暂无「${html(roles[state.role - 1])}」分类作品。</p>`;
        if (page && (state.offset || page.more)) content += `<nav class="catalog-pagination" aria-label="作品分页"><button type="button" data-page-prev ${state.offset ? '' : 'disabled'}>上一页</button><span>第 ${Math.floor(state.offset / 50) + 1} 页</span><button type="button" data-page-next ${page.more && songs.length ? '' : 'disabled'}>下一页</button></nav>`;
      }
    }
    box.className = 'albStage music-search-stage artist-catalog-stage';
    box.innerHTML = `<div class="catalog-shell"><header class="catalog-hero">${heroPic ? `<img class="catalog-hero-bg" src="${html(asset(heroPic))}" alt="">` : ''}<div class="catalog-hero-shade"></div><div class="catalog-hero-copy"><span class="catalog-eyebrow">ARTIST / 歌手主页</span><h2>${html(profile.name || state.name)}</h2><p>${html((profile.aliases || []).join(' / '))}</p><p>${html(counts)}</p><div class="catalog-hero-actions"><button type="button" data-go-songs>浏览歌曲</button><button type="button" data-make-hot>按热门制作</button></div></div></header><nav class="catalog-tabs" aria-label="歌手导航">${[['home','主页'],['songs','歌曲'],['albums',`专辑 ${albums.length}`],['bio','歌手简介']].map(([key, label]) => `<button type="button" data-tab="${key}" aria-current="${key === state.tab ? 'page' : 'false'}">${label}</button>`).join('')}</nav><div class="catalog-content">${content}</div></div>`;
    if (legacy) {
      box.querySelector('.catalog-track-mount').append(legacy);
      if (!usePopular && !songs.length) legacy.querySelector('.track-table')?.remove();
    }
    box.scrollTop = state.scrollTop || 0;
    box.onscroll = () => { if (visible(state)) state.scrollTop = box.scrollTop; };
    queueMicrotask(() => {
      if (visible(state)) setTitle(state.name + ' · 歌手主页',
        state.tab === 'songs' ? `${roles[state.role - 1]}作品 · 选择歌曲后制作商品` : counts + ' · 选择歌曲或专辑后制作商品');
    });
    box.querySelectorAll('[data-tab]').forEach(button => { button.onclick = () => navigate(state, {tab: button.dataset.tab}); });
    box.querySelector('[data-go-songs]').onclick = () => navigate(state, {tab: 'songs'});
    box.querySelector('[data-make-hot]').onclick = () => openHotMaker(state.base);
    box.querySelector('[data-go-albums]')?.addEventListener('click', () => navigate(state, {tab: 'albums'}));
    if (state.tab === 'albums') bindAlbumSelection(box, selectedAlbums, state);
    box.querySelector('[data-bio-toggle]')?.addEventListener('click', () => { state.expanded = !state.expanded; render(state); });
    box.querySelectorAll('[data-catalog-album]').forEach(button => { button.onclick = () => openAlbumDetail(selectedAlbums[Number(button.dataset.catalogAlbum)]); });
    box.querySelectorAll('[data-role]').forEach(button => { button.onclick = () => navigate(state, {role: Number(button.dataset.role), offset: 0, all: Number(button.dataset.role) !== 1}); });
    box.querySelector('[data-all-works]')?.addEventListener('click', () => navigate(state, {all: true, offset: 0}));
    box.querySelector('[data-popular]')?.addEventListener('click', () => navigate(state, {all: false, offset: 0}));
    box.querySelector('[data-page-prev]')?.addEventListener('click', () => navigate(state, {offset: Math.max(0, state.offset - 50)}));
    box.querySelector('[data-page-next]')?.addEventListener('click', () => navigate(state, {offset: state.offset + 50}));
    box.querySelectorAll('[data-profile-retry]').forEach(button => { button.onclick = () => { loadProfile(state); render(state); }; });
    box.querySelector('[data-works-retry]')?.addEventListener('click', () => { state.errors.delete(pageKey(state)); loadWorks(state); render(state); });
    if (!state.profile && !state.profileError) loadProfile(state);
    if (state.tab === 'songs' && !usePopular && !page && !error) loadWorks(state);
  }

  renderArtistResultStage = function(data) {
    if (data._album || data.searchKind === 'song') {
      active = null;
      legacyRender(data);
      return;
    }
    const name = data.artist?.name || ARTIST_Q;
    if (!name) return legacyRender(data);
    let state = states.get(name);
    if (!state || (!data._catalog && state.base !== data)) {
      state = {name, base: data, tab: 'home', role: 1, offset: 0, all: false, expanded: false,
        profile: null, profilePending: false, profileError: '', pages: new Map(), errors: new Map(), pending: new Set(), albumSelection: new Set()};
      if (states.size >= 20) states.delete(states.keys().next().value);
      states.set(name, state);
    }
    if (data._catalog) Object.assign(state, data._catalog);
    render(state);
  };
})();

/* Shared artist portraits for home shortcuts and search suggestions. */
(() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const picture = value => /^https?:\/\//i.test(String(value || '')) ? String(value) : '';
  const requests = new Map(), profiles = new Map();
  const queue = [];
  let running = 0;
  let portraits = {};
  try { portraits = JSON.parse(localStorage.getItem('fold-artist-portraits') || '{}'); } catch (_) {}
  if (!portraits || typeof portraits !== 'object' || Array.isArray(portraits)) portraits = {};
  portraits = Object.fromEntries(Object.entries(portraits).filter(([,value]) => value && Number.isFinite(value.time) && picture(value.pic)));

  function cachedPicture(name) {
    const hit = portraits[name];
    return hit && Date.now() - hit.time < 86400000 ? picture(hit.pic) : '';
  }
  function pump() {
    while (running < 3 && queue.length) {
      const job = queue.shift();
      running++;
      jget('/api/artist/profile?name=' + encodeURIComponent(job.name), 20000)
        .then(job.resolve, job.reject)
        .finally(() => { running--; pump(); });
    }
  }
  function profile(name) {
    if (profiles.has(name)) return Promise.resolve(profiles.get(name));
    if (requests.has(name)) return requests.get(name);
    const request = new Promise((resolve, reject) => { queue.push({name, resolve, reject}); pump(); })
      .then(data => {
        if (profiles.size >= 40) profiles.delete(profiles.keys().next().value);
        profiles.set(name, data);
        const pic = picture(data.artist?.pic);
        if (pic) {
          portraits[name] = {pic, time: Date.now()};
          portraits = Object.fromEntries(Object.entries(portraits).sort((a,b) => b[1].time-a[1].time).slice(0,40));
          try { localStorage.setItem('fold-artist-portraits', JSON.stringify(portraits)); } catch (_) {}
        }
        return data;
      }).finally(() => requests.delete(name));
    requests.set(name, request);
    return request;
  }
  function avatar(name, pic) {
    const url = picture(pic) || cachedPicture(name);
    return `<span class="artist-avatar" data-artist-avatar="${escape(name)}"><span class="artist-avatar-fallback" aria-hidden="true">${escape(Array.from(name)[0] || '♪')}</span><img alt="" ${url ? `data-avatar-url="${escape(url)}"` : ''}></span>`;
  }
  function rows(artists, query = '') {
    const seen = new Set();
    const exact = (artists || []).filter(a => a.name?.toLocaleLowerCase() === query.trim().toLocaleLowerCase());
    return (exact.length ? exact : artists || []).filter(a => a.name && !seen.has(a.name) && seen.add(a.name)).slice(0,5)
      .map(a => `<button class="search-popover__row search-popover__artist" type="button" data-search-artist="${escape(a.name)}">${avatar(a.name,a.pic)}<span><b>${escape(a.name)}</b><small>歌手 · 查看主页、歌曲和专辑</small></span><i aria-hidden="true">→</i></button>`).join('');
  }
  function hydrate(root) {
    root.querySelectorAll('[data-artist-avatar]').forEach(holder => {
      if (holder.dataset.avatarBound) return;
      holder.dataset.avatarBound = '1';
      const image = holder.querySelector('img');
      const set = url => {
        url = picture(url);
        if (!url || !holder.isConnected) return;
        image.onload = () => holder.classList.add('has-picture');
        image.onerror = () => { holder.classList.remove('has-picture'); image.hidden = true; };
        image.hidden = false;
        image.src = url;
      };
      if (image.dataset.avatarUrl) set(image.dataset.avatarUrl);
      else profile(holder.dataset.artistAvatar).then(data => set(data.artist?.pic)).catch(() => {});
    });
  }
  window.ArtistDiscovery = {rows, hydrate, profile};
  const quick = document.querySelector('.discover-home__quick');
  if (!quick) return;
  const names = ['周杰伦','G-DRAGON','林俊杰','陈奕迅','邓紫棋','Taylor Swift','薛之谦','IU','Adele','Bruno Mars'];
  const section = document.createElement('section');
  section.className = 'discover-artists';
  section.setAttribute('aria-label','热门歌手');
  section.innerHTML = `<div class="discover-artists-heading"><h3>热门歌手</h3><span>点头像进入歌手主页</span></div><div class="discover-artists-list">${names.map(name => `<button type="button" class="discover-artist" data-discover-artist="${escape(name)}">${avatar(name)}<b>${escape(name)}</b></button>`).join('')}</div>`;
  quick.closest('.discover-home').after(section);
  quick.remove();
  section.addEventListener('click', event => {
    const button = event.target.closest('[data-discover-artist]');
    if (!button) return;
    event.stopPropagation();
    window.goArtistPage(button.dataset.discoverArtist);
  });
  hydrate(section);
})();
