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
const skillResults = document.querySelector('#skill-results');
const skillSummary = document.querySelector('#skill-summary');
const skillQuery = document.querySelector('#skill-query');
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
const guildPanel = document.querySelector('#guild-panel');
const guildsNode = document.querySelector('#guilds');
const guildSummary = document.querySelector('#guild-summary');
const guildQuery = document.querySelector('#guild-query');
const guildDetail = document.querySelector('#guild-detail');
let activeWorld = null;
let activeWorldHash = null;
let loadedUsers = [];
let selectedUserId = null;
let onlinePlayers = [];
let loadedContainers = [];
let selectedContainerId = null;
let loadedGuilds = [];
let selectedGuildId = null;
let discoveredWorlds = [];
let mapData = null;
let selectedMapPlayerId = null;
let selectedMapBaseId = null;
let mapRequest = null;
const mapView = {zoom: 1, panX: 0, panY: 0, drag: null};
let serverConfig = null;
let backupData = null;
let pendingBackupRestore = null;
let restartConfirmationToken = null;
const SERVER_CONTEXT_REFRESH_MS = 15_000;
const OWNER_PLAYER_UID = '00000000-0000-0000-0000-000000000000';
let serverContextRequest = null;

function playersFromResponse(payload) {
  return Array.isArray(payload?.players) ? payload.players : [];
}

function showView(name) {
  document.querySelectorAll('[data-page]').forEach(page => page.classList.toggle('hidden', page.dataset.page !== name));
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === name));
  if (name === 'config' && !serverConfig) loadServerConfig();
  if (name === 'backups' && !backupData) loadBackups();
  if (name === 'map') loadWorldMap();
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value >= 10 || unit === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unit]}`;
}

function backupSearchText(backup) {
  return [backup.name, backup.source_label, backup.path, ...(backup.world_ids || [])].join(' ').toLocaleLowerCase('zh-CN');
}

function setBackupResult(message, kind = '') {
  const node = document.querySelector('#backup-result');
  node.textContent = message;
  node.className = `sync-result ${kind}`.trim();
}

function renderBackups() {
  const root = document.querySelector('#backup-list');
  const query = document.querySelector('#backup-query').value.trim().toLocaleLowerCase('zh-CN');
  const source = document.querySelector('#backup-source').value;
  const rows = (backupData?.backups || []).filter(backup => (!source || backup.source === source) && (!query || backupSearchText(backup).includes(query)));
  root.innerHTML = '';
  for (const backup of rows) {
    const article = document.createElement('article'); article.className = 'backup-row';
    const icon = document.createElement('span'); icon.className = `backup-icon ${backup.source}`; icon.innerHTML = '<i class="ph ph-archive-box" aria-hidden="true"></i>';
    const copy = document.createElement('span'); copy.className = 'backup-copy';
    const title = document.createElement('strong'); title.textContent = backup.name;
    const meta = document.createElement('small');
    const worlds = backup.world_ids?.length ? backup.world_ids.join(', ') : '未识别世界';
    meta.textContent = `${new Date(backup.created_at).toLocaleString('zh-CN', {hour12:false})} · ${worlds}`;
    copy.append(title, meta);
    const sourceBadge = document.createElement('span'); sourceBadge.className = `backup-source ${backup.source}`; sourceBadge.textContent = backup.source_label;
    const stats = document.createElement('span'); stats.className = 'backup-row-stats';
    const size = document.createElement('strong'); size.textContent = formatBytes(backup.size_bytes);
    const files = document.createElement('small'); files.textContent = `${backup.file_count.toLocaleString()} 个文件${backup.has_level_save ? ' · 含 Level.sav' : ''}`;
    stats.append(size, files);
    const technical = document.createElement('details'); technical.className = 'backup-path';
    const summary = document.createElement('summary'); summary.textContent = '查看路径';
    const code = document.createElement('code'); code.textContent = backup.path;
    technical.append(summary, code);
    const actions = document.createElement('span'); actions.className = 'backup-actions';
    let worldSelect = null;
    if ((backup.world_ids || []).length > 1) {
      worldSelect = document.createElement('select'); worldSelect.setAttribute('aria-label', `${backup.name} 恢复世界`);
      for (const worldId of backup.world_ids) {
        const option = document.createElement('option'); option.value = worldId; option.textContent = worldId; worldSelect.append(option);
      }
      actions.append(worldSelect);
    }
    const restore = document.createElement('button'); restore.className = 'backup-restore secondary';
    restore.innerHTML = '<i class="ph ph-clock-counter-clockwise" aria-hidden="true"></i> 恢复';
    restore.disabled = !backup.has_level_save || !(backup.world_ids || []).length;
    restore.title = restore.disabled ? '该备份中没有可恢复的世界' : '检查后恢复到本地 Save';
    restore.addEventListener('click', () => beginBackupRestore(backup, worldSelect?.value || backup.world_ids[0], restore));
    actions.append(restore, technical);
    article.append(icon, copy, sourceBadge, stats, actions); root.append(article);
  }
  document.querySelector('#backup-summary').textContent = `显示 ${rows.length} / ${backupData?.count || 0} 份备份 · 固定目录只读扫描`;
  if (!rows.length) root.innerHTML = '<div class="empty">没有匹配的本地备份</div>';
}

async function loadBackups() {
  const root = document.querySelector('#backup-list');
  const button = document.querySelector('#reload-backups');
  root.innerHTML = '<div class="empty">正在统计备份文件与占用空间…</div>';
  button.disabled = true;
  try {
    const response = await fetch('/api/backups');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '备份索引读取失败');
    backupData = data;
    document.querySelector('#backup-total').textContent = data.count.toLocaleString();
    document.querySelector('#backup-size').textContent = formatBytes(data.total_size_bytes);
    renderBackups();
  } catch (error) {
    root.innerHTML = '<div class="empty"></div>';
    root.querySelector('.empty').textContent = error.message;
    document.querySelector('#backup-summary').textContent = '备份索引暂不可用';
  } finally { button.disabled = false; }
}

async function beginBackupRestore(backup, worldId, button) {
  button.disabled = true;
  setBackupResult(`正在检查 ${backup.name}…`);
  try {
    const response = await fetch('/api/backups/restore/prepare', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({backup_id:backup.backup_id, world_id:worldId})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '备份恢复检查失败');
    pendingBackupRestore = data;
    document.querySelector('#restore-world-id').textContent = data.world_id;
    document.querySelector('#restore-backup-name').textContent = `${data.backup_name} · ${data.source_label}`;
    document.querySelector('#restore-current-hash').textContent = data.current_sha256;
    document.querySelector('#restore-backup-hash').textContent = data.backup_sha256;
    const checkbox = document.querySelector('#backup-restore-confirm'); checkbox.checked = false;
    document.querySelector('#confirm-backup-restore').disabled = true;
    document.querySelector('#backup-restore-dialog').showModal();
    setBackupResult('备份检查通过，请在弹窗中完成第二次确认。');
  } catch (error) {
    pendingBackupRestore = null;
    setBackupResult(error.message, 'error');
  } finally { button.disabled = false; }
}

function showResourceTab(name) {
  document.querySelectorAll('[data-resource-tab]').forEach(button => {
    const active = button.dataset.resourceTab === name;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
  document.querySelectorAll('[data-resource-pane]').forEach(pane => pane.classList.toggle('hidden', pane.dataset.resourcePane !== name));
  const resources = {containers: loadedContainers, users: loadedUsers, guilds: loadedGuilds};
  const hasData = resources[name]?.length || 0;
  document.querySelector('#resource-empty').classList.toggle('hidden', Boolean(hasData));
  document.querySelector('#container-detail').classList.toggle('hidden', name !== 'containers');
  document.querySelector('#player-detail').classList.toggle('hidden', name !== 'users');
  document.querySelector('#guild-detail').classList.toggle('hidden', name !== 'guilds');
  if (name === 'containers' && hasData) selectContainer(selectedContainerId || loadedContainers[0].container_id);
  if (name === 'users' && hasData) selectUser(selectedUserId || loadedUsers[0].player_uid);
  if (name === 'guilds' && hasData) selectGuild(selectedGuildId || loadedGuilds[0].guild_id);
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
  const result = button.closest('[data-page="map"]') ? document.querySelector('#map-result') : document.querySelector('#player-copy-result');
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

function formatUptime(seconds) {
  if (!Number.isFinite(seconds)) return '—';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days} 天 ${hours} 小时`;
  if (hours) return `${hours} 小时 ${minutes} 分`;
  return `${minutes} 分钟`;
}

