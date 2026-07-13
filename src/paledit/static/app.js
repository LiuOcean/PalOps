const worldsNode = document.querySelector('#worlds');
const rootNode = document.querySelector('#root');
const template = document.querySelector('#world-template');
const itemTemplate = document.querySelector('#item-template');
const itemResults = document.querySelector('#item-results');
const itemSummary = document.querySelector('#item-summary');
const itemQuery = document.querySelector('#item-query');
const palResults = document.querySelector('#pal-results');
const palSummary = document.querySelector('#pal-summary');
const palQuery = document.querySelector('#pal-query');
const userPanel = document.querySelector('#user-panel');
const usersNode = document.querySelector('#users');
const userSummary = document.querySelector('#user-summary');
const userTemplate = document.querySelector('#user-template');
const playerDetail = document.querySelector('#player-detail');
const containerPanel = document.querySelector('#container-panel');
const containersNode = document.querySelector('#containers');
const containerSummary = document.querySelector('#container-summary');
const containerQuery = document.querySelector('#container-query');
const containerTemplate = document.querySelector('#container-template');
let activeWorld = null;
let activeWorldHash = null;
let loadedUsers = [];
let selectedUserId = null;
let onlinePlayers = [];
let loadedContainers = [];
let serverConfig = null;
let restartConfirmationToken = null;
const SERVER_CONTEXT_REFRESH_MS = 15_000;
let serverContextRequest = null;

function showView(name) {
  document.querySelectorAll('[data-page]').forEach(page => page.classList.toggle('hidden', page.dataset.page !== name));
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === name));
  if (name === 'config' && !serverConfig) loadServerConfig();
}

function setConfigResult(message, kind = '') {
  const node = document.querySelector('#config-result');
  node.textContent = message;
  node.className = `config-result ${kind}`.trim();
}

function configChanges() {
  if (!serverConfig) return {};
  const updates = {};
  document.querySelectorAll('.config-row [data-config-control]').forEach(control => {
    if (control.value !== control.dataset.original) updates[control.dataset.key] = control.value;
  });
  return updates;
}

function syncConfigChanges() {
  document.querySelectorAll('.config-row').forEach(row => {
    const control = row.querySelector('[data-config-control]');
    const changed = control.value !== control.dataset.original;
    row.classList.toggle('changed', changed);
    row.querySelector('.change-state').textContent = changed ? '已修改' : '未修改';
  });
  const count = Object.keys(configChanges()).length;
  document.querySelector('#save-config').disabled = count === 0;
  if (count) setConfigResult(`${count} 项待保存。保存后需重启服务器才会应用。`);
}

function renderServerConfig() {
  const root = document.querySelector('#config-settings');
  const query = document.querySelector('#config-query').value.trim().toLocaleLowerCase('zh-CN');
  root.innerHTML = '';
  const categories = new Map();
  for (const setting of serverConfig.settings) {
    if (query && !`${setting.label} ${setting.description} ${setting.key} ${setting.value} ${setting.category}`.toLocaleLowerCase('zh-CN').includes(query)) continue;
    if (!categories.has(setting.category)) categories.set(setting.category, []);
    categories.get(setting.category).push(setting);
  }
  for (const [category, settings] of categories) {
    const heading = document.createElement('h3'); heading.className = 'config-group-title'; heading.textContent = category; root.append(heading);
    for (const setting of settings) {
      const row = document.createElement('label'); row.className = 'config-row';
      const key = document.createElement('span'); key.className = 'config-key';
      const label = document.createElement('strong'); label.textContent = setting.label;
      const description = document.createElement('span'); description.textContent = setting.description;
      const code = document.createElement('code'); code.textContent = setting.key;
      key.append(label, description, code);
      let control;
      if (setting.control === 'select' && setting.options?.length) {
        control = document.createElement('select');
        for (const item of setting.options) {
          const option = document.createElement('option'); option.value = item.value; option.textContent = item.label; control.append(option);
        }
        if (!setting.options.some(item => item.value === setting.value)) {
          const option = document.createElement('option'); option.value = setting.value; option.textContent = '当前值暂未识别'; control.prepend(option);
        }
        control.value = setting.value;
        control.addEventListener('change', syncConfigChanges);
      } else {
        control = document.createElement('input'); control.value = setting.value; control.autocomplete = 'off'; control.spellcheck = false;
        control.addEventListener('input', syncConfigChanges);
      }
      control.dataset.configControl = ''; control.dataset.original = setting.value; control.dataset.key = setting.key;
      const state = document.createElement('span'); state.className = 'change-state'; state.textContent = '未修改';
      row.append(key, control, state); root.append(row);
    }
  }
  if (!root.children.length) root.innerHTML = '<div class="empty">没有匹配的配置项</div>';
}

