/* Mini CD image-model setup and component drafts. The production editor stays
   responsible for dimensional layout until each generated part is verified. */
(() => {
  const el = id => document.getElementById(id);
  if (!el('aiCard')) return;
  const targets = [
    ['disc', 'CD 盘面'], ['inside', '封面背面／内页'], ['back', '封底'],
    ['right-spine', '右侧封'], ['left-spine', '左侧封'],
    ['left-spine-back', '左侧封背面'], ['tray', '内盘底']
  ];
  const defaults = {openai: 'gpt-image-2.5-sunburst', gemini: 'gemini-nano-banana-2.1'};
  let profiles = [], defaultId = '', running = false, providerInfo = {};
  const images = {};
  const api = async (path, data, timeoutMs = 0) => {
    const controller = new AbortController();
    const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
      const response = await fetch('/api/design/ai/' + path, {
        method: data === undefined ? 'GET' : 'POST',
        headers: data === undefined ? {} : {'Content-Type': 'application/json'},
        body: data === undefined ? undefined : JSON.stringify(data),
        cache: 'no-store', signal: controller.signal
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw Error(result.error || ('HTTP ' + response.status));
      return result;
    } finally { if (timer) clearTimeout(timer); }
  };
  const status = message => { el('aiRunState').textContent = message; };
  const configStatus = (message, error = false) => {
    el('aiConfigState').textContent = message;
    el('aiConfigState').dataset.error = error ? 'true' : 'false';
  };
  const profileChoice = () => el('aiProfileSelect').value || defaultId;
  const selectedProfile = () => profiles.find(p => p.id === el('aiEditProfile').value);

  function showModelChoices() {
    const provider = el('aiProvider').value;
    const list = el('aiModelSuggestions');
    list.replaceChildren();
    for (const model of providerInfo[provider]?.models || []) {
      list.append(new Option(model, model));
    }
    el('aiModelHint').textContent = provider === 'gemini'
      ? '选择 Gemini 图片模型，也可填其他模型 ID。Google AI 会员与 API Key 额度分开；具体出图额度以密钥所属项目为准。'
      : '选择 OpenAI 图片模型，也可填其他支持图片编辑的模型 ID。';
  }

  function showKeyHint() {
    const profile = selectedProfile();
    const changedProvider = profile && profile.provider !== el('aiProvider').value;
    el('aiApiKey').placeholder = changedProvider ? '切换服务商后须填写新 API Key'
      : profile?.hasKey ? '已保存密钥；留空则保留' : '输入 API Key';
    el('aiKeyHint').textContent = changedProvider
      ? '不同服务商的密钥不能共用，请填写新服务商的 API Key。'
      : profile?.hasKey
        ? '✓ 密钥已安全保存在本机。这里不会回显；需要更换时输入新密钥再保存。'
        : '新建配置时请填写密钥；保存后不会再次显示完整内容。';
  }

  function drawCards() {
    const grid = el('aiComponentGrid');
    grid.replaceChildren();
    for (const [key, name] of targets) {
      const card = document.createElement('article');
      card.className = 'aiComp';
      if (images[key]?.url) {
        const img = document.createElement('img');
        img.src = images[key].url;
        img.alt = name + ' AI 草图';
        card.append(img);
      } else {
        const blank = document.createElement('div');
        blank.className = 'aiBlank';
        blank.textContent = '等待生成';
        card.append(blank);
      }
      const title = document.createElement('b'); title.textContent = name;
      const note = document.createElement('small');
      note.textContent = images[key]?.message || '可用文字单独修改';
      const actions = document.createElement('div'); actions.className = 'aiCompActions';
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'plain sm';
      button.textContent = images[key]?.url ? '按描述重绘' : '单独生成';
      button.disabled = running;
      button.onclick = () => generateOne(key, true);
      actions.append(button);
      if (images[key]?.url) {
        const link = document.createElement('a');
        link.href = images[key].url; link.download = '迷你CD-' + key + '.png';
        link.textContent = '下载图片'; link.className = 'plain sm';
        actions.append(link);
      }
      card.append(title, note, actions);
      grid.append(card);
    }
  }

  function fillEdit() {
    const profile = selectedProfile();
    el('aiProfileName').value = profile?.name || '';
    el('aiProvider').value = profile?.provider || 'gemini';
    el('aiModel').value = profile?.model || defaults.gemini;
    showModelChoices();
    el('aiApiKey').value = '';
    showKeyHint();
    el('aiMakeDefault').checked = Boolean(profile?.default || !profiles.length);
    configStatus('');
  }

  async function loadProfiles(preferred = '') {
    const data = await api('profiles');
    profiles = data.profiles || []; defaultId = data.default || '';
    providerInfo = data.providers || {};
    const select = el('aiProfileSelect');
    select.replaceChildren(new Option('选择图片模型', ''));
    for (const profile of profiles) {
      select.add(new Option(profile.name + ' · ' + profile.model + (profile.default ? '（默认）' : ''), profile.id));
    }
    select.value = preferred && profiles.some(p => p.id === preferred) ? preferred : defaultId;
    const edit = el('aiEditProfile');
    edit.replaceChildren(new Option('新建配置', ''));
    for (const profile of profiles) edit.add(new Option(profile.name + ' · ' + profile.model, profile.id));
    edit.value = preferred && profiles.some(p => p.id === preferred) ? preferred : defaultId;
    fillEdit();
  }

  el('btnAiSettings').onclick = () => el('aiConfigDialog').showModal();
  el('aiDialogClose').onclick = () => el('aiConfigDialog').close();
  el('aiEditProfile').onchange = fillEdit;
  el('aiProvider').onchange = () => {
    el('aiModel').value = providerInfo[el('aiProvider').value]?.model || defaults[el('aiProvider').value];
    showModelChoices();
    showKeyHint();
  };
  el('aiSaveProfile').onclick = async () => {
    try {
      configStatus('正在保存…');
      const data = await api('profile', {
        id: el('aiEditProfile').value,
        name: el('aiProfileName').value,
        provider: el('aiProvider').value,
        model: el('aiModel').value,
        apiKey: el('aiApiKey').value,
        makeDefault: el('aiMakeDefault').checked
      });
      await loadProfiles(data.profile.id);
      configStatus('配置已保存在本机。');
    } catch (error) { configStatus('保存失败：' + error.message); }
  };
  el('aiTestProfile').onclick = async () => {
    if (!el('aiEditProfile').value) return configStatus('请先保存配置，再验证密钥。');
    const button = el('aiTestProfile');
    button.disabled = true;
    try {
      configStatus('正在验证密钥和模型；此操作不生成图片，最多等待 30 秒…');
      const data = await api('test', {id: el('aiEditProfile').value}, 30000);
      configStatus(data.message);
    } catch (error) {
      configStatus(error.name === 'AbortError'
        ? '连接超时：工作台未能访问模型接口，请检查本机代理或网络。'
        : '连接失败：' + error.message, true);
    } finally { button.disabled = false; }
  };
  el('aiDeleteProfile').onclick = async () => {
    const id = el('aiEditProfile').value;
    if (!id) return configStatus('当前没有已保存的配置。');
    if (!confirm('删除此模型配置和本机保存的密钥？')) return;
    try {
      await api('delete', {id});
      await loadProfiles();
      configStatus('配置已删除。');
    } catch (error) { configStatus('删除失败：' + error.message); }
  };

  el('btnAiCoverUpload').onclick = () => el('aiCoverFile').click();
  el('aiCoverFile').onchange = async () => {
    const file = el('aiCoverFile').files?.[0];
    if (!file) return;
    try {
      status('正在上传封面…');
      const response = await fetch('/api/upload?name=' + encodeURIComponent(file.name), {
        method: 'POST', body: await file.arrayBuffer()
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || '上传失败');
      PIC = location.origin + '/api/design/ai/source?uid=' + encodeURIComponent(data.upload);
      el('cover').src = PIC; el('cover').hidden = false; el('coverBlank').hidden = true;
      el('picNote').textContent = '已上传封面 · ' + data.size;
      if (typeof syncRail === 'function') syncRail();
      if (typeof syncBuildEnabled === 'function') syncBuildEnabled();
      status('封面已上传，可以生成 AI 组件。');
    } catch (error) { status('封面上传失败：' + error.message); }
  };

  async function callGenerate(target, useExisting) {
    const data = await api('generate', {
      profileId: profileChoice(), pic: PIC,
      target, instruction: el('aiInstruction').value,
      album: el('album').value, artist: el('artist').value,
      company: el('company').value,
      id: new URLSearchParams(location.search).get('id') || '',
      date: new URLSearchParams(location.search).get('date') || '',
      innerCopy: el('innerCopy').value,
      barcode: el('barcode').value,
      copyright: el('copyright').value,
      trackData: typeof currentTrackData === 'function' ? currentTrackData() : [],
      sourceUid: useExisting ? images[target]?.upload || '' : ''
    });
    images[target] = {...data, message: '已生成 · 可继续按描述重绘'};
    drawCards();
  }

  async function generateOne(target, useExisting) {
    if (running) return;
    if (!PIC) return status('先上传或选择专辑封面。');
    if (!profileChoice()) return status('先点“模型配置”保存图片模型和 API Key。');
    running = true; drawCards();
    status('正在生成' + (targets.find(x => x[0] === target)?.[1] || target) + '…');
    try { await callGenerate(target, useExisting); status('组件已生成，可以继续描述修改。'); }
    catch (error) { status('生成失败：' + error.message); }
    finally { running = false; drawCards(); }
  }

  el('btnAiAll').onclick = async () => {
    if (running) return;
    if (!PIC) return status('先上传或选择专辑封面。');
    if (!profileChoice()) return status('先点“模型配置”保存图片模型和 API Key。');
    running = true; el('btnAiAll').disabled = true; drawCards();
    let done = 0, failed = 0, firstError = '';
    for (const [target, name] of targets) {
      status('正在生成 ' + name + ' · ' + (done + failed + 1) + '/' + targets.length);
      try { await callGenerate(target, false); done++; }
      catch (error) {
        firstError = error.message;
        images[target] = {message: '失败：' + firstError}; failed++; drawCards();
        break;
      }
    }
    running = false; el('btnAiAll').disabled = false; drawCards();
    status(firstError
      ? '已停止，避免继续产生失败请求。' + firstError
      : 'AI 草图完成 ' + done + '/' + targets.length + '。');
  };

  drawCards();
  loadProfiles().catch(error => status('读取模型配置失败：' + error.message));
})();