function renderServerMetrics(metrics, error = '') {
  const value = (id, text) => { document.querySelector(id).textContent = text; };
  if (!metrics) {
    for (const id of ['#metric-fps', '#metric-frame-time', '#metric-players', '#metric-uptime', '#metric-bases', '#metric-days']) value(id, '—');
    value('#metrics-updated', error || 'REST 指标暂不可用');
    return;
  }
  value('#metric-fps', Number.isFinite(metrics.server_fps) ? metrics.server_fps.toFixed(0) : '—');
  value('#metric-frame-time', Number.isFinite(metrics.frame_time_ms) ? `${metrics.frame_time_ms.toFixed(2)} ms` : '—');
  const current = Number.isFinite(metrics.current_players) ? metrics.current_players : onlinePlayers.length;
  value('#metric-players', Number.isFinite(metrics.max_players) ? `${current} / ${metrics.max_players}` : String(current));
  value('#metric-uptime', formatUptime(metrics.uptime_seconds));
  value('#metric-bases', Number.isFinite(metrics.base_camps) ? String(metrics.base_camps) : '—');
  value('#metric-days', Number.isFinite(metrics.world_days) ? `第 ${metrics.world_days} 天` : '—');
  value('#metrics-updated', `官方 REST · ${new Date().toLocaleTimeString('zh-CN', {hour12:false})}`);
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
      const [statusResponse, playersResponse, metricsResponse] = await Promise.all([
        fetch('/api/server/status'), fetch('/api/server/players'), fetch('/api/server/metrics'),
      ]);
      const status = await statusResponse.json();
      const playerData = await playersResponse.json();
      const metricsData = await metricsResponse.json();
      if (!statusResponse.ok) throw new Error(status.detail || '服务器状态读取失败');
      if (!playersResponse.ok) throw new Error(playerData.detail || 'RCON 玩家列表读取失败');
      state.className = `status-pill ${status.online ? '' : 'offline'}`.trim();
      state.textContent = status.online ? '在线' : '离线';
      document.querySelector('#server-health').textContent = status.health;
      document.querySelector('#restart-policy').textContent = status.restart_policy;
      document.querySelector('#overview-state-title').textContent = status.online ? '服务器连接正常' : '服务器当前离线';
      document.querySelector('#overview-state-copy').textContent = status.online ? '容器、玩家接口与管理链路均可访问。' : '容器未处于可服务状态，请检查运行日志。';
      document.querySelector('#overview-health-icon').classList.toggle('offline', !status.online);
      rcon.className = 'connection-state'; rcon.textContent = 'RCON 已连接';
      onlinePlayers = playersFromResponse(playerData);
      renderOnlinePlayers();
      renderServerMetrics(metricsResponse.ok ? metricsData : null, metricsData.detail);
      if (mapData) {
        syncMapPlayersFromServer(onlinePlayers);
        renderMapPlayers();
        if (selectedMapPlayerId) renderMapPlayerDetail(selectedMapPlayerId);
        renderMapFocusResults();
      }
    } catch (error) {
      state.className = 'status-pill offline'; state.textContent = '不可用';
      rcon.className = 'connection-state offline'; rcon.textContent = 'RCON 未连接';
      document.querySelector('#overview-state-title').textContent = '服务器状态不可用';
      document.querySelector('#overview-state-copy').textContent = error.message;
      document.querySelector('#overview-health-icon').classList.add('offline');
      renderServerMetrics(null, error.message);
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
    discoveredWorlds = data.worlds;
    if (!activeWorld && discoveredWorlds.length === 1) activeWorld = discoveredWorlds[0].path;
    rootNode.textContent = data.root;
    worldsNode.innerHTML = '';
    for (const world of data.worlds) worldsNode.append(renderWorld(world));
    if (!data.worlds.length) worldsNode.innerHTML = '<div class="empty">没有发现 Level.sav</div>';
    if (!document.querySelector('[data-page="map"]').classList.contains('hidden')) loadWorldMap();
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
      button.textContent = '重新诊断';
      activeWorld = world.path;
      mapData = null;
      await Promise.all([loadUsers(), loadContainers(), loadGuilds()]);
      document.querySelector('#resource-empty').classList.add('hidden');
      showResourceTab('containers');
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
    const row = containerTemplate.content.firstElementChild.cloneNode(true);
    row.querySelector('.container-label').textContent = container.label || '未命名容器';
    row.querySelector('.container-type').textContent = container.type_name;
    row.querySelector('.container-id').textContent = container.container_id;
    row.querySelector('.container-usage').textContent = `${container.occupied_slots}/${container.slot_capacity || '—'} 槽`;
    row.classList.toggle('active', container.container_id === selectedContainerId);
    row.addEventListener('click', () => selectContainer(container.container_id));
    containersNode.append(row);
  }
  if (!rows.length) containersNode.innerHTML = '<div class="empty">没有匹配的箱子或容器</div>';
  if (rows.length && !rows.some(row => row.container_id === selectedContainerId)) selectContainer(rows[0].container_id);
}

function selectContainer(containerId) {
  selectedContainerId = containerId;
  const container = loadedContainers.find(row => row.container_id === containerId);
  [...containersNode.querySelectorAll('.container-row')].forEach(row => row.classList.toggle('active', row.querySelector('.container-id').textContent === containerId));
  const detailRoot = document.querySelector('#container-detail');
  detailRoot.innerHTML = '';
  if (!container) {
    detailRoot.innerHTML = '<div class="detail-empty"><i class="ph ph-archive" aria-hidden="true"></i><strong>选择一个储物箱</strong><p>道具、数量和技术信息将在这里展示。</p></div>';
    return;
  }
  const detail = document.querySelector('#container-detail-template').content.firstElementChild.cloneNode(true);
  detail.querySelector('.container-label').textContent = container.label || '未命名容器';
  detail.querySelector('.container-type').textContent = container.type_name;
  detail.querySelector('.slot-usage').textContent = `${container.occupied_slots} / ${container.slot_capacity || '—'}`;
  detail.querySelector('.item-total').textContent = `${container.total_items.toLocaleString()} 件`;
  detail.querySelector('.container-id').textContent = container.container_id;
  detail.querySelector('.object-id').textContent = container.object_id;
  const items = detail.querySelector('.container-items');
  const occupied = container.slots.filter(slot => slot.item_id !== 'None' && slot.count > 0);
  if (!occupied.length) items.innerHTML = '<p class="container-empty">这个储物箱是空的</p>';
  for (const slot of occupied) {
    const row = document.createElement('div'); row.className = 'container-item';
    const main = document.createElement('div'); main.className = 'container-item-main';
    const image = document.createElement('img'); image.className = 'mini-item-icon'; image.alt = ''; image.loading = 'lazy';
    if (slot.icon_url) image.src = slot.icon_url; else image.classList.add('hidden');
    const copy = document.createElement('span'); copy.innerHTML = '<strong></strong><small></small>';
    copy.querySelector('strong').textContent = slot.name_zh;
    copy.querySelector('small').textContent = `${slot.category} · ${slot.item_id}`;
    const count = document.createElement('b'); count.textContent = slot.count.toLocaleString();
    main.append(image, copy); row.append(main, count); items.append(row);
  }
  detailRoot.append(detail);
}