async function loadServerConfig() {
  const root = document.querySelector('#config-settings');
  root.innerHTML = '<div class="empty">正在从 palworld-server 读取持久化配置…</div>';
  document.querySelector('#save-config').disabled = true;
  document.querySelector('#export-config').disabled = true;
  try {
    const response = await fetch('/api/server/config');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '配置读取失败');
    serverConfig = data;
    document.querySelector('#config-source').textContent = `${data.host} · ${data.path} · ${data.settings.length} 个可编辑项`;
    document.querySelector('#export-config').disabled = false;
    renderServerConfig();
    setConfigResult(data.note);
  } catch (error) {
    serverConfig = null;
    root.innerHTML = `<div class="empty"></div>`;
    root.querySelector('.empty').textContent = error.message;
    setConfigResult(error.message, 'error');
  }
}

async function saveServerConfig() {
  const button = document.querySelector('#save-config');
  const updates = configChanges();
  button.disabled = true; button.textContent = '正在备份并保存…';
  try {
    const response = await fetch('/api/server/config', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({updates, expected_revision:serverConfig.revision})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '配置保存失败');
    setConfigResult(`已保存 ${data.changed.length} 项 · 远端备份：${data.backup_path} · 请重启以应用`, 'ok');
    appendOperationLog(`服务器配置已保存（${data.changed.length} 项）`);
    await loadServerConfig();
    setConfigResult(`已保存 ${data.changed.length} 项 · 远端备份：${data.backup_path} · 请重启以应用`, 'ok');
  } catch (error) {
    setConfigResult(error.message, 'error');
    button.disabled = false;
  } finally { button.textContent = '备份并保存到服务器'; }
}

function exportServerConfig() {
  if (!serverConfig) return;
  const payload = {host:serverConfig.host, source:serverConfig.path, exported_at:new Date().toISOString(), settings:Object.fromEntries(serverConfig.settings.map(row => [row.key, row.value]))};
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type:'application/json'});
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `palworld-config-${new Date().toISOString().slice(0,10)}.json`; link.click(); URL.revokeObjectURL(link.href);
}

function showOperationTab(name) {
  document.querySelectorAll('[data-operation-pane]').forEach(pane => pane.classList.toggle('hidden', pane.dataset.operationPane !== name));
  document.querySelectorAll('[data-operation-tab]').forEach(button => button.classList.toggle('active', button.dataset.operationTab === name));
}

function setOperationResult(message, kind = '') {
  const node = document.querySelector('#operation-result');
  node.textContent = message;
  node.className = `operation-result ${kind}`.trim();
}

function appendOperationLog(label) {
  const log = document.querySelector('#operation-log');
  if (log.querySelector('p')?.textContent === '本次会话尚无写操作') log.innerHTML = '';
  const row = document.createElement('p');
  row.textContent = `${new Date().toLocaleTimeString('zh-CN', {hour12:false})} · ${label}`;
  log.prepend(row);
}

async function copyPlayerText(text, button, label) {
  const result = document.querySelector('#player-copy-result');
  const original = button.innerHTML;
  try {
    await navigator.clipboard.writeText(text);
    button.innerHTML = '<i class="ph ph-check" aria-hidden="true"></i> 已复制';
    result.textContent = `已复制${label}：${text}`;
    result.className = 'copy-result ok';
  } catch (error) {
    result.textContent = `复制失败，请手动复制：${text}`;
    result.className = 'copy-result error';
  } finally {
    window.setTimeout(() => { button.innerHTML = original; }, 1400);
  }
}

function playerCopyButton(text, label, className = 'copy-button') {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = className;
  button.innerHTML = `<i class="ph ph-copy" aria-hidden="true"></i> ${label}`;
  button.title = `复制 ${text}`;
  button.addEventListener('click', () => copyPlayerText(text, button, label));
  return button;
}

