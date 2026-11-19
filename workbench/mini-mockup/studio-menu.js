/* Migrated drawer and player-style reference library. Selections are sent to the player renderer. */
(() => {
  const base = '/mini-mockup/player-skins/';
  const storageKey = 'fold-player-skin-reference';
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const entries = [
    ['vip','♫','免费听 VIP 歌曲','未接入'], ['messages','✉','我的消息','未接入'],
    ['membership','◎','我的会员','未接入'], ['dress','✿','装扮中心','播放器样式 ›'],
    ['creator','♧','创作者中心','作品库 ›'], ['recent','◷','最近播放','暂无记录'],
    ['timer','◴','定时关闭','未接入'], ['shop','▢','商城','未接入'], ['tickets','◇','云村有票','未接入']
  ];
  let catalog = null, loading = null, selection = null;
  let savedId = '';
  try { savedId = JSON.parse(localStorage.getItem(storageKey) || 'null')?.id || ''; } catch (_) {}
  const imageUrl = path => asset(base + path);
  function loadCatalog() {
    if (catalog) return Promise.resolve(catalog);
    if (loading) return loading;
    loading = fetch(imageUrl('catalog.json')).then(response => {
      if (!response.ok) throw new Error('样式目录加载失败');
      return response.json();
    }).then(data => {
      catalog = data;
      selection = data.skins.find(skin => skin.id === savedId) || null;
      syncMaker();
      return data;
    }).finally(() => { loading = null; });
    return loading;
  }
  function dialog(title, className = '') {
    const element = document.createElement('dialog');
    element.className = 'studio-dialog ' + className;
    element.setAttribute('aria-label',title);
    element.innerHTML = `<header class="studio-dialog-head"><h2>${escape(title)}</h2><button type="button" data-dialog-close aria-label="关闭${escape(title)}">×</button></header><div class="studio-dialog-body"></div>`;
    document.body.append(element);
    element.querySelector('[data-dialog-close]').onclick = () => element.close();
    element.addEventListener('click', event => { if (event.target === element) element.close(); });
    element.addEventListener('close', () => element.remove(), {once:true});
    element.showModal();
    return element;
  }
  function info(title, text) {
    const view = dialog(title,'studio-info-dialog');
    view.querySelector('.studio-dialog-body').innerHTML = `<div class="studio-info-empty"><span aria-hidden="true">○</span><h3>${escape(title)}</h3><p>${escape(text)}</p><button type="button" class="studio-primary">知道了</button></div>`;
    view.querySelector('.studio-primary').onclick = () => view.close();
  }
  const notes = {
    vip:'此入口已加入。工作台目前用于制作音乐周边，尚未接入音乐播放及 VIP 音乐授权服务。',
    messages:'消息入口已加入，站内消息服务尚未接入，目前没有可展示的消息。',
    membership:'会员入口已加入，当前工作台尚未接入账号和会员服务。',
    recent:'当前工作台尚未接入音乐播放功能，因此没有最近播放记录。已制作的商品可在作品库查看。',
    timer:'定时关闭入口已加入。音乐播放器接入后才能设置播放停止时间，不会关闭当前制作任务或电脑。',
    shop:'商城入口已加入，商品购买服务尚未接入。',
    tickets:'云村有票入口已加入，票务服务尚未接入。'
  };
  function settings() {
    const view = dialog('设置','studio-info-dialog');
    const body = view.querySelector('.studio-dialog-body');
    body.innerHTML = '<p class="studio-muted">复用工作台现有设置，立即生效。</p><button class="studio-setting" type="button" data-theme-setting>切换浅色 / 深色主题 →</button><button class="studio-setting" type="button" data-watermark-setting>商品图水印设置 →</button><button class="studio-setting" type="button" data-skin-setting>播放器样式 →</button>';
    body.querySelector('[data-theme-setting]').onclick = () => document.querySelector('#btnTheme').click();
    body.querySelector('[data-watermark-setting]').onclick = () => { view.close(); document.querySelector('#productWatermarkButton').click(); };
    body.querySelector('[data-skin-setting]').onclick = () => { view.close(); openDress(); };
  }
  function openDrawer() {
    const view = dialog('工作台菜单','studio-drawer');
    const body = view.querySelector('.studio-dialog-body');
    body.innerHTML = `<div class="studio-drawer-banner"><b>拾音工坊</b><span>音乐周边制作 · 装扮中心</span></div><nav aria-label="工作台菜单">${entries.map(([id,icon,name,status])=>`<button type="button" class="studio-menu-item ${id==='dress'?'is-featured':''}" data-menu="${id}"><i aria-hidden="true">${icon}</i><span>${name}</span><small>${status}</small></button>`).join('')}</nav><footer class="studio-drawer-foot"><button type="button" data-settings>⚙ 设置</button><button type="button" data-more>⊞ 更多</button></footer>`;
    body.querySelectorAll('[data-menu]').forEach(button => { button.onclick = () => {
      const id = button.dataset.menu;
      view.close();
      if (id === 'dress') return openDress();
      if (id === 'creator') return document.querySelector('#btnLib').click();
      info(entries.find(entry=>entry[0]===id)[2],notes[id]);
    }; });
    body.querySelector('[data-settings]').onclick = () => { view.close(); settings(); };
    body.querySelector('[data-more]').onclick = () => { view.close(); info('更多','侧栏入口已全部保留。账号、音乐播放、商城和票务等服务尚未接入；可用的播放器样式在装扮中心查看。'); };
  }
  function preview(skin) {
    const view = dialog(skin.name,'studio-preview-dialog');
    view.querySelector('.studio-dialog-body').innerHTML = `<img class="studio-skin-preview" src="${escape(imageUrl(skin.preview))}" alt="${escape(skin.name)}"><p class="studio-muted">原播放器演示素材，仅作样式参考；图中歌曲不会用于你的商品出图。</p>`;
  }
  function openDress() {
    const view = dialog('装扮中心','studio-dress-dialog');
    const body = view.querySelector('.studio-dialog-body');
    let panel = '播放器样式', category = '推荐', draft = selection?.id || savedId || '';
    body.innerHTML = '<p class="studio-info-empty" role="status">正在加载播放器样式…</p>';
    loadCatalog().then(data => {
      if (!view.isConnected) return;
      if (!data.skins.some(skin=>skin.id===draft)) draft='';
      function render() {
        const list = category === '推荐' ? data.skins : data.skins.filter(skin=>skin.category===category);
        const chosen = data.skins.find(skin=>skin.id===draft);
        body.innerHTML = `<div class="studio-dress-panels" aria-label="装扮栏目">${data.panels.map(name=>`<button type="button" data-panel="${escape(name)}" aria-pressed="${name===panel}">${escape(name)}</button>`).join('')}</div><p class="studio-reference-note">每款装扮都关联出图版式。示例图用于参考，新出图按对应风格重绘并带入当前歌曲的封面和文字。</p>${panel==='播放器样式'?`<div class="studio-dress-cats" aria-label="样式分类">${data.categories.map(name=>`<button type="button" data-category="${escape(name)}" aria-pressed="${name===category}">${escape(name)}</button>`).join('')}</div><div class="studio-dress-summary">${escape(category)} · ${list.length} 款样式</div><div class="studio-skin-grid">${list.map(skin=>`<article class="studio-skin-card ${skin.id===draft?'is-selected':''}"><label><input type="radio" name="studio-player-skin" value="${escape(skin.id)}" ${skin.id===draft?'checked':''}><img loading="lazy" src="${escape(imageUrl(skin.preview))}" alt=""><b>${escape(skin.name)}</b><small>${escape(skin.category)} · 可出图</small></label><button type="button" data-preview="${escape(skin.id)}" aria-label="放大预览${escape(skin.name)}">放大预览</button></article>`).join('')}</div>${list.length?'':'<p class="studio-info-empty">此分类暂未采集到素材。</p>'}`:`<p class="studio-info-empty">「${escape(panel)}」入口已保留，当前尚未接入素材与功能。</p>`}<p class="studio-skin-source">素材来源：${escape(data.source)}<br>${escape(data.api_note || '')}</p><footer class="studio-dress-footer"><span>当前选择<b>${escape(chosen?.name || '默认样式')}</b></span><div><button type="button" data-reset>恢复默认</button><button type="button" data-cancel>取消</button><button type="button" data-confirm class="studio-primary">确定选择</button></div></footer>`;
        body.querySelectorAll('[data-panel]').forEach(button=> {button.onclick=()=>{panel=button.dataset.panel;render();};});
        body.querySelectorAll('[data-category]').forEach(button=> {button.onclick=()=>{category=button.dataset.category;render();};});
        body.querySelectorAll('input[name="studio-player-skin"]').forEach(input=> {input.onchange=()=>{draft=input.value;render();};});
        body.querySelectorAll('[data-preview]').forEach(button=> {button.onclick=()=>preview(data.skins.find(skin=>skin.id===button.dataset.preview));});
        body.querySelector('[data-reset]').onclick=()=>{draft='';render();};
        body.querySelector('[data-cancel]').onclick=()=>view.close();
        body.querySelector('[data-confirm]').onclick=()=>{
          const selected = data.skins.find(skin=>skin.id===draft) || null;
          try { localStorage.setItem(storageKey,JSON.stringify(selected?{id:selected.id}:null)); }
          catch (_) { return toast('浏览器未能保存选择，请检查存储空间后重试'); }
          selection=selected; savedId=selected?.id || ''; syncMaker(); view.close();
          toast(selected?'已选择播放器样式：'+selected.name:'已恢复默认样式');
        };
      }
      render();
    }).catch(()=>{
      if (!view.isConnected) return;
      body.innerHTML='<p class="studio-info-empty">样式目录暂时未能加载。</p><button class="studio-setting" type="button">重试</button>';
      body.querySelector('button').onclick=()=>{view.close();openDress();};
    });
  }
  function syncMaker() {
    document.querySelectorAll('.song-maker-page').forEach(page => {
      let card=page.querySelector('[data-player-skin-reference]');
      if (!card) {
        card=document.createElement('div'); card.className='studio-maker-reference';
        card.setAttribute('data-player-skin-reference','');
        page.querySelector('.song-maker-details')?.before(card);
      }
      const stamp=selection?.id || 'default';
      if (card.dataset.selection===stamp) return;
      card.dataset.selection=stamp;
      card.innerHTML=`${selection?`<img src="${escape(imageUrl(selection.preview))}" alt="">`:''}<span><b>播放器样式：${escape(selection?.name || '默认样式')}</b><small>${selection ? '新出图将应用这款版式，并带入当前歌曲。' : '使用工作台默认播放界面。'}</small></span><button type="button">更换样式</button>`;
      card.querySelector('button').onclick=openDress;
    });
  }
  const menuButton=document.createElement('button');
  menuButton.type='button'; menuButton.className='studio-menu-trigger';
  menuButton.setAttribute('aria-label','工作台菜单'); menuButton.textContent='☰';
  menuButton.onclick=openDrawer;
  document.querySelector('.bar')?.prepend(menuButton);
  const stage=document.querySelector('#albStage');
  if (stage) new MutationObserver(syncMaker).observe(stage,{childList:true,subtree:true});
  window.StudioMenu={open:openDrawer,openDress,getSelectionId:()=>savedId};
  if (savedId) loadCatalog().catch(()=>{});
})();