function guildSearchText(guild) {
  const members = (guild.players || []).flatMap(player => [player.nickname, player.player_uid]);
  return [guild.name, guild.display_name, guild.admin_player_uid, ...members].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN');
}

async function loadGuilds() {
  if (!activeWorld) return;
  guildPanel.classList.remove('hidden');
  guildsNode.innerHTML = '<div class="empty">正在解码公会成员与据点位置…</div>';
  const response = await fetch(`/api/world/guilds?path=${encodeURIComponent(activeWorld)}`);
  const data = await response.json();
  if (!response.ok) { guildsNode.innerHTML = `<div class="empty">${data.detail}</div>`; return; }
  activeWorldHash = data.level_sha256;
  loadedGuilds = data.guilds;
  guildSummary.textContent = `${data.count} 个公会 · ${data.base_count} 个据点 · 只读展示`;
  if (!selectedGuildId || !loadedGuilds.some(guild => guild.guild_id === selectedGuildId)) {
    selectedGuildId = loadedGuilds.find(guild => guild.players.some(player => player.player_uid.toLowerCase() === OWNER_PLAYER_UID))?.guild_id || loadedGuilds[0]?.guild_id;
  }
  renderGuilds();
}

function renderGuilds() {
  const query = guildQuery.value.trim().toLocaleLowerCase('zh-CN');
  const rows = loadedGuilds.filter(guild => !query || guildSearchText(guild).includes(query));
  guildsNode.innerHTML = '';
  for (const guild of rows) {
    const row = document.createElement('button'); row.className = 'resource-row guild-row'; row.dataset.guildId = guild.guild_id;
    const icon = document.createElement('span'); icon.className = 'resource-row-icon'; icon.innerHTML = '<i class="ph ph-buildings" aria-hidden="true"></i>';
    const copy = document.createElement('span'); copy.className = 'resource-row-copy';
    const name = document.createElement('strong'); name.textContent = guild.display_name;
    const facts = document.createElement('small'); facts.textContent = `${guild.member_count} 名成员 · ${guild.base_count} 个据点`;
    copy.append(name, facts);
    const level = document.createElement('span'); level.className = 'guild-level'; level.textContent = `Lv.${guild.base_camp_level}`;
    row.append(icon, copy, level);
    row.classList.toggle('active', guild.guild_id === selectedGuildId);
    row.addEventListener('click', () => selectGuild(guild.guild_id));
    guildsNode.append(row);
  }
  if (!rows.length) guildsNode.innerHTML = '<div class="empty">没有匹配的公会或成员</div>';
  if (rows.length && !rows.some(guild => guild.guild_id === selectedGuildId)) selectGuild(rows[0].guild_id);
  else if (document.querySelector('[data-resource-tab="guilds"]').classList.contains('active')) selectGuild(selectedGuildId);
}

function guildStat(label, value) {
  const stat = document.createElement('div');
  const caption = document.createElement('small'); caption.textContent = label;
  const number = document.createElement('strong'); number.textContent = value;
  stat.append(caption, number); return stat;
}

function renderGuildDetail(guild) {
  const card = document.createElement('article'); card.className = 'container-detail-content guild-detail-content';
  const header = document.createElement('header');
  const title = document.createElement('div'); title.className = 'detail-title';
  const icon = document.createElement('span'); icon.className = 'detail-icon'; icon.innerHTML = '<i class="ph ph-buildings" aria-hidden="true"></i>';
  const copy = document.createElement('div');
  const eyebrow = document.createElement('p'); eyebrow.className = 'eyebrow'; eyebrow.textContent = '公会与据点';
  const heading = document.createElement('h2'); heading.textContent = guild.display_name;
  const subtitle = document.createElement('p'); subtitle.className = 'container-type'; subtitle.textContent = `公会等级 Lv.${guild.base_camp_level}`;
  copy.append(eyebrow, heading, subtitle); title.append(icon, copy);
  const state = document.createElement('span'); state.className = 'read-only-state'; state.innerHTML = '<i class="ph ph-eye" aria-hidden="true"></i> 只读';
  header.append(title, state); card.append(header);

  const stats = document.createElement('div'); stats.className = 'detail-stats';
  stats.append(guildStat('成员', `${guild.member_count} 人`), guildStat('据点', `${guild.base_count} 处`)); card.append(stats);

  const memberSection = document.createElement('section'); memberSection.className = 'guild-section';
  const memberHeading = document.createElement('h3'); memberHeading.textContent = '成员'; memberSection.append(memberHeading);
  const memberList = document.createElement('div'); memberList.className = 'guild-member-list';
  for (const member of guild.players) {
    const row = document.createElement('div'); row.className = 'guild-member-row';
    if (member.player_uid.toLowerCase() === OWNER_PLAYER_UID) row.classList.add('owner');
    const avatar = document.createElement('span'); avatar.className = 'guild-member-icon';
    avatar.innerHTML = `<i class="ph ${member.player_uid === guild.admin_player_uid ? 'ph-crown' : 'ph-user'}" aria-hidden="true"></i>`;
    const memberCopy = document.createElement('span');
    const name = document.createElement('strong'); name.textContent = member.nickname || '未命名成员';
    const uid = document.createElement('code'); uid.textContent = member.player_uid;
    memberCopy.append(name, uid);
    const badges = document.createElement('span'); badges.className = 'guild-member-badges';
    if (member.player_uid === guild.admin_player_uid) { const badge = document.createElement('b'); badge.textContent = '会长'; badges.append(badge); }
    if (member.player_uid.toLowerCase() === OWNER_PLAYER_UID) { const badge = document.createElement('b'); badge.textContent = '我'; badges.append(badge); }
    const linkedUser = loadedUsers.find(user => user.player_uid === member.player_uid);
    if (linkedUser) {
      const view = document.createElement('button'); view.className = 'icon-button guild-view-player'; view.title = '查看玩家存档'; view.innerHTML = '<i class="ph ph-arrow-right" aria-hidden="true"></i>';
      view.addEventListener('click', () => { showResourceTab('users'); selectUser(member.player_uid); }); badges.append(view);
    }
    row.append(avatar, memberCopy, badges); memberList.append(row);
  }
  if (!guild.players.length) memberList.innerHTML = '<p class="container-empty">成员块无法从这个存档版本解码</p>';
  memberSection.append(memberList); card.append(memberSection);

  const baseSection = document.createElement('section'); baseSection.className = 'guild-section';
  const baseHeading = document.createElement('h3'); baseHeading.textContent = '据点'; baseSection.append(baseHeading);
  const baseList = document.createElement('div'); baseList.className = 'guild-base-list';
  guild.base_camps.forEach((base, index) => {
    const row = document.createElement('div'); row.className = 'guild-base-row';
    const baseIcon = document.createElement('span'); baseIcon.className = 'guild-base-icon'; baseIcon.innerHTML = '<i class="ph ph-map-pin" aria-hidden="true"></i>';
    const baseCopy = document.createElement('span');
    const name = document.createElement('strong'); name.textContent = `据点 ${index + 1}`;
    const location = document.createElement('code');
    location.textContent = `X ${Math.round(base.location.x).toLocaleString()} · Y ${Math.round(base.location.y).toLocaleString()} · Z ${Math.round(base.location.z).toLocaleString()}`;
    baseCopy.append(name, location);
    const radius = document.createElement('small'); radius.textContent = `范围 ${Math.round(base.area_range).toLocaleString()}`;
    row.append(baseIcon, baseCopy, radius); baseList.append(row);
  });
  if (!guild.base_camps.length) baseList.innerHTML = '<p class="container-empty">这个公会没有据点</p>';
  baseSection.append(baseList); card.append(baseSection);

  const technical = document.createElement('details'); technical.className = 'technical-info';
  const summary = document.createElement('summary'); summary.textContent = '查看技术信息';
  const values = document.createElement('dl');
  for (const [label, value] of [['公会 GUID', guild.guild_id], ['会长 UID', guild.admin_player_uid]]) {
    const row = document.createElement('div'); const term = document.createElement('dt'); term.textContent = label;
    const detail = document.createElement('dd'); const code = document.createElement('code'); code.textContent = value; detail.append(code); row.append(term, detail); values.append(row);
  }
  technical.append(summary, values); card.append(technical);
  return card;
}