function loadServerContext({showLoading = true} = {}) {
  if (serverContextRequest) return serverContextRequest;
  serverContextRequest = (async () => {
    const state = document.querySelector('#server-state');
    const rcon = document.querySelector('#rcon-state');
    if (showLoading) {
      state.className = 'status-pill loading'; state.textContent = '读取中';
      rcon.className = 'connection-state loading'; rcon.textContent = '检查中';
    }
    try {
      const [statusResponse, playersResponse] = await Promise.all([fetch('/api/server/status'), fetch('/api/server/players')]);
      const status = await statusResponse.json();
      const playerData = await playersResponse.json();
      if (!statusResponse.ok) throw new Error(status.detail || '服务器状态读取失败');
      if (!playersResponse.ok) throw new Error(playerData.detail || 'RCON 玩家列表读取失败');
      state.className = `status-pill ${status.online ? '' : 'offline'}`.trim();
      state.textContent = status.online ? '在线' : '离线';
      document.querySelector('#server-health').textContent = status.health;
      document.querySelector('#restart-policy').textContent = status.restart_policy;
      rcon.className = 'connection-state'; rcon.textContent = 'RCON 已连接';
      onlinePlayers = playerData.players;
      renderOnlinePlayers();
    } catch (error) {
      state.className = 'status-pill offline'; state.textContent = '不可用';
      rcon.className = 'connection-state offline'; rcon.textContent = 'RCON 未连接';
      document.querySelector('#online-players').textContent = error.message;
      document.querySelector('#players-page-list').textContent = error.message;
    } finally {
      serverContextRequest = null;
    }
  })();
  return serverContextRequest;
}

function refreshServerContextInBackground() {
  if (!document.hidden) void loadServerContext({showLoading: false});
}

function renderOnlinePlayers() {
  document.querySelector('#online-count').textContent = `${onlinePlayers.length} 人在线`;
  const compact = document.querySelector('#online-players');
  const page = document.querySelector('#players-page-list');
  const select = document.querySelector('#player-select');
  compact.innerHTML = ''; page.innerHTML = ''; select.innerHTML = '';
  if (!onlinePlayers.length) {
    compact.innerHTML = '<p>当前没有在线玩家</p>';
    page.textContent = '当前没有在线玩家';
    const option = document.createElement('option'); option.value = ''; option.textContent = '当前没有在线玩家'; select.append(option);
    return;
  }
  const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = '请选择在线玩家'; select.append(placeholder);
  for (const player of onlinePlayers) {
    const compactRow = document.createElement('div'); compactRow.className = 'online-player';
    const compactIdentity = document.createElement('span'); compactIdentity.className = 'online-player-identity';
    const compactName = document.createElement('strong'); compactName.textContent = player.name;
    const compactMeta = document.createElement('small'); compactMeta.textContent = player.level ? `Lv.${player.level} · ${player.command_id}` : player.command_id;
    compactIdentity.append(compactName, compactMeta);
    compactRow.append(compactIdentity, playerCopyButton(player.command_id, '复制 ID', 'icon-copy-button')); compact.append(compactRow);

    const pageRow = document.createElement('div'); pageRow.className = 'standalone-player';
    const pageHead = document.createElement('div'); pageHead.className = 'player-card-head';
    const pageName = document.createElement('strong'); pageName.textContent = player.name;
    const pageMeta = document.createElement('span'); pageMeta.textContent = player.level ? `Lv.${player.level} · 在线` : '在线';
    pageHead.append(pageName, pageMeta);

    const details = document.createElement('dl'); details.className = 'player-identifiers';
    for (const [label, value] of [['Player ID', player.player_uid], ['User ID', player.steam_id]]) {
      const row = document.createElement('div');
      const term = document.createElement('dt'); term.textContent = label;
      const data = document.createElement('dd');
      const code = document.createElement('code'); code.textContent = value || '—';
      data.append(code);
      if (value) data.append(playerCopyButton(value, `复制 ${label}`));
      row.append(term, data); details.append(row);
    }

    const commands = document.createElement('div'); commands.className = 'player-command-actions';
    commands.append(
      playerCopyButton(`/TeleportToMe ${player.command_id}`, 'TeleportToMe', 'secondary command-copy-button'),
      playerCopyButton(`/TeleportToPlayer ${player.command_id}`, 'TeleportToPlayer', 'secondary command-copy-button'),
    );
    pageRow.append(pageHead, details, commands); page.append(pageRow);
    const option = document.createElement('option'); option.value = player.command_id; option.textContent = player.level ? `${player.name} · Lv.${player.level}` : player.name; select.append(option);
  }
}