function selectGuild(guildId) {
  selectedGuildId = guildId;
  guildsNode.querySelectorAll('.guild-row').forEach(row => row.classList.toggle('active', row.dataset.guildId === guildId));
  const guild = loadedGuilds.find(row => row.guild_id === guildId);
  guildDetail.innerHTML = '';
  if (guild) guildDetail.append(renderGuildDetail(guild));
}

function normalizedPlayerId(value) {
  return String(value || '').replaceAll('-', '').toLocaleLowerCase('en-US');
}

function mapPosition(location) {
  const bounds = mapData.landscape;
  const mapX = -256 + (256 * (location.x - bounds.min_x)) / (bounds.max_x - bounds.min_x);
  const mapY = (256 * (location.y - bounds.min_y)) / (bounds.max_y - bounds.min_y);
  return {left: (mapY / 256) * 100, top: (-mapX / 256) * 100};
}

function serverPlayersForMap(players) {
  return (Array.isArray(players) ? players : []).flatMap(player => {
    if (player.location_x === null || player.location_x === undefined || player.location_y === null || player.location_y === undefined) return [];
    const x = Number(player.location_x);
    const y = Number(player.location_y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return [];
    return [{
      ...player,
      nickname: player.name || '未命名玩家',
      location: {x, y},
      location_source: 'Palworld REST /v1/api/players',
    }];
  });
}

function guildBasesForMap(guilds) {
  return guilds.flatMap(guild => (guild.base_camps || []).map((base, index) => ({
    ...base,
    guild_id: guild.guild_id,
    guild_name: guild.display_name,
    guild_level: guild.base_camp_level,
    guild_member_count: guild.member_count,
    guild_admin_player_uid: guild.admin_player_uid,
    guild_member_names: (guild.players || []).map(player => player.nickname).filter(Boolean),
    base_index: index + 1,
    is_owner_guild: (guild.players || []).some(player => normalizedPlayerId(player.player_uid) === normalizedPlayerId(OWNER_PLAYER_UID)),
  })));
}

function syncMapSummary() {
  if (!mapData) return;
  document.querySelector('#map-player-count').textContent = mapData.mappable_player_count;
  document.querySelector('#base-camp-count').textContent = mapData.base_camps.length;
  document.querySelector('#fast-travel-count').textContent = mapData.fast_travel_count;
  document.querySelector('#boss-tower-count').textContent = mapData.boss_tower_count;
  const snapshot = new Date(mapData.captured_at * 1000).toLocaleTimeString('zh-CN', {hour12:false});
  document.querySelector('#map-snapshot').textContent = `玩家实时 · ${snapshot} · 据点存档快照`;
  const result = document.querySelector('#map-result');
  const guildNote = mapData.guild_warning ? ` · ${mapData.guild_warning}` : ` · ${mapData.base_camps.length} 个存档据点`;
  result.textContent = `${mapData.mappable_player_count} 名在线玩家${guildNote} · ${mapData.fast_travel_count} 个传送点 · ${mapData.boss_tower_count} 座塔主塔`;
  result.className = mapData.guild_warning ? 'sync-result' : 'sync-result ok';
}

function syncMapPlayersFromServer(players) {
  if (!mapData) return;
  mapData.players = serverPlayersForMap(players);
  mapData.mappable_player_count = mapData.players.length;
  mapData.captured_at = Date.now() / 1000;
  syncMapSummary();
}

function updateMapPlayerPositions() {
  document.querySelectorAll('#map-player-layer .map-player-marker').forEach(marker => {
    const baseLeft = Number(marker.dataset.mapLeft);
    const baseTop = Number(marker.dataset.mapTop);
    const left = 50 + (baseLeft - 50) * mapView.zoom;
    const top = 50 + (baseTop - 50) * mapView.zoom;
    marker.style.left = `calc(${left}% + ${mapView.panX}px)`;
    marker.style.top = `calc(${top}% + ${mapView.panY}px)`;
  });
}

function updateMapTransform() {
  const plane = document.querySelector('#map-plane');
  plane.style.transform = `translate(${mapView.panX}px, ${mapView.panY}px) scale(${mapView.zoom})`;
  document.querySelector('#map-zoom-label').textContent = `${Math.round(mapView.zoom * 100)}%`;
  updateMapPlayerPositions();
}

function setMapZoom(next) {
  mapView.zoom = Math.max(1, Math.min(4, next));
  if (mapView.zoom === 1) { mapView.panX = 0; mapView.panY = 0; }
  updateMapTransform();
}

function resetMapView() {
  mapView.zoom = 1;
  mapView.panX = 0;
  mapView.panY = 0;
  updateMapTransform();
}

function renderFastTravelMarkers() {
  const layer = document.querySelector('#fast-travel-layer');
  layer.innerHTML = '';
  if (!mapData) return;
  const fragment = document.createDocumentFragment();
  mapData.fast_travel.forEach(([x, y], index) => {
    const position = mapPosition({x, y});
    const marker = document.createElement('span');
    marker.className = 'fast-travel-marker';
    marker.style.left = `${position.left}%`;
    marker.style.top = `${position.top}%`;
    marker.title = `传送点 ${index + 1} · X ${Math.round(x).toLocaleString()} · Y ${Math.round(y).toLocaleString()}`;
    marker.setAttribute('aria-label', marker.title);
    fragment.append(marker);
  });
  layer.append(fragment);
  layer.classList.toggle('hidden', !document.querySelector('#show-fast-travel').checked);
}

function renderBossTowerMarkers() {
  const layer = document.querySelector('#boss-tower-layer');
  layer.innerHTML = '';
  if (!mapData) return;
  const fragment = document.createDocumentFragment();
  mapData.boss_tower.forEach(([x, y], index) => {
    const position = mapPosition({x, y});
    const marker = document.createElement('span');
    marker.className = 'boss-tower-marker';
    marker.style.left = `${position.left}%`;
    marker.style.top = `${position.top}%`;
    marker.innerHTML = '<i class="ph ph-crown" aria-hidden="true"></i>';
    marker.title = `塔主塔 ${index + 1} · X ${Math.round(x).toLocaleString()} · Y ${Math.round(y).toLocaleString()}`;
    marker.setAttribute('aria-label', marker.title);
    fragment.append(marker);
  });
  layer.append(fragment);
  layer.classList.toggle('hidden', !document.querySelector('#show-boss-towers').checked);
}

function renderBaseCampMarkers() {
  const layer = document.querySelector('#base-camp-layer');
  layer.innerHTML = '';
  if (!mapData) return;
  const xSpan = mapData.landscape.max_x - mapData.landscape.min_x;
  const ySpan = mapData.landscape.max_y - mapData.landscape.min_y;
  const fragment = document.createDocumentFragment();
  for (const base of mapData.base_camps) {
    const position = mapPosition(base.location);
    const range = document.createElement('span');
    range.className = `map-base-range${base.is_owner_guild ? ' owner' : ''}`;
    range.style.left = `${position.left}%`;
    range.style.top = `${position.top}%`;
    range.style.width = `${(base.area_range * 2 / ySpan) * 100}%`;
    range.style.height = `${(base.area_range * 2 / xSpan) * 100}%`;

    const marker = document.createElement('button');
    marker.type = 'button';
    marker.className = `map-base-marker${base.is_owner_guild ? ' owner' : ''}`;
    marker.classList.toggle('active', base.base_id === selectedMapBaseId);
    marker.style.left = `${position.left}%`;
    marker.style.top = `${position.top}%`;
    marker.title = `${base.guild_name} · 据点 ${base.base_index} · 范围 ${Math.round(base.area_range).toLocaleString()}`;
    const pin = document.createElement('span'); pin.className = 'map-base-pin'; pin.innerHTML = '<i class="ph ph-buildings" aria-hidden="true"></i>';
    const label = document.createElement('span'); label.className = 'map-base-label'; label.textContent = base.guild_name;
    marker.append(pin, label);
    marker.addEventListener('pointerdown', event => event.stopPropagation());
    marker.addEventListener('click', event => { event.stopPropagation(); selectMapBase(base.base_id); });
    fragment.append(range, marker);
  }
  layer.append(fragment);
  layer.classList.toggle('hidden', !document.querySelector('#show-base-camps').checked);
}

function playerFanout(players) {
  const groups = new Map();
  for (const player of players) {
    const position = mapPosition(player.location);
    player.mapPosition = position;
    const key = `${Math.round(position.left)}:${Math.round(position.top)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(player);
  }
  const offsets = new Map();
  for (const group of groups.values()) {
    group.forEach((player, index) => {
      if (group.length === 1) { offsets.set(player.player_uid, {x:0, y:0}); return; }
      const radius = group.length <= 4 ? 20 : 28;
      const angle = -Math.PI / 2 + (index / group.length) * Math.PI * 2;
      offsets.set(player.player_uid, {x:Math.cos(angle) * radius, y:Math.sin(angle) * radius});
    });
  }
  return offsets;
}

function renderMapPlayers() {
  const layer = document.querySelector('#map-player-layer');
  layer.innerHTML = '';
  if (!mapData) return;
  const players = mapData.players.filter(player => player.location);
  const offsets = playerFanout(players);
  const fragment = document.createDocumentFragment();
  for (const player of players) {
    const offset = offsets.get(player.player_uid) || {x:0,y:0};
    const marker = document.createElement('button');
    marker.type = 'button';
    marker.className = `map-player-marker online${normalizedPlayerId(player.player_uid) === normalizedPlayerId(OWNER_PLAYER_UID) ? ' owner' : ''}`;
    marker.classList.toggle('active', normalizedPlayerId(player.player_uid) === normalizedPlayerId(selectedMapPlayerId));
    marker.dataset.mapLeft = player.mapPosition.left;
    marker.dataset.mapTop = player.mapPosition.top;
    marker.style.setProperty('--fan-x', `${offset.x}px`);
    marker.style.setProperty('--fan-y', `${offset.y}px`);
    marker.title = `${player.nickname || '未命名玩家'} · Lv.${player.level} · 服务器实时位置`;
    const pin = document.createElement('span'); pin.className = 'map-player-pin'; pin.innerHTML = '<i class="ph ph-user" aria-hidden="true"></i>';
    const label = document.createElement('span'); label.className = 'map-player-label'; label.textContent = player.nickname || '未命名玩家';
    marker.append(pin, label);
    marker.addEventListener('pointerdown', event => event.stopPropagation());
    marker.addEventListener('click', event => { event.stopPropagation(); selectMapPlayer(player.player_uid); });
    fragment.append(marker);
  }
  layer.append(fragment);
  updateMapPlayerPositions();
  layer.classList.toggle('hidden', !document.querySelector('#show-map-players').checked);
}

function detailRow(label, value, code = false) {
  const row = document.createElement('div');
  const term = document.createElement('dt'); term.textContent = label;
  const data = document.createElement('dd');
  const content = document.createElement(code ? 'code' : 'span'); content.textContent = value;
  data.append(content); row.append(term, data); return row;
}

function renderMapPlayerDetail(playerUid) {
  const root = document.querySelector('#map-player-detail');
  const player = mapData?.players.find(row => normalizedPlayerId(row.player_uid) === normalizedPlayerId(playerUid));
  root.innerHTML = '';
  if (!player) {
    root.innerHTML = '<div class="detail-empty"><i class="ph ph-crosshair" aria-hidden="true"></i><strong>选择玩家或据点</strong><p>这里会显示实时玩家命令，或存档据点的公会、范围与精确坐标。</p></div>';
    return;
  }
  const article = document.createElement('article'); article.className = 'map-player-card';
  const head = document.createElement('header');
  const identity = document.createElement('div');
  const eyebrow = document.createElement('p'); eyebrow.className = 'eyebrow'; eyebrow.textContent = '当前在线 · 服务器实时位置';
  const name = document.createElement('h2'); name.textContent = player.nickname || '未命名玩家';
  const level = document.createElement('p'); level.className = 'map-player-level'; level.textContent = `Lv.${player.level}`;
  identity.append(eyebrow, name, level);
  const state = document.createElement('span'); state.className = 'map-player-state online'; state.textContent = '在线';
  head.append(identity, state);
  const location = document.createElement('div'); location.className = 'map-location-card';
  location.innerHTML = '<i class="ph ph-crosshair" aria-hidden="true"></i><span><small>服务器实时坐标</small><strong></strong></span>';
  location.querySelector('strong').textContent = `X ${player.location.x.toFixed(2)} · Y ${player.location.y.toFixed(2)}`;
  const facts = document.createElement('dl'); facts.className = 'map-player-facts';
  facts.append(
    detailRow('玩家 UID', player.player_uid, true),
    detailRow('位置来源', player.location_source),
  );
  if (player.command_id) facts.append(detailRow('命令 ID', player.command_id, true));
  const actions = document.createElement('div'); actions.className = 'map-player-actions';
  actions.append(playerCopyButton(player.player_uid, '复制玩家 UID', 'secondary'));
  if (player.command_id) {
    actions.append(
      playerCopyButton(player.command_id, '复制命令 ID', 'secondary'),
      playerCopyButton(`/TeleportToMe ${player.command_id}`, 'TeleportToMe', 'secondary'),
      playerCopyButton(`/TeleportToPlayer ${player.command_id}`, 'TeleportToPlayer', 'secondary'),
    );
  } else {
    const disabled = document.createElement('button'); disabled.disabled = true; disabled.textContent = 'Teleport 仅在线可用'; disabled.title = '现有服务器命令需要在线列表提供的命令 ID'; actions.append(disabled);
  }
  const full = document.createElement('button'); full.className = 'primary'; full.textContent = '打开完整玩家详情';
  full.addEventListener('click', async () => {
    showView('saves'); showResourceTab('users');
    if (!loadedUsers.length) await loadUsers();
    selectUser(player.player_uid);
  });
  actions.append(full);
  article.append(head, location, facts, actions); root.append(article);
}

function renderMapBaseDetail(baseId) {
  const root = document.querySelector('#map-player-detail');
  const base = mapData?.base_camps.find(row => row.base_id === baseId);
  root.innerHTML = '';
  if (!base) { renderMapPlayerDetail(null); return; }
  const article = document.createElement('article'); article.className = 'map-player-card map-base-card';
  const head = document.createElement('header');
  const identity = document.createElement('div');
  const eyebrow = document.createElement('p'); eyebrow.className = 'eyebrow'; eyebrow.textContent = base.is_owner_guild ? '我的公会 · 存档据点' : '公会 · 存档据点';
  const name = document.createElement('h2'); name.textContent = `${base.guild_name} · 据点 ${base.base_index}`;
  const level = document.createElement('p'); level.className = 'map-player-level'; level.textContent = `公会 Lv.${base.guild_level} · ${base.guild_member_count} 名成员`;
  identity.append(eyebrow, name, level);
  const state = document.createElement('span'); state.className = 'map-player-state'; state.textContent = '只读快照';
  head.append(identity, state);
  const location = document.createElement('div'); location.className = 'map-location-card';
  location.innerHTML = '<i class="ph ph-map-pin" aria-hidden="true"></i><span><small>存档精确坐标</small><strong></strong></span>';
  location.querySelector('strong').textContent = `X ${base.location.x.toFixed(2)} · Y ${base.location.y.toFixed(2)} · Z ${base.location.z.toFixed(2)}`;
  const facts = document.createElement('dl'); facts.className = 'map-player-facts';
  facts.append(
    detailRow('据点范围', Math.round(base.area_range).toLocaleString()),
    detailRow('据点 GUID', base.base_id, true),
    detailRow('公会 GUID', base.guild_id, true),
    detailRow('会长 UID', base.guild_admin_player_uid, true),
  );
  const actions = document.createElement('div'); actions.className = 'map-player-actions';
  const coordinates = `${base.location.x.toFixed(2)}, ${base.location.y.toFixed(2)}, ${base.location.z.toFixed(2)}`;
  actions.append(playerCopyButton(coordinates, '复制 XYZ 坐标', 'secondary'), playerCopyButton(base.base_id, '复制据点 GUID', 'secondary'));
  const full = document.createElement('button'); full.className = 'primary'; full.textContent = '打开公会详情';
  full.addEventListener('click', async () => {
    showView('saves'); showResourceTab('guilds');
    if (!loadedGuilds.length) await loadGuilds();
    selectGuild(base.guild_id);
  });
  actions.append(full);
  article.append(head, location, facts, actions); root.append(article);
}

function focusMapLocation(location, minimumZoom = 2.4) {
  if (!mapData) return;
  const position = mapPosition(location);
  mapView.zoom = Math.max(mapView.zoom, minimumZoom);
  const size = document.querySelector('#map-stage').getBoundingClientRect();
  mapView.panX = -((position.left - 50) / 100) * size.width * mapView.zoom;
  mapView.panY = -((position.top - 50) / 100) * size.height * mapView.zoom;
  updateMapTransform();
}

function mapSearchTargets() {
  if (!mapData) return [];
  const players = mapData.players.map(player => ({
    kind: 'player', id: player.player_uid, label: player.nickname, meta: `在线玩家 · Lv.${player.level}`,
    search: `${player.nickname} ${player.player_uid}`, location: player.location,
  }));
  const bases = mapData.base_camps.map(base => ({
    kind: 'base', id: base.base_id, label: `${base.guild_name} · 据点 ${base.base_index}`,
    meta: `公会 Lv.${base.guild_level} · 范围 ${Math.round(base.area_range).toLocaleString()}`,
    search: `${base.guild_name} ${base.base_id} ${base.guild_id} ${base.guild_member_names.join(' ')}`, location: base.location,
  }));
  const towers = mapData.boss_tower.map(([x, y], index) => ({
    kind: 'tower', id: String(index), label: `塔主塔 ${index + 1}`, meta: `X ${Math.round(x).toLocaleString()} · Y ${Math.round(y).toLocaleString()}`,
    search: `塔主塔 ${index + 1} boss tower`, location: {x, y},
  }));
  return [...players, ...bases, ...towers];
}

function focusMapTarget(target) {
  if (target.kind === 'player') selectMapPlayer(target.id);
  else if (target.kind === 'base') selectMapBase(target.id);
  else { selectedMapPlayerId = null; selectedMapBaseId = null; renderMapPlayers(); renderBaseCampMarkers(); renderMapPlayerDetail(null); }
  focusMapLocation(target.location);
  document.querySelector('#map-focus-results').classList.add('hidden');
}

function renderMapFocusResults() {
  const root = document.querySelector('#map-focus-results');
  const query = document.querySelector('#map-focus-query').value.trim().toLocaleLowerCase('zh-CN');
  root.innerHTML = '';
  if (!query || !mapData) { root.classList.add('hidden'); return; }
  const targets = mapSearchTargets().filter(target => target.search.toLocaleLowerCase('zh-CN').includes(query)).slice(0, 8);
  for (const target of targets) {
    const button = document.createElement('button'); button.type = 'button';
    const icon = target.kind === 'player' ? 'ph-user' : target.kind === 'base' ? 'ph-buildings' : 'ph-crown';
    button.innerHTML = `<i class="ph ${icon}" aria-hidden="true"></i><span><strong></strong><small></small></span>`;
    button.querySelector('strong').textContent = target.label;
    button.querySelector('small').textContent = target.meta;
    button.addEventListener('click', () => focusMapTarget(target));
    root.append(button);
  }
  if (!targets.length) root.innerHTML = '<p>没有匹配的地图目标</p>';
  root.classList.remove('hidden');
}

function selectMapPlayer(playerUid) {
  selectedMapPlayerId = playerUid;
  selectedMapBaseId = null;
  renderMapPlayers();
  renderBaseCampMarkers();
  renderMapPlayerDetail(playerUid);
}

function selectMapBase(baseId) {
  selectedMapBaseId = baseId;
  selectedMapPlayerId = null;
  renderMapPlayers();
  renderBaseCampMarkers();
  renderMapBaseDetail(baseId);
}

async function loadWorldMap() {
  if (mapRequest) return mapRequest;
  const empty = document.querySelector('#map-empty');
  const result = document.querySelector('#map-result');
  empty.classList.remove('hidden');
  empty.querySelector('strong').textContent = '正在读取服务器玩家位置';
  empty.querySelector('p').textContent = '直接请求 palworld-server Palworld REST 在线玩家接口。';
  result.textContent = '';
  mapRequest = (async () => {
    try {
      const guildPromise = activeWorld
        ? fetch(`/api/world/guilds?path=${encodeURIComponent(activeWorld)}`).then(async response => {
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || '存档据点读取失败');
            return payload;
          }).catch(error => ({guilds: [], base_count: 0, warning: `据点未加载：${error.message}`}))
        : Promise.resolve({guilds: [], base_count: 0, warning: '尚未选择本地世界，据点未加载'});
      const [mapResponse, playersResponse, guildData] = await Promise.all([fetch('/api/world/map'), fetch('/api/server/players'), guildPromise]);
      const data = await mapResponse.json();
      const playerData = await playersResponse.json();
      if (!mapResponse.ok) throw new Error(data.detail || '地图数据读取失败');
      if (!playersResponse.ok) throw new Error(playerData.detail || '服务器玩家位置读取失败');
      onlinePlayers = playersFromResponse(playerData);
      renderOnlinePlayers();
      if (!guildData.warning) {
        loadedGuilds = guildData.guilds;
        activeWorldHash = guildData.level_sha256;
      }
      mapData = {
        ...data,
        players: [],
        guilds: guildData.guilds,
        base_camps: guildBasesForMap(guildData.guilds),
        guild_warning: guildData.warning || '',
      };
      syncMapPlayersFromServer(onlinePlayers);
      renderFastTravelMarkers();
      renderBossTowerMarkers();
      const selectedBaseStillExists = mapData.base_camps.some(base => base.base_id === selectedMapBaseId);
      if (!selectedBaseStillExists && (!selectedMapPlayerId || !mapData.players.some(player => normalizedPlayerId(player.player_uid) === normalizedPlayerId(selectedMapPlayerId)))) {
        selectedMapPlayerId = mapData.players.find(player => normalizedPlayerId(player.player_uid) === normalizedPlayerId(OWNER_PLAYER_UID))?.player_uid || mapData.players[0]?.player_uid || null;
      }
      renderMapPlayers();
      renderBaseCampMarkers();
      if (selectedBaseStillExists) renderMapBaseDetail(selectedMapBaseId);
      else { selectedMapBaseId = null; renderMapPlayerDetail(selectedMapPlayerId); }
      renderMapFocusResults();
      empty.classList.add('hidden');
      syncMapSummary();
    } catch (error) {
      empty.classList.remove('hidden');
      empty.querySelector('strong').textContent = '地图读取失败';
      empty.querySelector('p').textContent = error.message;
      result.textContent = error.message; result.className = 'sync-result error';
    } finally { mapRequest = null; }
  })();
  return mapRequest;
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
  if (!selectedUserId || !data.users.some(user => user.player_uid === selectedUserId)) {
    selectedUserId = data.users.find(user => user.player_uid.toLowerCase() === OWNER_PLAYER_UID)?.player_uid || data.users[0]?.player_uid;
  }
  if (document.querySelector('[data-resource-tab="users"]').classList.contains('active')) selectUser(selectedUserId);
}

function selectUser(playerUid) {
  selectedUserId = playerUid;
  [...usersNode.children].forEach((node, index) => node.classList.toggle('active', loadedUsers[index]?.player_uid === playerUid));
  const user = loadedUsers.find(row => row.player_uid === playerUid);
  playerDetail.innerHTML = '';
  if (user) playerDetail.append(renderUser(user));
}

const OWNED_PAL_PAGE_SIZE = 40;

function ownedPalSearchText(pal) {
  const skills = (pal.passive_skills || []).flatMap(skill => [skill.skill_id, skill.name_zh, skill.description]);
  return [pal.name_zh, pal.nickname, pal.character_id, ...skills].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN');
}

function renderOwnedPal(pal) {
  const row = document.createElement('details'); row.className = 'pal-chip';
  const header = document.createElement('summary');
  const image = document.createElement('img'); image.className = 'mini-pal-icon'; image.alt = ''; image.loading = 'lazy';
  if (pal.icon_url) image.src = pal.icon_url; else image.classList.add('hidden');
  const copy = document.createElement('span'); copy.className = 'pal-chip-copy';
  const label = document.createElement('strong');
  label.textContent = `${pal.name_zh}${pal.nickname ? ` · ${pal.nickname}` : ''}`;
  const facts = document.createElement('small');
  const gender = pal.gender === 'EPalGenderType::Male' ? '雄性' : pal.gender === 'EPalGenderType::Female' ? '雌性' : '';
  facts.textContent = [`Lv.${pal.level}`, gender, pal.is_boss ? 'Boss' : '', pal.is_lucky ? '闪光' : '', pal.is_tower ? '塔主' : '', pal.condensation_rank > 1 ? `浓缩 ${pal.condensation_rank}` : ''].filter(Boolean).join(' · ');
  copy.append(label, facts);
  const id = document.createElement('code'); id.textContent = pal.character_id;
  const chevron = document.createElement('i'); chevron.className = 'ph ph-caret-down pal-detail-chevron'; chevron.setAttribute('aria-hidden', 'true');
  header.append(image, copy, id, chevron);

  const detail = document.createElement('div'); detail.className = 'pal-detail-body';
  const stats = document.createElement('div'); stats.className = 'pal-stat-grid';
  const statRows = [
    ['当前 HP', pal.hp || '—'],
    ['生命个体值', pal.talents?.hp || '—'],
    ['攻击个体值', pal.talents?.attack || '—'],
    ['防御个体值', pal.talents?.defense || '—'],
  ];
  for (const [name, value] of statRows) {
    const stat = document.createElement('span');
    const caption = document.createElement('small'); caption.textContent = name;
    const number = document.createElement('strong'); number.textContent = value;
    stat.append(caption, number); stats.append(stat);
  }
  detail.append(stats);
  const boosts = Object.entries(pal.rank_boosts || {}).filter(([, value]) => value);
  if (boosts.length) {
    const boostLabels = {attack:'攻击', defense:'防御', work_speed:'工作速度'};
    const boost = document.createElement('p'); boost.className = 'pal-rank-boosts';
    boost.textContent = `强化加成 · ${boosts.map(([key, value]) => `${boostLabels[key]} +${value}`).join(' · ')}`;
    detail.append(boost);
  }
  const skillList = document.createElement('div'); skillList.className = 'passive-skill-list';
  const skillHeading = document.createElement('h4'); skillHeading.textContent = `被动技能 · ${(pal.passive_skills || []).length}`; skillList.append(skillHeading);
  for (const skill of pal.passive_skills || []) {
    const skillRow = document.createElement('div'); skillRow.className = 'passive-skill-row';
    const title = document.createElement('span');
    const name = document.createElement('strong'); name.textContent = skill.name_zh;
    const skillId = document.createElement('code'); skillId.textContent = skill.skill_id;
    title.append(name, skillId);
    const description = document.createElement('p'); description.textContent = skill.description || '暂无效果说明。';
    skillRow.append(title, description); skillList.append(skillRow);
  }
  if (!(pal.passive_skills || []).length) {
    const empty = document.createElement('p'); empty.className = 'pal-skill-empty'; empty.textContent = '没有被动技能'; skillList.append(empty);
  }
  detail.append(skillList);
  const technical = document.createElement('p'); technical.className = 'pal-technical'; technical.textContent = `实例 ${pal.instance_id}`; detail.append(technical);
  row.append(header, detail);
  return row;
}

function renderOwnedPals(card, user) {
  const input = card.querySelector('.owned-pal-query');
  const results = card.querySelector('.owned-pal-results');
  const summary = card.querySelector('.owned-pal-summary');
  const more = card.querySelector('.owned-pal-more');
  let visible = OWNED_PAL_PAGE_SIZE;
  const render = (reset = false) => {
    if (reset) visible = OWNED_PAL_PAGE_SIZE;
    const query = input.value.trim().toLocaleLowerCase('zh-CN');
    const filtered = query ? user.pals.filter(pal => ownedPalSearchText(pal).includes(query)) : user.pals;
    results.replaceChildren(...filtered.slice(0, visible).map(renderOwnedPal));
    summary.textContent = `显示 ${Math.min(visible, filtered.length)} / ${filtered.length}`;
    const remaining = Math.max(0, filtered.length - visible);
    more.classList.toggle('hidden', remaining === 0);
    more.textContent = `再加载 ${Math.min(OWNED_PAL_PAGE_SIZE, remaining)} 只`;
    if (!filtered.length) results.innerHTML = '<div class="empty">没有匹配的帕鲁或被动技能</div>';
  };
  input.addEventListener('input', () => render(true));
  more.addEventListener('click', () => { visible += OWNED_PAL_PAGE_SIZE; render(); });
  render();
}

function renderUser(user) {
  const card = userTemplate.content.firstElementChild.cloneNode(true);
  card.querySelector('.user-name').textContent = user.nickname || '未命名用户';
  card.querySelector('.user-id').textContent = user.player_uid;
  card.querySelector('.pal-count').textContent = `${user.pal_count} 只帕鲁`;
  const form = card.querySelector('form');
  for (const field of ['nickname','level','experience','unused_status_points','satiety','technology_points']) form.elements[field].value = user[field] ?? 0;
  card.querySelector('.readonly-data').textContent = `生命值 ${user.hp} · 护盾 ${user.shield_hp} · 声音 ${user.voice_id} · 实例 ${user.instance_id}`;
  renderOwnedPals(card, user);
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
      activeWorldHash = data.level_sha256; backupData = null; status.textContent = `已保存，备份：${data.backup_path}`;
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
      activeWorldHash = data.level_sha256; backupData = null; await loadUsers();
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
    loadedContainers = [];
    loadedUsers = [];
    loadedGuilds = [];
    backupData = null;
    mapData = null;
    selectedMapPlayerId = null;
    selectedMapBaseId = null;
    selectedContainerId = null;
    selectedGuildId = null;
    userPanel.classList.add('hidden');
    containerPanel.classList.add('hidden');
    guildPanel.classList.add('hidden');
    document.querySelector('#resource-empty').classList.remove('hidden');
    document.querySelector('#container-detail').innerHTML = '<div class="detail-empty"><i class="ph ph-archive" aria-hidden="true"></i><strong>选择一个储物箱</strong><p>道具、数量和技术信息将在这里展示。</p></div>';
    document.querySelector('#guild-detail').innerHTML = '<div class="detail-empty"><i class="ph ph-buildings" aria-hidden="true"></i><strong>选择一个公会</strong><p>会长、成员与据点位置会在这里展开。</p></div>';
    await scan();
  } catch (error) {
    result.className = 'sync-result error';
    result.textContent = error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = '<i class="ph ph-arrows-clockwise" aria-hidden="true"></i> 从服务器同步';
  }
});
document.querySelector('#reload-users').addEventListener('click', loadUsers);
let searchTimer;
function setCatalogImage(row, url, fallbackIcon = 'ph-package') {
  const wrap = row.querySelector('.item-icon-wrap');
  const image = row.querySelector('.item-icon');
  const icon = wrap.querySelector('i');
  icon.className = `ph ${fallbackIcon}`;
  if (!url) { wrap.classList.add('missing'); return; }
  image.src = url;
  image.addEventListener('error', () => wrap.classList.add('missing'), {once:true});
}

async function loadItems(query = '') {
  const response = await fetch(`/api/items?q=${encodeURIComponent(query)}&limit=100`);
  const data = await response.json();
  itemSummary.textContent = `${data.total_items.toLocaleString()} 个内部 ID · ${data.localized_items.toLocaleString()} 个中文名称 · 本地图标与详细说明`;
  itemResults.innerHTML = '';
  for (const item of data.results) {
    const row = itemTemplate.content.firstElementChild.cloneNode(true);
    setCatalogImage(row, item.icon_url);
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
  palSummary.textContent = `${data.total_pals.toLocaleString()} 个 CharacterID · ${data.localized_pals.toLocaleString()} 个中文名称 · 本地帕鲁图标`;
  palResults.innerHTML = '';
  for (const pal of data.results) {
    const row = itemTemplate.content.firstElementChild.cloneNode(true);
    setCatalogImage(row, pal.icon_url, 'ph-paw-print');
    row.querySelector('.item-name').textContent = pal.name_zh;
    row.querySelector('.item-description').textContent = 'Palworld 角色数据标识与本地图鉴图标。';
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
let skillSearchTimer;
async function loadSkills(query = '') {
  const response = await fetch(`/api/skills?q=${encodeURIComponent(query)}&limit=100`);
  const data = await response.json();
  skillSummary.textContent = `${data.total_skills.toLocaleString()} 个被动技能 · 可搜索名称、效果与内部 ID`;
  skillResults.innerHTML = '';
  for (const skill of data.results) {
    const row = itemTemplate.content.firstElementChild.cloneNode(true);
    setCatalogImage(row, '', 'ph-sparkle');
    row.querySelector('.item-name').textContent = skill.name_zh;
    row.querySelector('.item-description').textContent = skill.description || '暂无效果说明。';
    row.querySelector('.item-id').textContent = skill.skill_id;
    row.querySelector('.item-category').textContent = '被动技能';
    row.querySelector('.localization').textContent = '中文';
    row.addEventListener('click', () => navigator.clipboard.writeText(skill.skill_id));
    skillResults.append(row);
  }
  if (!data.results.length) skillResults.innerHTML = '<div class="empty">没有匹配的被动技能</div>';
}
skillQuery.addEventListener('input', () => {
  clearTimeout(skillSearchTimer);
  skillSearchTimer = setTimeout(() => loadSkills(skillQuery.value), 180);
});
containerQuery.addEventListener('input', renderContainers);
document.querySelector('#reload-containers').addEventListener('click', loadContainers);
guildQuery.addEventListener('input', renderGuilds);
document.querySelector('#reload-guilds').addEventListener('click', loadGuilds);
document.querySelectorAll('[data-resource-tab]').forEach(button => button.addEventListener('click', () => showResourceTab(button.dataset.resourceTab)));
document.querySelector('#reload-backups').addEventListener('click', loadBackups);
document.querySelector('#backup-query').addEventListener('input', renderBackups);
document.querySelector('#backup-source').addEventListener('change', renderBackups);
const backupRestoreDialog = document.querySelector('#backup-restore-dialog');
const backupRestoreConfirm = document.querySelector('#backup-restore-confirm');
const backupRestoreButton = document.querySelector('#confirm-backup-restore');
backupRestoreConfirm.addEventListener('change', () => { backupRestoreButton.disabled = !backupRestoreConfirm.checked; });
backupRestoreDialog.addEventListener('close', async () => {
  if (backupRestoreDialog.returnValue !== 'confirm') {
    pendingBackupRestore = null;
    setBackupResult('已取消恢复，本地世界未受影响。');
    return;
  }
  const pending = pendingBackupRestore; pendingBackupRestore = null;
  if (!pending) { setBackupResult('恢复确认已失效，请重新检查备份。', 'error'); return; }
  setBackupResult('正在备份当前世界并执行原子恢复…');
  try {
    const response = await fetch('/api/backups/restore', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({backup_id:pending.backup_id, world_id:pending.world_id, expected_sha256:pending.current_sha256, confirmed:true})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '备份恢复失败');
    backupData = null; activeWorldHash = null; mapData = null;
    await Promise.all([loadBackups(), scan()]);
    setBackupResult(`恢复完成 · 当前世界的恢复前快照：${data.safety_backup_path}`, 'ok');
  } catch (error) {
    setBackupResult(error.message, 'error');
  } finally {
    backupRestoreConfirm.checked = false;
    backupRestoreButton.disabled = true;
  }
});

document.querySelector('#reload-map').addEventListener('click', () => { mapData = null; loadWorldMap(); });
document.querySelector('#show-map-players').addEventListener('change', event => document.querySelector('#map-player-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#show-base-camps').addEventListener('change', event => document.querySelector('#base-camp-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#show-fast-travel').addEventListener('change', event => document.querySelector('#fast-travel-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#show-boss-towers').addEventListener('change', event => document.querySelector('#boss-tower-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#map-focus-query').addEventListener('input', renderMapFocusResults);
document.querySelector('#map-zoom-in').addEventListener('click', () => setMapZoom(mapView.zoom + 0.35));
document.querySelector('#map-zoom-out').addEventListener('click', () => setMapZoom(mapView.zoom - 0.35));
document.querySelector('#map-reset-view').addEventListener('click', resetMapView);
const mapStage = document.querySelector('#map-stage');
mapStage.addEventListener('wheel', event => {
  event.preventDefault();
  setMapZoom(mapView.zoom + (event.deltaY < 0 ? 0.25 : -0.25));
}, {passive:false});
mapStage.addEventListener('pointerdown', event => {
  if (event.button !== 0 || event.target.closest('.map-player-marker,.map-base-marker')) return;
  mapView.drag = {pointerId:event.pointerId, x:event.clientX, y:event.clientY, panX:mapView.panX, panY:mapView.panY};
  mapStage.setPointerCapture(event.pointerId);
  mapStage.classList.add('dragging');
});
mapStage.addEventListener('pointermove', event => {
  if (!mapView.drag || mapView.drag.pointerId !== event.pointerId) return;
  mapView.panX = mapView.drag.panX + event.clientX - mapView.drag.x;
  mapView.panY = mapView.drag.panY + event.clientY - mapView.drag.y;
  updateMapTransform();
});
function stopMapDrag(event) {
  if (!mapView.drag || mapView.drag.pointerId !== event.pointerId) return;
  mapView.drag = null;
  mapStage.classList.remove('dragging');
  if (mapStage.hasPointerCapture(event.pointerId)) mapStage.releasePointerCapture(event.pointerId);
}
mapStage.addEventListener('pointerup', stopMapDrag);
mapStage.addEventListener('pointercancel', stopMapDrag);

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
showView('saves');
scan();
loadItems();
loadPals();
loadSkills();
loadServerContext();
window.setInterval(refreshServerContextInBackground, SERVER_CONTEXT_REFRESH_MS);
document.addEventListener('visibilitychange', refreshServerContextInBackground);