async function submitServerAction(payload, button, successLabel) {
  button.disabled = true;
  setOperationResult('正在安全地提交操作…');
  try {
    const response = await fetch('/api/server/actions', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...payload, confirmed:true})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '操作失败');
    setOperationResult(`${successLabel} · ${data.results.map(row => row.response || row.command).join(' · ')}`, 'ok');
    appendOperationLog(successLabel);
  } catch (error) {
    setOperationResult(error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

async function scan() {
  worldsNode.innerHTML = '<div class="empty">正在读取存档头…</div>';
  try {
    const response = await fetch('/api/worlds');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '扫描失败');
    rootNode.textContent = data.root;
    worldsNode.innerHTML = '';
    for (const world of data.worlds) worldsNode.append(renderWorld(world));
    if (!data.worlds.length) worldsNode.innerHTML = '<div class="empty">没有发现 Level.sav</div>';
  } catch (error) {
    worldsNode.innerHTML = `<div class="empty">${error.message}</div>`;
  }
}

function renderWorld(world) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector('h3').textContent = world.world_id;
  node.querySelector('.meta').textContent = world.path;
  node.querySelector('.format').textContent = `${world.level.magic} · ${world.level.format}`;
  node.querySelector('.players').textContent = `${world.player_files} 个玩家档`;
  node.querySelector('.backups').textContent = `${world.backup_sets} 组备份`;
  const button = node.querySelector('.inspect');
  const result = node.querySelector('.result');
  button.addEventListener('click', async () => {
    button.disabled = true;
    result.className = 'result'; result.textContent = '正在解压并遍历 1.0 数据…';
    try {
      const response = await fetch(`/api/world/inspect?path=${encodeURIComponent(world.path)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '诊断失败');
      result.className = 'result ok';
      result.textContent = `兼容 · ${data.character_count} 个角色实体 · 可编辑用户与道具`;
      activeWorld = world.path;
      await Promise.all([loadUsers(), loadContainers()]);
    } catch (error) {
      result.className = 'result error'; result.textContent = error.message;
    } finally { button.disabled = false; }
  });
  return node;
}

async function loadContainers() {
  if (!activeWorld) return;
  containerPanel.classList.remove('hidden');
  containersNode.innerHTML = '<div class="empty">正在关联地图对象与物品容器…</div>';
  const response = await fetch(`/api/world/containers?path=${encodeURIComponent(activeWorld)}`);
  const data = await response.json();
  if (!response.ok) { containersNode.innerHTML = `<div class="empty">${data.detail}</div>`; return; }
  loadedContainers = data.containers;
  containerSummary.textContent = `${data.count} 个物品容器 · ${data.labeled_count} 个带标签 · 只读展示`;
  renderContainers();
}

function renderContainers() {
  const query = containerQuery.value.trim().toLocaleLowerCase('zh-CN');
  const rows = loadedContainers.filter(container => {
    const items = container.slots.map(slot => `${slot.name_zh} ${slot.item_id}`).join(' ');
    return !query || `${container.label} ${container.object_id} ${container.container_id} ${items}`.toLocaleLowerCase('zh-CN').includes(query);
  });
  containersNode.innerHTML = '';
  for (const container of rows) {
    const card = containerTemplate.content.firstElementChild.cloneNode(true);
    card.querySelector('.container-label').textContent = container.label || '未命名容器';
    card.querySelector('.container-type').textContent = `${container.type_name} · ${container.object_id}`;
    card.querySelector('.container-id').textContent = container.container_id;
    card.querySelector('.container-usage').textContent = `${container.occupied_slots}/${container.slot_capacity || '—'} 槽 · ${container.total_items.toLocaleString()} 件`;
    const items = card.querySelector('.container-items');
    const occupied = container.slots.filter(slot => slot.item_id !== 'None' && slot.count > 0);
    if (!occupied.length) items.innerHTML = '<p class="container-empty">空箱</p>';
    for (const slot of occupied) {
      const row = document.createElement('div'); row.className = 'container-item';
      const image = document.createElement('img'); image.className = 'mini-item-icon'; image.alt = ''; image.loading = 'lazy';
      if (slot.icon_url) image.src = slot.icon_url; else image.classList.add('hidden');
      const copy = document.createElement('span'); copy.innerHTML = '<strong></strong><small></small>';
      copy.querySelector('strong').textContent = slot.name_zh;
      copy.querySelector('small').textContent = `${slot.category} · ${slot.item_id}`;
      const count = document.createElement('b'); count.textContent = `× ${slot.count.toLocaleString()}`;
      row.append(image, copy, count); items.append(row);
    }
    containersNode.append(card);
  }
  if (!rows.length) containersNode.innerHTML = '<div class="empty">没有匹配的箱子或容器</div>';
}

async function loadUsers() {
  if (!activeWorld) return;
  userPanel.classList.remove('hidden');
  usersNode.innerHTML = '<div class="empty">正在关联用户、玩家文件与帕鲁…</div>';
  const response = await fetch(`/api/world/users?path=${encodeURIComponent(activeWorld)}`);
  const data = await response.json();
  if (!response.ok) { usersNode.innerHTML = `<div class="empty">${data.detail}</div>`; return; }
  activeWorldHash = data.level_sha256;
  userSummary.textContent = `${data.users.length} 个用户 · 所有字段以 Palworld 原始类型读写`;
  loadedUsers = data.users;
  usersNode.innerHTML = '';
  for (const user of data.users) {
    const button = document.createElement('button');
    const name = document.createElement('span'); name.textContent = user.nickname || '未命名用户';
    const meta = document.createElement('small'); meta.textContent = `Lv.${user.level} · ${user.pal_count} 只帕鲁`;
    button.append(name, meta);
    button.classList.toggle('active', user.player_uid === selectedUserId);
    button.addEventListener('click', () => selectUser(user.player_uid));
    usersNode.append(button);
  }
  if (!selectedUserId || !data.users.some(user => user.player_uid === selectedUserId)) selectedUserId = data.users[0]?.player_uid;
  selectUser(selectedUserId);
}

function selectUser(playerUid) {
  selectedUserId = playerUid;
  [...usersNode.children].forEach((node, index) => node.classList.toggle('active', loadedUsers[index]?.player_uid === playerUid));
  const user = loadedUsers.find(row => row.player_uid === playerUid);
  playerDetail.innerHTML = '';
  if (user) playerDetail.append(renderUser(user));
}

function renderUser(user) {
  const card = userTemplate.content.firstElementChild.cloneNode(true);
  card.querySelector('.user-name').textContent = user.nickname || '未命名用户';
  card.querySelector('.user-id').textContent = user.player_uid;
  card.querySelector('.pal-count').textContent = `${user.pal_count} 只帕鲁`;
  const form = card.querySelector('form');
  for (const field of ['nickname','level','experience','unused_status_points','satiety','technology_points']) form.elements[field].value = user[field] ?? 0;
  card.querySelector('.readonly-data').textContent = `生命值 ${user.hp} · 护盾 ${user.shield_hp} · 声音 ${user.voice_id} · 实例 ${user.instance_id}`;
  const palBox = card.querySelector('.pal-list div');
  for (const pal of user.pals) {
    const row = document.createElement('div'); row.className = 'pal-chip';
    const label = document.createElement('span');
    label.textContent = `${pal.name_zh}${pal.nickname ? ` · ${pal.nickname}` : ''} · Lv.${pal.level}`;
    const id = document.createElement('code'); id.textContent = pal.character_id;
    row.append(label, id);
    palBox.append(row);
  }
  const inventoryBox = card.querySelector('.inventory-list');
  for (const [category, slots] of Object.entries(user.inventories || {})) {
    const group = document.createElement('div'); group.className = 'inventory-group';
    const title = document.createElement('h4'); title.textContent = `${category} · ${slots.length} 个槽位`; group.append(title);
    for (const slot of slots) group.append(renderInventorySlot(user, category, slot));
    inventoryBox.append(group);
  }
  card.querySelectorAll('.detail-tabs button').forEach(button => button.addEventListener('click', () => {
    card.querySelectorAll('.detail-tabs button').forEach(node => node.classList.toggle('active', node === button));
    card.querySelectorAll('.tab-pane').forEach(pane => pane.classList.toggle('hidden', pane.dataset.pane !== button.dataset.tab));
  }));
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('.save-user'); const status = form.querySelector('.save-result');
    button.disabled = true; status.textContent = '正在备份、写入并重新解析…';
    const body = {expected_sha256: activeWorldHash, expected_player_sha256:user.player_file_sha256};
    for (const field of ['nickname','level','experience','unused_status_points','satiety','technology_points']) body[field] = form.elements[field].type === 'number' ? Number(form.elements[field].value) : form.elements[field].value;
    try {
      const response = await fetch(`/api/world/users/${user.player_uid}?path=${encodeURIComponent(activeWorld)}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const data = await response.json(); if (!response.ok) throw new Error(data.detail);
      activeWorldHash = data.level_sha256; status.textContent = `已保存，备份：${data.backup_path}`;
      await loadUsers();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  return card;
}

function renderInventorySlot(user, category, slot) {
  const row = document.createElement('div'); row.className = 'inventory-row';
  const number = document.createElement('span'); number.className = 'slot-number'; number.textContent = `#${slot.slot_index}`;
  const itemField = document.createElement('label'); itemField.className = 'item-field';
  const itemName = document.createElement('span'); itemName.className = 'inventory-item-name';
  const image = document.createElement('img'); image.className = 'mini-item-icon'; image.alt = ''; if (slot.icon_url) image.src = slot.icon_url; else image.classList.add('hidden');
  const nameCopy = document.createElement('span'); nameCopy.textContent = slot.name_zh; nameCopy.title = slot.description;
  itemName.append(image, nameCopy);
  const item = document.createElement('input'); item.value = slot.item_id; item.title = '使用 Palworld 内部道具 ID';
  itemField.append(itemName, item);
  const count = document.createElement('input'); count.type = 'number'; count.min = '0'; count.max = '999999'; count.value = slot.count;
  const save = document.createElement('button'); save.textContent = '保存';
  save.addEventListener('click', async () => {
    save.disabled = true; save.textContent = '写入中';
    try {
      const body = {category,slot_index:slot.slot_index,item_id:item.value,count:Number(count.value),expected_sha256:activeWorldHash};
      const response = await fetch(`/api/world/users/${user.player_uid}/inventory?path=${encodeURIComponent(activeWorld)}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const data = await response.json(); if (!response.ok) throw new Error(data.detail);
      activeWorldHash = data.level_sha256; await loadUsers();
    } catch (error) { alert(error.message); }
    finally { save.disabled = false; save.textContent = '保存'; }
  });
  row.append(number,itemField,count,save); return row;
}

document.querySelector('#refresh').addEventListener('click', scan);
document.querySelector('#pull-save').addEventListener('click', async event => {
  const button = event.currentTarget;
  const result = document.querySelector('#pull-result');
  button.disabled = true;
  button.textContent = '正在从 palworld-server 拉取…';
  result.className = 'sync-result';
  result.textContent = '正在下载并校验最新存档，当前本地数据会先保留。';
  try {
    const response = await fetch('/api/save/pull', {method: 'POST'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '更新失败');
    result.className = 'sync-result ok';
    result.textContent = `更新完成 · ${data.world_count} 个世界${data.backup_path ? ` · 原数据备份：${data.backup_path}` : ''}`;
    activeWorld = null;
    activeWorldHash = null;
    userPanel.classList.add('hidden');
    await scan();
  } catch (error) {
    result.className = 'sync-result error';
    result.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = '从 palworld-server 更新数据';
  }
});
document.querySelector('#reload-users').addEventListener('click', loadUsers);
let searchTimer;
async function loadItems(query = '') {
  const response = await fetch(`/api/items?q=${encodeURIComponent(query)}&limit=100`);
  const data = await response.json();
  itemSummary.textContent = `${data.total_items.toLocaleString()} 个内部 ID · ${data.localized_items.toLocaleString()} 个中文名称 · PalDB 1.0 数据`;
  itemResults.innerHTML = '';
  for (const item of data.results) {
    const row = itemTemplate.content.firstElementChild.cloneNode(true);
    const image = row.querySelector('.item-icon');
    if (item.icon_url) image.src = item.icon_url; else row.querySelector('.item-icon-wrap').classList.add('missing');
    row.querySelector('.item-name').textContent = item.name_zh;
    row.querySelector('.item-description').textContent = item.description;
    row.querySelector('.item-id').textContent = item.id;
    row.querySelector('.item-category').textContent = item.category;
    const status = row.querySelector('.localization');
    status.textContent = item.localized ? '中文' : '待本地化';
    if (!item.localized) status.classList.add('pending');
    row.addEventListener('click', () => navigator.clipboard.writeText(item.id));
    itemResults.append(row);
  }
  if (!data.results.length) itemResults.innerHTML = '<div class="empty">没有匹配的道具 ID</div>';
}
itemQuery.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadItems(itemQuery.value), 180);
});
let palSearchTimer;
async function loadPals(query = '') {
  const response = await fetch(`/api/pals?q=${encodeURIComponent(query)}&limit=100`);
  const data = await response.json();
  palSummary.textContent = `${data.total_pals.toLocaleString()} 个 CharacterID · ${data.localized_pals.toLocaleString()} 个中文名称 · PalDB 1.0 数据`;
  palResults.innerHTML = '';
  for (const pal of data.results) {
    const row = itemTemplate.content.firstElementChild.cloneNode(true);
    row.querySelector('.item-icon-wrap').classList.add('missing');
    row.querySelector('.item-name').textContent = pal.name_zh;
    row.querySelector('.item-description').textContent = 'Palworld 角色数据标识。';
    row.querySelector('.item-id').textContent = pal.character_id;
    row.querySelector('.item-category').textContent = '帕鲁';
    const status = row.querySelector('.localization');
    status.textContent = pal.localized ? '中文' : '待本地化';
    if (!pal.localized) status.classList.add('pending');
    row.addEventListener('click', () => navigator.clipboard.writeText(pal.character_id));
    palResults.append(row);
  }
  if (!data.results.length) palResults.innerHTML = '<div class="empty">没有匹配的 CharacterID</div>';
}
palQuery.addEventListener('input', () => {
  clearTimeout(palSearchTimer);
  palSearchTimer = setTimeout(() => loadPals(palQuery.value), 180);
});
containerQuery.addEventListener('input', renderContainers);
document.querySelector('#reload-containers').addEventListener('click', loadContainers);

document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
document.querySelectorAll('[data-jump]').forEach(button => button.addEventListener('click', () => {
  showView(button.dataset.jump);
  if (button.dataset.jump === 'operations' && button.closest('[data-page="players"]')) showOperationTab('player');
}));
document.querySelectorAll('[data-operation-tab]').forEach(button => button.addEventListener('click', () => showOperationTab(button.dataset.operationTab)));

document.querySelector('#reload-config').addEventListener('click', loadServerConfig);
document.querySelector('#config-query').addEventListener('input', () => { if (serverConfig) renderServerConfig(); });
document.querySelector('#save-config').addEventListener('click', saveServerConfig);
document.querySelector('#export-config').addEventListener('click', exportServerConfig);

const configRestartConfirm = document.querySelector('#config-restart-confirm');
const configRestartButton = document.querySelector('#config-restart');
const restartDialog = document.querySelector('#restart-dialog');
configRestartConfirm.addEventListener('change', () => { configRestartButton.disabled = !configRestartConfirm.checked; });
configRestartButton.addEventListener('click', async () => {
  configRestartButton.disabled = true;
  setConfigResult('正在创建一次性重启确认…');
  try {
    const response = await fetch('/api/server/restart/prepare', {method:'POST'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '无法发起重启确认');
    restartConfirmationToken = data.confirmation_token;
    restartDialog.showModal();
    setConfigResult(`请在弹窗中完成第二次确认（${data.expires_in} 秒内有效）。`);
  } catch (error) {
    restartConfirmationToken = null;
    setConfigResult(error.message, 'error');
    configRestartButton.disabled = false;
  }
});
restartDialog.addEventListener('close', async () => {
  if (restartDialog.returnValue !== 'confirm') {
    restartConfirmationToken = null;
    configRestartButton.disabled = !configRestartConfirm.checked;
    setConfigResult('已取消重启，服务器未受影响。');
    return;
  }
  const token = restartConfirmationToken; restartConfirmationToken = null;
  configRestartButton.disabled = true;
  setConfigResult('正在保存世界、重启容器并等待健康检查…');
  try {
    const response = await fetch('/api/server/restart', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmation_token:token, confirmed:true})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '服务器重启失败');
    setConfigResult(`重启完成 · ${data.status}`, 'ok');
    appendOperationLog('配置应用并重启完成');
    await loadServerContext();
  } catch (error) { setConfigResult(error.message, 'error'); }
  finally {
    configRestartConfirm.checked = false;
    configRestartButton.disabled = true;
  }
});
const restartConfirm = document.querySelector('#restart-confirm');
const restartButton = document.querySelector('#safe-restart');
restartConfirm.addEventListener('change', () => { restartButton.disabled = !restartConfirm.checked; });
restartButton.addEventListener('click', async () => {
  await submitServerAction({
    action:'safe_restart',
    message:document.querySelector('#restart-message').value,
    seconds:Number(document.querySelector('#restart-seconds').value),
  }, restartButton, '安全重启已排定');
  restartConfirm.checked = false; restartButton.disabled = true;
});

const playerConfirm = document.querySelector('#player-confirm');
const playerButton = document.querySelector('#run-player-action');
function syncPlayerButton() { playerButton.disabled = !playerConfirm.checked || !document.querySelector('#player-select').value; }
playerConfirm.addEventListener('change', syncPlayerButton);
document.querySelector('#player-select').addEventListener('change', syncPlayerButton);
playerButton.addEventListener('click', async () => {
  const action = document.querySelector('#player-action').value;
  await submitServerAction({action, player_uid:document.querySelector('#player-select').value}, playerButton, action === 'kick' ? '玩家已踢出' : '玩家已封禁');
  playerConfirm.checked = false; syncPlayerButton();
});

const advancedAction = document.querySelector('#advanced-action');
const advancedConfirm = document.querySelector('#advanced-confirm');
const advancedButton = document.querySelector('#run-advanced-action');
function syncAdvancedForm() {
  const action = advancedAction.value;
  document.querySelector('#advanced-message-wrap').classList.toggle('hidden', action === 'save');
  document.querySelector('#advanced-seconds-wrap').classList.toggle('hidden', action !== 'shutdown');
  advancedButton.classList.toggle('danger', action === 'shutdown');
  advancedButton.classList.toggle('primary', action !== 'shutdown');
  advancedButton.disabled = !advancedConfirm.checked;
}
advancedAction.addEventListener('change', syncAdvancedForm);
advancedConfirm.addEventListener('change', syncAdvancedForm);
advancedButton.addEventListener('click', async () => {
  const action = advancedAction.value;
  const payload = {action};
  if (action !== 'save') payload.message = document.querySelector('#advanced-message').value;
  if (action === 'shutdown') payload.seconds = Number(document.querySelector('#advanced-seconds').value);
  await submitServerAction(payload, advancedButton, action === 'save' ? '世界已保存' : action === 'broadcast' ? '广播已发送' : '关服已排定');
  advancedConfirm.checked = false; syncAdvancedForm();
});

document.querySelectorAll('[data-quick-action]').forEach(button => button.addEventListener('click', () => {
  showOperationTab(button.dataset.quickTab);
  if (button.dataset.quickTab === 'advanced') { advancedAction.value = button.dataset.quickAction; syncAdvancedForm(); }
  if (button.dataset.quickTab === 'player') document.querySelector('#player-action').value = button.dataset.quickAction;
  document.querySelector('.operation-workspace').scrollIntoView({behavior:'smooth', block:'start'});
}));

syncAdvancedForm();
scan();
loadItems();
loadPals();
loadServerContext();
window.setInterval(refreshServerContextInBackground, SERVER_CONTEXT_REFRESH_MS);
document.addEventListener('visibilitychange', refreshServerContextInBackground);
