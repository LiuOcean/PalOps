const worldsNode = document.querySelector('#worlds');
const rootNode = document.querySelector('#root');
const template = document.querySelector('#world-template');
const itemTemplate = document.querySelector('#item-template');
const itemResults = document.querySelector('#item-results');
const itemSummary = document.querySelector('#item-summary');
const itemQuery = document.querySelector('#item-query');
const itemMore = document.querySelector('#item-more');
const itemCategories = document.querySelector('#item-categories');
const palResults = document.querySelector('#pal-results');
const palSummary = document.querySelector('#pal-summary');
const palQuery = document.querySelector('#pal-query');
const palMore = document.querySelector('#pal-more');
const skillResults = document.querySelector('#skill-results');
const skillSummary = document.querySelector('#skill-summary');
const skillQuery = document.querySelector('#skill-query');
const skillMore = document.querySelector('#skill-more');
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
const worldSearchQuery = document.querySelector('#world-search-query');
const worldSearchSummary = document.querySelector('#world-search-summary');
const worldSearchResults = document.querySelector('#world-search-results');
const worldSearchDetail = document.querySelector('#world-search-detail');
let activeWorld = null;
let activeWorldHash = null;
let loadedUsers = [];
let selectedUserId = null;
let onlinePlayers = [];
let loadedContainers = [];
let selectedContainerId = null;
let loadedGuilds = [];
let selectedGuildId = null;
let loadedSearchResults = [];
let selectedSearchKey = null;
let discoveredWorlds = [];
let mapData = null;
let selectedMapPlayerId = null;
let selectedMapBaseId = null;
let mapRequest = null;
const mapView = {zoom: 1, panX: 0, panY: 0, drag: null};
const MAP_MAX_DISPLAY_ZOOM = 8;
let mapTileFrame = null;
let serverConfig = null;
let backupData = null;
let selectedBackupId = null;
let pendingBackupRestore = null;
let pendingBackupDelete = null;
let restartConfirmationToken = null;
const SERVER_CONTEXT_REFRESH_MS = 15_000;
const CHAT_REFRESH_MS = 5_000;
const CHAT_BACKGROUND_REFRESH_MS = 30_000;
const SIDEBAR_STORAGE_KEY = 'paledit.sidebar.collapsed';
const OWNER_PLAYER_UID = '00000000-0000-0000-0000-000000000000';
const CATALOG_PAGE_SIZE = 100;
const catalogStates = {
  items: {query:'', offset:0, matchCount:0, loading:false, requestId:0, categories:new Set()},
  pals: {query:'', offset:0, matchCount:0, loading:false, requestId:0},
  skills: {query:'', offset:0, matchCount:0, loading:false, requestId:0},
};
let serverContextRequest = null;
let chatRequest = null;
let chatData = null;
let serverHistory = null;
let historyHours = 24;
let historyRequest = null;
let historyRequestHours = null;
const ROUTES = {
  overview: {page:'overview', root:'overview'},
  'world/search': {page:'saves', root:'world', resource:'search'},
  'world/containers': {page:'saves', root:'world', resource:'containers'},
  'world/players': {page:'saves', root:'world', resource:'users'},
  'world/guilds': {page:'saves', root:'world', resource:'guilds'},
  'world/backups': {page:'backups', root:'world'},
  map: {page:'map', root:'map'},
  'manage/players': {page:'players', root:'manage'},
  'manage/chat': {page:'chat', root:'manage'},
  'manage/rules': {page:'config', root:'manage'},
  'manage/operations': {page:'operations', root:'manage'},
  'catalog/items': {page:'data', root:'catalog', catalog:'items'},
  'catalog/pals': {page:'data', root:'catalog', catalog:'pals'},
  'catalog/skills': {page:'data', root:'catalog', catalog:'skills'},
};
const LEGACY_ROUTES = {
  overview:'overview', saves:'world/containers', backups:'world/backups', map:'map',
  players:'manage/players', config:'manage/rules', operations:'manage/operations', data:'catalog/items',
};

function playersFromResponse(payload) {
  return Array.isArray(payload?.players) ? payload.players : [];
}

function currentRoute() {
  const route = location.hash.replace(/^#\/?/, '');
  return ROUTES[route] ? route : 'world/containers';
}

function setSidebarCollapsed(collapsed, {persist = true} = {}) {
  const frame = document.querySelector('.app-frame');
  const toggle = document.querySelector('#sidebar-toggle');
  frame.classList.toggle('sidebar-collapsed', collapsed);
  toggle.setAttribute('aria-expanded', String(!collapsed));
  toggle.setAttribute('aria-label', collapsed ? '展开菜单栏' : '收起菜单栏');
  toggle.title = collapsed ? '展开菜单栏' : '收起菜单栏';
  toggle.querySelector('i').className = `ph ${collapsed ? 'ph-caret-right' : 'ph-caret-left'}`;
  if (persist) {
    try { localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? 'true' : 'false'); } catch (_) { /* storage may be unavailable */ }
  }
}

function initSidebar() {
  let collapsed = false;
  try { collapsed = localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true'; } catch (_) { /* use expanded default */ }
  setSidebarCollapsed(collapsed, {persist:false});
  document.querySelector('#sidebar-toggle').addEventListener('click', () => {
    setSidebarCollapsed(!document.querySelector('.app-frame').classList.contains('sidebar-collapsed'));
  });
}

function navigate(route) {
  const target = ROUTES[route] ? route : (LEGACY_ROUTES[route] || 'world/containers');
  if (currentRoute() === target && location.hash) applyRoute(target);
  else location.hash = `#/${target}`;
}

function applyRoute(route = currentRoute()) {
  const state = ROUTES[route];
  document.querySelectorAll('[data-page]').forEach(page => page.classList.toggle('hidden', page.dataset.page !== state.page));
  document.querySelectorAll('[data-nav-root]').forEach(button => {
    const active = button.dataset.navRoot === state.root;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.section-nav [data-route]').forEach(button => {
    const active = button.dataset.route === route;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
  if (state.resource) showResourceTab(state.resource, {fromRoute:true});
  if (state.catalog) document.querySelectorAll('[data-catalog-pane]').forEach(pane => pane.classList.toggle('hidden', pane.dataset.catalogPane !== state.catalog));
  document.querySelector('.world-workspace')?.classList.remove('mobile-detail-open');
  document.querySelector('.app-shell').scrollTo({top:0});
  if (state.page === 'config' && !serverConfig) loadServerConfig();
  if (state.page === 'backups' && !backupData) loadBackups();
  if (state.page === 'map') loadWorldMap();
  if (state.page === 'chat') void loadChat();
}

function showView(name) {
  navigate(LEGACY_ROUTES[name] || name);
}

function showModalWithFocus(dialog, opener = document.activeElement) {
  dialog.showModal();
  dialog.addEventListener('close', () => opener?.focus(), {once:true});
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
  let currentDay = '';
  for (const backup of rows) {
    const day = new Date(backup.created_at).toLocaleDateString('zh-CN', {year:'numeric', month:'long', day:'numeric'});
    if (day !== currentDay) {
      const heading = document.createElement('h3'); heading.className = 'backup-group-label'; heading.textContent = day;
      root.append(heading); currentDay = day;
    }
    const article = document.createElement('button'); article.type = 'button'; article.className = 'backup-row';
    article.dataset.backupId = backup.backup_id;
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
    const files = document.createElement('small'); files.textContent = `${backup.file_count.toLocaleString()} 个文件${backup.has_level_save ? ' · 含 Level.sav' : ''}${backup.protected ? ' · 24 小时保护中' : ''}`;
    stats.append(size, files);
    article.append(icon, copy, sourceBadge, stats);
    article.classList.toggle('active', backup.backup_id === selectedBackupId);
    article.setAttribute('aria-selected', String(backup.backup_id === selectedBackupId));
    article.addEventListener('click', () => selectBackup(backup.backup_id));
    root.append(article);
  }
  document.querySelector('#backup-summary').textContent = `显示 ${rows.length} / ${backupData?.count || 0} 份备份 · 固定目录只读扫描`;
  if (!rows.length) {
    root.innerHTML = '<div class="empty">没有匹配的本地备份</div>';
    renderBackupDetail(null);
  } else {
    if (!rows.some(backup => backup.backup_id === selectedBackupId)) selectedBackupId = rows[0].backup_id;
    selectBackup(selectedBackupId);
  }
}

function selectBackup(backupId, {preserveList = false} = {}) {
  selectedBackupId = backupId;
  if (!preserveList) document.querySelectorAll('.backup-row').forEach(row => {
    const active = row.dataset.backupId === backupId;
    row.classList.toggle('active', active); row.setAttribute('aria-selected', String(active));
  });
  renderBackupDetail((backupData?.backups || []).find(backup => backup.backup_id === backupId));
}

function renderBackupDetail(backup) {
  const root = document.querySelector('#backup-detail');
  root.innerHTML = '';
  if (!backup) {
    root.innerHTML = '<div class="detail-empty"><i class="ph ph-floppy-disk-back" aria-hidden="true"></i><strong>选择一份备份</strong><p>恢复、删除和技术路径集中显示在这里。</p></div>';
    return;
  }
  const article = document.createElement('article'); article.className = 'backup-detail-card';
  article.innerHTML = '<header><span class="backup-icon"><i class="ph ph-archive-box" aria-hidden="true"></i></span><div><p class="eyebrow">选中备份</p><h2></h2><span class="backup-source"></span></div></header><dl class="backup-detail-facts"></dl>';
  article.querySelector('.backup-icon').classList.add(backup.source);
  article.querySelector('h2').textContent = backup.name;
  const source = article.querySelector('.backup-source'); source.classList.add(backup.source); source.textContent = backup.source_label;
  const facts = article.querySelector('dl');
  const values = [
    ['创建时间', new Date(backup.created_at).toLocaleString('zh-CN', {hour12:false})],
    ['占用空间', `${formatBytes(backup.size_bytes)} · ${backup.file_count.toLocaleString()} 个文件`],
    ['世界', backup.world_ids?.join(', ') || '未识别世界'],
    ['安全状态', backup.protected ? `保护至 ${new Date(backup.protected_until).toLocaleString('zh-CN', {hour12:false})}` : '可按确认链操作'],
  ];
  for (const [label, value] of values) {
    const row = document.createElement('div'); const dt = document.createElement('dt'); const dd = document.createElement('dd');
    dt.textContent = label; dd.textContent = value; row.append(dt, dd); facts.append(row);
  }
  const path = document.createElement('details'); path.className = 'technical-info';
  path.innerHTML = '<summary>查看技术路径</summary><code></code>'; path.querySelector('code').textContent = backup.path;
  const actions = document.createElement('div'); actions.className = 'backup-detail-actions';
  let worldSelect = null;
  if ((backup.world_ids || []).length > 1) {
    worldSelect = document.createElement('select'); worldSelect.setAttribute('aria-label', `${backup.name} 恢复世界`);
    for (const worldId of backup.world_ids) { const option = document.createElement('option'); option.value = worldId; option.textContent = worldId; worldSelect.append(option); }
    actions.append(worldSelect);
  }
  const restore = document.createElement('button'); restore.className = 'backup-restore primary'; restore.innerHTML = '<i class="ph ph-clock-counter-clockwise" aria-hidden="true"></i> 检查并恢复';
  restore.disabled = !backup.has_level_save || !(backup.world_ids || []).length;
  restore.addEventListener('click', () => beginBackupRestore(backup, worldSelect?.value || backup.world_ids[0], restore));
  const remove = document.createElement('button'); remove.className = 'backup-delete danger'; remove.innerHTML = '<i class="ph ph-trash" aria-hidden="true"></i> 永久删除';
  remove.disabled = !backup.deletable; remove.title = backup.protected ? '安全快照仍在保护期内' : '永久删除这份本地备份';
  remove.addEventListener('click', () => beginBackupDelete(backup));
  actions.append(restore, remove); article.append(path, actions); root.append(article);
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
    document.querySelector('#backup-review').textContent = `${data.retention.review_count.toLocaleString()} 份`;
    const latest = data.backups?.[0];
    document.querySelector('#overview-last-backup').textContent = latest ? new Date(latest.created_at).toLocaleString('zh-CN', {hour12:false}) : '尚无备份';
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
    showModalWithFocus(document.querySelector('#backup-restore-dialog'), button);
    setBackupResult('备份检查通过，请在弹窗中完成第二次确认。');
  } catch (error) {
    pendingBackupRestore = null;
    setBackupResult(error.message, 'error');
  } finally { button.disabled = false; }
}

function beginBackupDelete(backup) {
  pendingBackupDelete = backup;
  document.querySelector('#delete-backup-name').textContent = backup.name;
  document.querySelector('#delete-backup-source').textContent = backup.source_label;
  document.querySelector('#delete-backup-world').textContent = backup.world_ids?.join(', ') || '未识别世界';
  document.querySelector('#delete-backup-size').textContent = formatBytes(backup.size_bytes);
  const checkbox = document.querySelector('#backup-delete-confirm'); checkbox.checked = false;
  document.querySelector('#confirm-backup-delete').disabled = true;
  showModalWithFocus(document.querySelector('#backup-delete-dialog'));
}

function showResourceTab(name, {fromRoute = false} = {}) {
  if (!fromRoute) {
    const route = {search:'world/search', containers:'world/containers', users:'world/players', guilds:'world/guilds'}[name];
    if (route && currentRoute() !== route) { navigate(route); return; }
  }
  document.querySelectorAll('[data-resource-tab]').forEach(button => {
    const active = button.dataset.resourceTab === name;
    button.setAttribute('role', 'tab');
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
  document.querySelectorAll('[data-resource-pane]').forEach(pane => pane.classList.toggle('hidden', pane.dataset.resourcePane !== name));
  const resources = {search: loadedSearchResults, containers: loadedContainers, users: loadedUsers, guilds: loadedGuilds};
  const hasData = resources[name]?.length || 0;
  document.querySelector('#resource-empty').classList.toggle('hidden', name === 'search' || Boolean(hasData));
  worldSearchDetail.classList.toggle('hidden', name !== 'search');
  document.querySelector('#container-detail').classList.toggle('hidden', name !== 'containers');
  document.querySelector('#player-detail').classList.toggle('hidden', name !== 'users');
  document.querySelector('#guild-detail').classList.toggle('hidden', name !== 'guilds');
  if (name === 'search' && hasData) selectWorldSearchResult(selectedSearchKey || searchResultKey(loadedSearchResults[0]));
  if (name === 'containers' && hasData) selectContainer(selectedContainerId || loadedContainers[0].container_id);
  if (name === 'users' && hasData) selectUser(selectedUserId || loadedUsers[0].player_uid);
  if (name === 'guilds' && hasData) selectGuild(selectedGuildId || loadedGuilds[0].guild_id);
}

function openMobileWorldDetail() {
  document.querySelector('.world-workspace')?.classList.add('mobile-detail-open');
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
  document.querySelector('#save-config').textContent = count ? `备份并保存 · ${count} 项` : '备份并保存';
  if (count) setConfigResult(`${count} 项待保存。保存后需重启服务器才会应用。`);
}

function configExperienceGroup(setting) {
  const key = setting.key;
  if (['PUID','PGID','TZ','ARM64_DEVICE','MULTITHREADING','UPDATE_ON_BOOT','USE_DEPOT_DOWNLOADER'].includes(key)) return '高级';
  if (key.includes('PORT') || key.includes('RCON') || key.includes('REST_API') || ['SERVER_NAME','SERVER_DESCRIPTION','COMMUNITY','CROSSPLAY_PLATFORMS','PLAYERS'].includes(key)) return '连接';
  if (key.includes('BACKUP') || key.includes('UPDATE') || key.includes('DEPOT') || key.includes('DIRTY_INTERVAL')) return '备份维护';
  if (key.includes('BASE_CAMP') || key.includes('GUILD') || key.includes('PALBOX') || key.includes('BUILD_OBJECT')) return '世界与据点';
  return '游戏体验';
}

function renderServerConfig() {
  const root = document.querySelector('#config-settings');
  const query = document.querySelector('#config-query').value.trim().toLocaleLowerCase('zh-CN');
  root.innerHTML = '';
  const categories = new Map(['游戏体验','世界与据点','备份维护','连接','高级'].map(name => [name, []]));
  for (const setting of serverConfig.settings) {
    if (query && !`${setting.label} ${setting.description} ${setting.key} ${setting.value} ${setting.category}`.toLocaleLowerCase('zh-CN').includes(query)) continue;
    categories.get(configExperienceGroup(setting)).push(setting);
  }
  for (const [category, settings] of categories) {
    if (!settings.length) continue;
    const group = document.createElement('details'); group.className = 'config-group'; group.open = category !== '高级' || Boolean(query);
    const heading = document.createElement('summary'); heading.className = 'config-group-title'; heading.innerHTML = `<span>${category}</span><small>${settings.length} 项</small>`;
    const body = document.createElement('div'); body.className = 'config-group-body'; group.append(heading, body); root.append(group);
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
      row.append(key, control, state); body.append(row);
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
  document.querySelectorAll('[data-operation-tab]').forEach(button => {
    const active = button.dataset.operationTab === name;
    button.setAttribute('role', 'tab'); button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active));
  });
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

function historyValue(value, suffix = '', digits = 0) {
  return Number.isFinite(value) ? `${Number(value).toFixed(digits)}${suffix}` : '—';
}

function healthTone(score) {
  if (!Number.isFinite(score) || score < 45) return 'critical';
  if (score < 75) return 'warning';
  return 'healthy';
}

function chartTooltip(canvas) {
  const frame = canvas.parentElement;
  let tooltip = frame.querySelector('.chart-tooltip');
  if (tooltip) return tooltip;
  tooltip = document.createElement('div');
  tooltip.className = 'chart-tooltip';
  tooltip.setAttribute('aria-hidden', 'true');
  tooltip.append(document.createElement('small'), document.createElement('strong'));
  frame.appendChild(tooltip);
  return tooltip;
}

function chartAxisTime(timestamp, hours) {
  const date = new Date(timestamp * 1000);
  if (hours <= 1) return date.toLocaleTimeString('zh-CN', {hour:'2-digit', minute:'2-digit', hour12:false});
  if (hours <= 24) return date.toLocaleString('zh-CN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false});
  return date.toLocaleDateString('zh-CN', {month:'2-digit', day:'2-digit'});
}

function renderHistoryChart(canvasId, samples, key, {
  color = '#a8ff55', fill = '#a8ff5512', fixedMax = null, label = key, unit = '', digits = 0,
  rangeStart = null, rangeEnd = null, rangeHours = 24,
} = {}) {
  const canvas = document.querySelector(canvasId);
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  const context = canvas.getContext('2d');
  context.scale(ratio, ratio);
  const width = rect.width; const height = rect.height;
  const pad = {top:12, right:12, bottom:22, left:38};
  const points = samples
    .map((row, index) => ({sampleIndex:index, timestamp:Number(row.sampled_at), value:row[key] == null ? Number.NaN : Number(row[key])}))
    .filter(point => Number.isFinite(point.timestamp) && Number.isFinite(point.value));
  const values = points.map(point => point.value);
  const min = fixedMax === null && values.length ? Math.min(...values) : 0;
  const max = fixedMax === null && values.length ? Math.max(...values) : (fixedMax ?? 1);
  const spread = Math.max(max - min, 1);
  const firstTimestamp = Number(rangeStart) || Number(samples[0]?.sampled_at) || 0;
  const lastTimestamp = Number(rangeEnd) || Number(samples[samples.length - 1]?.sampled_at) || firstTimestamp + 1;
  const timeSpread = Math.max(lastTimestamp - firstTimestamp, 1);
  const xAt = timestamp => pad.left + Math.max(0, Math.min((timestamp - firstTimestamp) / timeSpread, 1)) * (width - pad.left - pad.right);
  const yAt = value => pad.top + (1 - (value - min) / spread) * (height - pad.top - pad.bottom);
  const draw = (hoveredPoint = null) => {
    context.clearRect(0, 0, width, height);
    context.strokeStyle = '#ffffff0d'; context.lineWidth = 1;
    context.fillStyle = '#657269'; context.font = '8px ui-monospace, monospace';
    for (let step = 0; step <= 3; step += 1) {
      const y = pad.top + (height - pad.top - pad.bottom) * step / 3;
      context.beginPath(); context.moveTo(pad.left, y); context.lineTo(width - pad.right, y); context.stroke();
    }
    const firstTime = chartAxisTime(firstTimestamp, rangeHours);
    const lastTime = chartAxisTime(lastTimestamp, rangeHours);
    context.fillText(firstTime, pad.left, height - 5); context.textAlign = 'right'; context.fillText(lastTime, width - pad.right, height - 5); context.textAlign = 'left';
    if (points.length < 2) return;
    context.fillText(max.toFixed(0), 4, pad.top + 4); context.fillText(min.toFixed(0), 4, height - pad.bottom + 3);
    context.beginPath();
    points.forEach((point, index) => { const x = xAt(point.timestamp); const y = yAt(point.value); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y); });
    const last = points[points.length - 1];
    context.lineTo(xAt(last.timestamp), height - pad.bottom); context.lineTo(xAt(points[0].timestamp), height - pad.bottom); context.closePath();
    context.fillStyle = fill; context.fill();
    context.beginPath();
    points.forEach((point, index) => { const x = xAt(point.timestamp); const y = yAt(point.value); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y); });
    context.strokeStyle = color; context.lineWidth = 1.7; context.lineJoin = 'round'; context.stroke();
    if (!hoveredPoint) return;
    const hoverX = xAt(hoveredPoint.timestamp); const hoverY = yAt(hoveredPoint.value);
    context.beginPath(); context.moveTo(hoverX, pad.top); context.lineTo(hoverX, height - pad.bottom);
    context.strokeStyle = '#ffffff35'; context.lineWidth = 1; context.stroke();
    context.beginPath(); context.arc(hoverX, hoverY, 4, 0, Math.PI * 2);
    context.fillStyle = '#0d1712'; context.fill(); context.strokeStyle = color; context.lineWidth = 2; context.stroke();
  };
  draw();

  const tooltip = chartTooltip(canvas);
  tooltip.classList.remove('visible');
  tooltip.setAttribute('aria-hidden', 'true');
  canvas.onpointermove = event => {
    if (points.length < 2) return;
    const bounds = canvas.getBoundingClientRect();
    const pointerX = Math.max(pad.left, Math.min(event.clientX - bounds.left, width - pad.right));
    const targetTimestamp = firstTimestamp + (pointerX - pad.left) / (width - pad.left - pad.right) * timeSpread;
    const point = points.reduce((nearest, candidate) => (
      Math.abs(candidate.timestamp - targetTimestamp) < Math.abs(nearest.timestamp - targetTimestamp) ? candidate : nearest
    ));
    const sample = samples[point.sampleIndex];
    draw(point);
    tooltip.querySelector('small').textContent = new Date(sample.sampled_at * 1000).toLocaleString('zh-CN', {hour12:false});
    tooltip.querySelector('strong').textContent = `${label} ${point.value.toFixed(digits)}${unit}`;
    tooltip.style.left = `${Math.max(76, Math.min(xAt(point.timestamp), width - 76))}px`;
    tooltip.style.top = `${Math.max(52, yAt(point.value))}px`;
    tooltip.classList.add('visible');
    tooltip.setAttribute('aria-hidden', 'false');
  };
  canvas.onpointerleave = () => {
    draw();
    tooltip.classList.remove('visible');
    tooltip.setAttribute('aria-hidden', 'true');
  };
}

function renderServerHistory() {
  if (!serverHistory) return;
  const samples = serverHistory.samples || [];
  const latest = serverHistory.latest || {};
  const summary = serverHistory.summary || {};
  const score = Number(latest.health_score);
  const ring = document.querySelector('#health-score-ring');
  ring.style.setProperty('--health-score', Number.isFinite(score) ? score : 0);
  ring.dataset.tone = healthTone(score);
  document.querySelector('#health-score').textContent = Number.isFinite(score) ? score.toFixed(0) : '—';
  document.querySelector('#health-latency').textContent = historyValue(latest.server_latency_ms, ' ms', 0);
  document.querySelector('#health-availability').textContent = historyValue(summary.availability_percent, '%', 1);
  document.querySelector('#health-incidents').textContent = Number.isFinite(summary.incident_count) ? String(summary.incident_count) : '—';
  document.querySelector('#health-sample-state').textContent = latest.error
    ? `指标采集异常 · ${latest.error}`
    : serverHistory.sample_count ? `${serverHistory.sample_count} 个样本 · ${historyHours === 168 ? '近 7 天' : `${historyHours} 小时`}` : '等待首个历史样本';
  document.querySelector('#history-latency-current').textContent = historyValue(latest.server_latency_ms, ' ms', 0);
  document.querySelector('#history-latency-summary').textContent = `平均 ${historyValue(summary.average_server_latency_ms, ' ms', 0)} · P95 ${historyValue(summary.p95_server_latency_ms, ' ms', 0)}`;
  document.querySelector('#history-fps-current').textContent = historyValue(latest.server_fps, '', 0);
  document.querySelector('#history-fps-summary').textContent = `平均 ${historyValue(summary.average_fps, '', 1)}`;
  document.querySelector('#history-health-current').textContent = Number.isFinite(score) ? score.toFixed(0) : '—';
  document.querySelector('#history-players-current').textContent = historyValue(latest.current_players, ' 人', 0);
  document.querySelector('#history-sample-count').textContent = `${serverHistory.sample_count} 个样本`;
  document.querySelector('#history-updated').textContent = latest.sampled_at ? `最近采样 ${new Date(latest.sampled_at * 1000).toLocaleString('zh-CN', {hour12:false})}` : '等待历史数据';
  document.querySelector('#latency-chart-empty').classList.toggle('hidden', samples.length >= 2);
  const rangeHours = Number(serverHistory.hours) || historyHours;
  const rangeEnd = Number(serverHistory.range_end) || Math.floor(Date.now() / 1000);
  const chartRange = {
    rangeStart:Number(serverHistory.range_start) || rangeEnd - rangeHours * 60 * 60,
    rangeEnd,
    rangeHours,
  };
  renderHistoryChart('#latency-chart', samples, 'server_latency_ms', {...chartRange, color:'#6ccfff', fill:'#6ccfff14', label:'服务器延迟', unit:' ms', digits:1});
  renderHistoryChart('#fps-chart', samples, 'server_fps', {...chartRange, color:'#a8ff55', fill:'#a8ff5512', label:'服务器 FPS', digits:1});
  renderHistoryChart('#health-chart', samples, 'health_score', {...chartRange, color:'#e8b75b', fill:'#e8b75b12', fixedMax:100, label:'健康分', digits:0});
  renderHistoryChart('#players-chart', samples, 'current_players', {...chartRange, color:'#ba8cff', fill:'#ba8cff12', label:'在线玩家', unit:' 人', digits:0});
}

async function loadServerHistory({showLoading = true} = {}) {
  const requestedHours = historyHours;
  if (historyRequest && historyRequestHours === requestedHours) return historyRequest;
  if (showLoading) document.querySelector('#history-updated').textContent = '正在读取本地历史…';
  const request = (async () => {
    try {
      const response = await fetch(`/api/server/history?hours=${requestedHours}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '服务器历史读取失败');
      if (historyHours !== requestedHours) return;
      serverHistory = data;
      renderServerHistory();
    } catch (error) {
      if (historyHours === requestedHours) document.querySelector('#history-updated').textContent = error.message;
    } finally {
      if (historyRequest === request) {
        historyRequest = null;
        historyRequestHours = null;
      }
    }
  })();
  historyRequest = request;
  historyRequestHours = requestedHours;
  return request;
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
      document.querySelector('#overview-attention').textContent = status.online ? (onlinePlayers.length ? `${onlinePlayers.length} 名玩家在线` : '无需介入') : '服务器离线';
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
      document.querySelector('#overview-attention').textContent = '管理链路不可用';
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
  if (!document.hidden) {
    void loadServerContext({showLoading: false});
    if (currentRoute() === 'overview') void loadServerHistory({showLoading: false});
  }
}

function renderChat() {
  const root = document.querySelector('#chat-messages');
  const status = document.querySelector('#chat-status');
  const storage = document.querySelector('#chat-storage');
  if (!root || !chatData) return;
  const keepAtBottom = root.scrollHeight - root.scrollTop - root.clientHeight < 80;
  const query = document.querySelector('#chat-query').value.trim().toLocaleLowerCase('zh-CN');
  const rows = (chatData.messages || []).filter(row => !query || `${row.player_name} ${row.message}`.toLocaleLowerCase('zh-CN').includes(query));
  root.innerHTML = '';
  if (!rows.length) {
    const empty = document.createElement('div'); empty.className = 'empty';
    empty.textContent = query ? '没有匹配的聊天记录' : '尚未保存聊天记录';
    root.append(empty);
  } else {
    let previous = null;
    for (const row of rows) {
      const day = row.game_at.slice(0, 10);
      if (previous?.day !== day) {
        const separator = document.createElement('div'); separator.className = 'chat-day';
        const date = new Date(`${day}T00:00:00`);
        separator.textContent = date.toLocaleDateString('zh-CN', {month:'long', day:'numeric', weekday:'short'});
        root.append(separator);
      }
      const grouped = previous?.day === day && previous?.player_name === row.player_name;
      const article = document.createElement('article'); article.className = `chat-message${grouped ? ' grouped' : ''}`;
      let hue = 0;
      for (const character of Array.from(row.player_name)) hue = (hue * 31 + character.codePointAt(0)) % 360;
      article.style.setProperty('--speaker-hue', String(hue));
      const avatar = document.createElement('span'); avatar.className = 'chat-avatar';
      avatar.textContent = Array.from(row.player_name || '?')[0] || '?';
      const body = document.createElement('div'); body.className = 'chat-message-body';
      const header = document.createElement('header');
      const player = document.createElement('strong'); player.textContent = row.player_name;
      const time = document.createElement('time'); time.dateTime = row.logged_at; time.textContent = row.game_at.slice(11, 16);
      const message = document.createElement('p'); message.textContent = row.message;
      header.append(player, time); body.append(header, message); article.append(avatar, body); root.append(article);
      previous = {...row, day};
    }
    if (keepAtBottom) root.scrollTop = root.scrollHeight;
  }
  const syncState = chatData.warning ? `远端同步失败，正在显示本地记录：${chatData.warning}` : `已保存 ${chatData.stored_count.toLocaleString()} 条${chatData.imported ? ` · 本次新增 ${chatData.imported} 条` : ' · 已是最新'}`;
  status.textContent = syncState;
  status.classList.toggle('error', Boolean(chatData.warning));
  document.querySelector('#chat-count').textContent = `${chatData.stored_count.toLocaleString()} 条已归档`;
  storage.innerHTML = '<i class="ph ph-database" aria-hidden="true"></i> SQLite 本地归档';
  storage.title = chatData.database_path;
}

function loadChat({showLoading = true} = {}) {
  if (chatRequest) return chatRequest;
  chatRequest = (async () => {
    const status = document.querySelector('#chat-status');
    if (showLoading && status) { status.textContent = '正在读取本地记录并同步服务器…'; status.classList.remove('error'); }
    try {
      const response = await fetch('/api/server/chat?limit=500');
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '聊天记录读取失败');
      chatData = data;
      renderChat();
    } catch (error) {
      if (status) { status.textContent = error.message; status.classList.add('error'); }
    } finally {
      chatRequest = null;
    }
  })();
  return chatRequest;
}

function refreshChatInBackground() {
  if (!document.hidden && currentRoute() === 'manage/chat') void loadChat({showLoading: false});
}

function persistChatInBackground() {
  if (!document.hidden && currentRoute() !== 'manage/chat') void loadChat({showLoading: false});
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
    const latestWorld = [...data.worlds].sort((a, b) => b.level.modified_at - a.level.modified_at)[0];
    document.querySelector('#overview-save-freshness').textContent = latestWorld ? new Date(latestWorld.level.modified_at * 1000).toLocaleString('zh-CN', {hour12:false}) : '未发现存档';
    document.querySelector('#overview-parser-state').textContent = latestWorld?.level.magic === 'PlM' ? 'Palworld 1.0 安全模式' : '等待兼容诊断';
    worldsNode.innerHTML = '';
    for (const world of data.worlds) worldsNode.append(renderWorld(world));
    if (!data.worlds.length) worldsNode.innerHTML = '<div class="empty">没有发现 Level.sav</div>';
    if (
      data.worlds.length === 1
      && currentRoute().startsWith('world/')
      && currentRoute() !== 'world/backups'
      && !loadedContainers.length
    ) worldsNode.querySelector('.inspect')?.click();
    if (!document.querySelector('[data-page="map"]').classList.contains('hidden')) await ensureMapSaveData();
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
      const response = await fetch(`/api/world/snapshot?path=${encodeURIComponent(world.path)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '诊断失败');
      result.className = 'result ok';
      result.textContent = `兼容 · ${data.summary.character_count} 个角色实体 · ${data.warnings.length} 项安全提示`;
      button.textContent = '重新诊断';
      activeWorld = world.path;
      mapData = null;
      hydrateWorldSnapshot(data);
      document.querySelector('#overview-parser-state').textContent = `${Object.values(data.capabilities).filter(Boolean).length} 项能力可用`;
      document.querySelector('#overview-attention').textContent = data.warnings.length ? `${data.warnings.length} 项解析提示` : '无需介入';
      document.querySelector('#resource-empty').classList.add('hidden');
      const route = currentRoute();
      if (["world/search", "world/containers", "world/players", "world/guilds"].includes(route)) applyRoute(route);
      else navigate("world/containers");
    } catch (error) {
      result.className = 'result error'; result.textContent = error.message;
    } finally { button.disabled = false; }
  });
  return node;
}

function renderUserNavigation() {
  userPanel.classList.remove('hidden');
  userSummary.textContent = `${loadedUsers.length} 个用户 · 所有字段以 Palworld 原始类型读写`;
  usersNode.innerHTML = '';
  for (const user of loadedUsers) {
    const button = document.createElement('button');
    const name = document.createElement('span'); name.textContent = user.nickname || '未命名用户';
    const meta = document.createElement('small'); meta.textContent = `Lv.${user.level} · ${user.pal_count} 只帕鲁`;
    if (user.player_uid.toLowerCase() === OWNER_PLAYER_UID) meta.textContent += ' · 我的角色';
    button.append(name, meta);
    button.classList.toggle('active', user.player_uid === selectedUserId);
    button.addEventListener('click', () => selectUser(user.player_uid));
    usersNode.append(button);
  }
  if (!selectedUserId || !loadedUsers.some(user => user.player_uid === selectedUserId)) {
    selectedUserId = loadedUsers.find(user => user.player_uid.toLowerCase() === OWNER_PLAYER_UID)?.player_uid || loadedUsers[0]?.player_uid;
  }
}

function hydrateWorldSnapshot(data) {
  activeWorldHash = data.level_sha256;
  loadedContainers = data.containers || [];
  loadedUsers = data.users || [];
  loadedGuilds = data.guilds || [];
  loadedSearchResults = [];
  selectedSearchKey = null;
  containerPanel.classList.remove('hidden'); guildPanel.classList.remove('hidden');
  containerSummary.textContent = `${loadedContainers.length} 个物品容器 · ${loadedContainers.filter(row => row.label).length} 个带标签 · 只读展示`;
  guildSummary.textContent = `${loadedGuilds.length} 个公会 · ${loadedGuilds.reduce((count, row) => count + row.base_count, 0)} 个据点 · 只读展示`;
  if (!selectedGuildId || !loadedGuilds.some(guild => guild.guild_id === selectedGuildId)) {
    selectedGuildId = loadedGuilds.find(guild => guild.players.some(player => player.player_uid.toLowerCase() === OWNER_PLAYER_UID))?.guild_id || loadedGuilds[0]?.guild_id;
  }
  renderUserNavigation(); renderContainers(); renderGuilds();
  if (worldSearchQuery.value.trim()) loadWorldSearch(worldSearchQuery.value);
}

function searchResultKey(result) {
  const identity = result.kind === 'item' ? result.item_id : result.instance_id;
  return `${result.kind}:${identity}:${result.container_id || ''}:${result.slot_index}`;
}

async function loadWorldSearch(query = worldSearchQuery.value) {
  const normalized = query.trim();
  if (!normalized) {
    loadedSearchResults = [];
    selectedSearchKey = null;
    worldSearchSummary.textContent = '搜索所有玩家背包、储物箱和帕鲁容器';
    worldSearchResults.innerHTML = '<div class="search-intro"><i class="ph ph-binoculars" aria-hidden="true"></i><strong>一次找遍整个世界</strong><p>结果会标明玩家、背包分类、储物箱、帕鲁终端或队伍位置。</p></div>';
    worldSearchDetail.innerHTML = '<div class="detail-empty"><i class="ph ph-magnifying-glass" aria-hidden="true"></i><strong>选择一条搜索结果</strong><p>这里会显示精确位置、数量或帕鲁资料。</p></div>';
    return;
  }
  if (!activeWorld) {
    worldSearchResults.innerHTML = '<div class="empty">请先打开一个世界存档</div>';
    return;
  }
  const needle = normalized.toLocaleLowerCase('zh-CN');
  const matches = (...values) => values.filter(Boolean).join(' ').toLocaleLowerCase('zh-CN').includes(needle);
  const results = [];
  for (const user of loadedUsers) {
    const ownerName = user.nickname || '未命名玩家';
    for (const [inventoryName, slots] of Object.entries(user.inventories || {})) {
      for (const slot of slots) {
        if (slot.item_id === 'None' || Number(slot.count) <= 0 || !matches(slot.name_zh, slot.item_id, slot.category, slot.description)) continue;
        results.push({...slot, kind:'item', location_kind:'player_inventory', location_label:`${ownerName} · ${inventoryName}`, owner_name:ownerName, owner_player_uid:user.player_uid, inventory_name:inventoryName, container_id:user.inventory_container_ids?.[inventoryName] || ''});
      }
    }
    for (const pal of user.pals || []) {
      const skills = (pal.passive_skills || []).flatMap(skill => [skill.skill_id, skill.name_zh, skill.description]);
      if (!matches(pal.name_zh, pal.character_id, pal.nickname, ...skills)) continue;
      results.push({...pal, kind:'pal', location_kind:'player_pal', location_label:`${ownerName} · ${pal.location_type || '其他帕鲁容器'}`, owner_name:ownerName, owner_player_uid:user.player_uid});
    }
  }
  for (const container of loadedContainers) {
    const containerName = container.label || container.type_name || '未命名储物箱';
    for (const slot of container.slots || []) {
      if (slot.item_id === 'None' || Number(slot.count) <= 0 || !matches(slot.name_zh, slot.item_id, slot.category, slot.description)) continue;
      results.push({...slot, kind:'item', location_kind:'storage_container', location_label:containerName, container_id:container.container_id, container_type:container.type_name, object_id:container.object_id});
    }
  }
  results.sort((left, right) => `${left.name_zh} ${left.location_label} ${left.kind}`.localeCompare(`${right.name_zh} ${right.location_label} ${right.kind}`, 'zh-CN'));
  const itemCount = results.filter(result => result.kind === 'item').length;
  const palCount = results.length - itemCount;
  loadedSearchResults = results.slice(0, 500);
  worldSearchSummary.textContent = `${results.length} 个位置 · ${itemCount} 个道具堆 · ${palCount} 只帕鲁${results.length > 500 ? ' · 显示前 500 个' : ''}`;
  renderWorldSearchResults();
}

function renderWorldSearchResults() {
  worldSearchResults.innerHTML = '';
  for (const result of loadedSearchResults) {
    const key = searchResultKey(result);
    const row = document.createElement('button'); row.type = 'button'; row.className = 'resource-row world-search-row'; row.dataset.searchKey = key;
    row.classList.toggle('active', key === selectedSearchKey);
    const image = document.createElement('span'); image.className = 'search-result-image';
    if (result.icon_url) {
      const img = document.createElement('img'); img.src = result.icon_url; img.alt = ''; img.loading = 'lazy'; image.append(img);
    } else image.innerHTML = `<i class="ph ${result.kind === 'pal' ? 'ph-paw-print' : 'ph-package'}" aria-hidden="true"></i>`;
    const copy = document.createElement('span'); copy.className = 'resource-row-copy';
    const name = document.createElement('strong'); name.textContent = result.nickname ? `${result.name_zh} · ${result.nickname}` : result.name_zh;
    const location = document.createElement('small'); location.textContent = result.location_label;
    copy.append(name, location);
    const value = document.createElement('span'); value.className = 'search-result-value';
    value.textContent = result.kind === 'item' ? `× ${Number(result.count).toLocaleString()}` : `Lv.${result.level}`;
    row.append(image, copy, value);
    row.addEventListener('click', () => selectWorldSearchResult(key));
    worldSearchResults.append(row);
  }
  if (!loadedSearchResults.length) worldSearchResults.innerHTML = '<div class="empty">没有在玩家背包、储物箱或帕鲁容器中找到匹配内容</div>';
  if (loadedSearchResults.length && !loadedSearchResults.some(result => searchResultKey(result) === selectedSearchKey)) {
    selectWorldSearchResult(searchResultKey(loadedSearchResults[0]));
  }
}

function selectWorldSearchResult(key) {
  selectedSearchKey = key;
  const result = loadedSearchResults.find(row => searchResultKey(row) === key);
  [...worldSearchResults.querySelectorAll('.world-search-row')].forEach(row => row.classList.toggle('active', row.dataset.searchKey === key));
  worldSearchDetail.innerHTML = '';
  if (!result) return;
  const article = document.createElement('article'); article.className = 'search-result-detail';
  const head = document.createElement('header');
  const title = document.createElement('div');
  const eyebrow = document.createElement('p'); eyebrow.className = 'eyebrow'; eyebrow.textContent = result.kind === 'item' ? '道具位置' : '帕鲁位置';
  const name = document.createElement('h2'); name.textContent = result.nickname ? `${result.name_zh} · ${result.nickname}` : result.name_zh;
  const id = document.createElement('code'); id.textContent = result.kind === 'item' ? result.item_id : result.character_id;
  title.append(eyebrow, name, id);
  const image = document.createElement('span'); image.className = 'search-detail-image';
  if (result.icon_url) { const img = document.createElement('img'); img.src = result.icon_url; img.alt = ''; image.append(img); }
  else image.innerHTML = `<i class="ph ${result.kind === 'pal' ? 'ph-paw-print' : 'ph-package'}" aria-hidden="true"></i>`;
  head.append(title, image);
  const facts = document.createElement('dl'); facts.className = 'search-detail-facts';
  facts.append(detailRow('所在位置', result.location_label));
  facts.append(detailRow('槽位', Number(result.slot_index) >= 0 ? String(Number(result.slot_index) + 1) : '未知'));
  if (result.kind === 'item') {
    facts.append(detailRow('数量', Number(result.count).toLocaleString()), detailRow('分类', result.category || '其他'));
  } else {
    facts.append(detailRow('等级', `Lv.${result.level}`), detailRow('归属玩家', result.owner_name), detailRow('实例 ID', result.instance_id, true));
  }
  const actions = document.createElement('div'); actions.className = 'search-detail-actions';
  const open = document.createElement('button'); open.className = 'primary'; open.innerHTML = '<i class="ph ph-arrow-square-out" aria-hidden="true"></i> 打开所在位置';
  open.addEventListener('click', () => {
    if (result.location_kind === 'storage_container') { navigate('world/containers'); selectContainer(result.container_id); }
    else { navigate('world/players'); selectUser(result.owner_player_uid); }
  });
  actions.append(open);
  article.append(head, facts, actions); worldSearchDetail.append(article);
  openMobileWorldDetail();
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
  openMobileWorldDetail();
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
    if (member.last_online) {
      const lastOnline = document.createElement('small'); lastOnline.textContent = new Date(member.last_online).toLocaleDateString('zh-CN'); lastOnline.title = `最后在线：${new Date(member.last_online).toLocaleString('zh-CN', {hour12:false})}`; badges.append(lastOnline);
    }
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
  if (guild) openMobileWorldDetail();
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

function mapViewportGeometry() {
  const stage = document.querySelector('#map-stage');
  const width = stage.clientWidth;
  const height = stage.clientHeight;
  return {width, height, planeSize: Math.max(width, height)};
}

function updateMapOverlayPositions() {
  const {width, height, planeSize} = mapViewportGeometry();
  if (!width || !height || !planeSize) return;
  const pixelRatio = window.devicePixelRatio || 1;
  const snap = value => Math.round(value * pixelRatio) / pixelRatio;

  document.querySelectorAll('.map-layer [data-map-left]').forEach(marker => {
    const mapLeft = Number(marker.dataset.mapLeft) / 100;
    const mapTop = Number(marker.dataset.mapTop) / 100;
    const centerX = width / 2 + (mapLeft * planeSize - planeSize / 2) * mapView.zoom + mapView.panX;
    const centerY = height / 2 + (mapTop * planeSize - planeSize / 2) * mapView.zoom + mapView.panY;
    const offsetX = Number(marker.dataset.mapOffsetX || 0);
    const offsetY = Number(marker.dataset.mapOffsetY || 0);

    if (marker.dataset.mapWidth && marker.dataset.mapHeight) {
      const rangeWidth = planeSize * (Number(marker.dataset.mapWidth) / 100) * mapView.zoom;
      const rangeHeight = planeSize * (Number(marker.dataset.mapHeight) / 100) * mapView.zoom;
      marker.style.left = `${snap(centerX - rangeWidth / 2)}px`;
      marker.style.top = `${snap(centerY - rangeHeight / 2)}px`;
      marker.style.width = `${snap(rangeWidth)}px`;
      marker.style.height = `${snap(rangeHeight)}px`;
      return;
    }

    const anchorX = Number(marker.dataset.mapAnchorX || 0);
    const anchorY = Number(marker.dataset.mapAnchorY || 0);
    marker.style.left = `${snap(centerX + offsetX - anchorX)}px`;
    marker.style.top = `${snap(centerY + offsetY - anchorY)}px`;
  });
}

function clampMapPan() {
  const {width, height, planeSize} = mapViewportGeometry();
  const maxX = Math.max(0, (planeSize * mapView.zoom - width) / 2);
  const maxY = Math.max(0, (planeSize * mapView.zoom - height) / 2);
  mapView.panX = Math.max(-maxX, Math.min(maxX, mapView.panX));
  mapView.panY = Math.max(-maxY, Math.min(maxY, mapView.panY));
}

function desiredMapTileLevel() {
  const config = mapData?.tiles;
  const stage = document.querySelector('#map-stage');
  if (!config || !stage.clientWidth) return null;
  const requiredPixels = Math.max(stage.clientWidth, stage.clientHeight) * window.devicePixelRatio * mapView.zoom;
  const level = Math.ceil(Math.log2(Math.max(1, requiredPixels / config.tile_size)));
  return Math.max(config.min_zoom, Math.min(config.max_zoom, level));
}

function mapTileUrl(template, level, x, y) {
  return template.replace('{z}', level).replace('{x}', x).replace('{y}', y);
}

function setMapTileReady(ready) {
  document.querySelector('#map-fallback-plane')?.classList.toggle('tiles-ready', ready);
}

function updateMapTileReadiness(level) {
  const root = document.querySelector('#map-tile-layer');
  if (root.dataset.level !== String(level)) return;
  const tiles = [...root.querySelectorAll('img')];
  setMapTileReady(tiles.length > 0 && tiles.every(tile => tile.complete && tile.naturalWidth > 0));
}

function renderMapTiles() {
  mapTileFrame = null;
  const config = mapData?.tiles;
  const stage = document.querySelector('#map-stage');
  const root = document.querySelector('#map-tile-layer');
  const level = desiredMapTileLevel();
  if (!config || level === null || !stage.clientWidth) return;

  const {width, height, planeSize} = mapViewportGeometry();
  const columns = 2 ** level;
  const planeLeft = ((-width / 2 - mapView.panX) / mapView.zoom + planeSize / 2) / planeSize;
  const planeRight = ((width / 2 - mapView.panX) / mapView.zoom + planeSize / 2) / planeSize;
  const planeTop = ((-height / 2 - mapView.panY) / mapView.zoom + planeSize / 2) / planeSize;
  const planeBottom = ((height / 2 - mapView.panY) / mapView.zoom + planeSize / 2) / planeSize;
  const startX = Math.max(0, Math.floor(planeLeft * columns) - 1);
  const endX = Math.min(columns - 1, Math.floor(planeRight * columns) + 1);
  const startY = Math.max(0, Math.floor(planeTop * columns) - 1);
  const endY = Math.min(columns - 1, Math.floor(planeBottom * columns) + 1);
  const existing = new Map([...root.querySelectorAll('img')].map(tile => [tile.dataset.tileKey, tile]));
  const fragment = document.createDocumentFragment();
  const pixelRatio = window.devicePixelRatio || 1;
  const snap = value => Math.round(value * pixelRatio) / pixelRatio;
  let addedTile = false;

  if (root.dataset.level !== String(level)) {
    root.dataset.level = String(level);
    setMapTileReady(false);
  }

  for (let x = startX; x <= endX; x += 1) {
    for (let y = startY; y <= endY; y += 1) {
      const key = `${level}/${x}/${y}`;
      let tile = existing.get(key);
      if (tile) {
        existing.delete(key);
      } else {
        tile = document.createElement('img');
        tile.alt = '';
        tile.draggable = false;
        tile.decoding = 'async';
        tile.dataset.tileKey = key;
        tile.addEventListener('load', () => updateMapTileReadiness(level));
        tile.addEventListener('error', () => setMapTileReady(false));
        tile.src = mapTileUrl(config.url_template, level, x, y);
        fragment.append(tile);
        addedTile = true;
      }

      const left = snap(width / 2 + ((x / columns) * planeSize - planeSize / 2) * mapView.zoom + mapView.panX);
      const right = snap(width / 2 + (((x + 1) / columns) * planeSize - planeSize / 2) * mapView.zoom + mapView.panX);
      const top = snap(height / 2 + ((y / columns) * planeSize - planeSize / 2) * mapView.zoom + mapView.panY);
      const bottom = snap(height / 2 + (((y + 1) / columns) * planeSize - planeSize / 2) * mapView.zoom + mapView.panY);
      tile.style.left = `${left}px`;
      tile.style.top = `${top}px`;
      tile.style.width = `${right - left + 0.5 / pixelRatio}px`;
      tile.style.height = `${bottom - top + 0.5 / pixelRatio}px`;
    }
  }
  existing.forEach(tile => tile.remove());
  root.append(fragment);
  if (addedTile) setMapTileReady(false);
  updateMapTileReadiness(level);
}

function scheduleMapTiles() {
  if (mapTileFrame !== null) return;
  mapTileFrame = requestAnimationFrame(renderMapTiles);
}

function updateMapTransform() {
  clampMapPan();
  const {width, height, planeSize} = mapViewportGeometry();
  const transform = `translate(${mapView.panX}px, ${mapView.panY}px) scale(${mapView.zoom})`;
  const fallback = document.querySelector('#map-fallback-plane');
  fallback.style.inset = 'auto';
  fallback.style.left = `${(width - planeSize) / 2}px`;
  fallback.style.top = `${(height - planeSize) / 2}px`;
  fallback.style.width = `${planeSize}px`;
  fallback.style.height = `${planeSize}px`;
  fallback.style.transform = transform;
  document.querySelector('#map-zoom-label').textContent = `${Math.round(mapView.zoom * 100)}%`;
  document.querySelector('#map-stage').classList.toggle('map-zoom-detail', mapView.zoom >= 2.2);
  updateMapOverlayPositions();
  scheduleMapTiles();
}

function setMapZoom(next, anchor = null) {
  const previous = mapView.zoom;
  const zoom = Math.max(1, Math.min(MAP_MAX_DISPLAY_ZOOM, next));
  if (anchor && zoom !== previous) {
    const rect = document.querySelector('#map-stage').getBoundingClientRect();
    const cursorX = anchor.clientX - rect.left - rect.width / 2;
    const cursorY = anchor.clientY - rect.top - rect.height / 2;
    mapView.panX = cursorX - ((cursorX - mapView.panX) / previous) * zoom;
    mapView.panY = cursorY - ((cursorY - mapView.panY) / previous) * zoom;
  }
  mapView.zoom = zoom;
  if (mapView.zoom === 1) { mapView.panX = 0; mapView.panY = 0; }
  updateMapTransform();
}

function resetMapView() {
  mapView.zoom = 1;
  mapView.panX = 0;
  mapView.panY = 0;
  updateMapTransform();
}

function mapWorldPositionAt(clientX, clientY) {
  if (!mapData) return null;
  const rect = document.querySelector('#map-stage').getBoundingClientRect();
  const planeSize = Math.max(rect.width, rect.height);
  const centeredX = clientX - rect.left - rect.width / 2;
  const centeredY = clientY - rect.top - rect.height / 2;
  const planeX = ((centeredX - mapView.panX) / mapView.zoom + planeSize / 2) / planeSize;
  const planeY = ((centeredY - mapView.panY) / mapView.zoom + planeSize / 2) / planeSize;
  if (planeX < 0 || planeX > 1 || planeY < 0 || planeY > 1) return null;
  const bounds = mapData.landscape;
  const mapX = -planeY * 256;
  const mapY = planeX * 256;
  return {
    x: ((mapX + 256) * (bounds.max_x - bounds.min_x)) / 256 + bounds.min_x,
    y: (mapY * (bounds.max_y - bounds.min_y)) / 256 + bounds.min_y,
  };
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
    marker.dataset.mapLeft = position.left;
    marker.dataset.mapTop = position.top;
    marker.dataset.mapAnchorX = 4.5;
    marker.dataset.mapAnchorY = 4.5;
    marker.title = `传送点 ${index + 1} · X ${Math.round(x).toLocaleString()} · Y ${Math.round(y).toLocaleString()}`;
    marker.setAttribute('aria-label', marker.title);
    fragment.append(marker);
  });
  layer.append(fragment);
  updateMapOverlayPositions();
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
    marker.dataset.mapLeft = position.left;
    marker.dataset.mapTop = position.top;
    marker.dataset.mapAnchorX = 8.5;
    marker.dataset.mapAnchorY = 8.5;
    marker.innerHTML = '<i class="ph ph-crown" aria-hidden="true"></i>';
    marker.title = `塔主塔 ${index + 1} · X ${Math.round(x).toLocaleString()} · Y ${Math.round(y).toLocaleString()}`;
    marker.setAttribute('aria-label', marker.title);
    fragment.append(marker);
  });
  layer.append(fragment);
  updateMapOverlayPositions();
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
    range.dataset.mapLeft = position.left;
    range.dataset.mapTop = position.top;
    range.dataset.mapWidth = (base.area_range * 2 / ySpan) * 100;
    range.dataset.mapHeight = (base.area_range * 2 / xSpan) * 100;

    const marker = document.createElement('button');
    marker.type = 'button';
    marker.className = `map-base-marker${base.is_owner_guild ? ' owner' : ''}`;
    marker.classList.toggle('active', base.base_id === selectedMapBaseId);
    marker.dataset.mapLeft = position.left;
    marker.dataset.mapTop = position.top;
    marker.dataset.mapAnchorX = 11;
    marker.dataset.mapAnchorY = 11;
    marker.title = `${base.guild_name} · 据点 ${base.base_index} · 范围 ${Math.round(base.area_range).toLocaleString()}`;
    const pin = document.createElement('span'); pin.className = 'map-base-pin'; pin.innerHTML = '<i class="ph ph-buildings" aria-hidden="true"></i>';
    const label = document.createElement('span'); label.className = 'map-base-label'; label.textContent = base.guild_name;
    marker.append(pin, label);
    marker.addEventListener('pointerdown', event => event.stopPropagation());
    marker.addEventListener('click', event => { event.stopPropagation(); selectMapBase(base.base_id); });
    fragment.append(range, marker);
  }
  layer.append(fragment);
  updateMapOverlayPositions();
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
    marker.dataset.mapAnchorX = 12.5;
    marker.dataset.mapAnchorY = 12.5;
    marker.dataset.mapOffsetX = offset.x;
    marker.dataset.mapOffsetY = offset.y;
    marker.title = `${player.nickname || '未命名玩家'} · Lv.${player.level} · 服务器实时位置`;
    const pin = document.createElement('span'); pin.className = 'map-player-pin'; pin.innerHTML = '<i class="ph ph-user" aria-hidden="true"></i>';
    const label = document.createElement('span'); label.className = 'map-player-label'; label.textContent = player.nickname || '未命名玩家';
    marker.append(pin, label);
    marker.addEventListener('pointerdown', event => event.stopPropagation());
    marker.addEventListener('click', event => { event.stopPropagation(); selectMapPlayer(player.player_uid); });
    fragment.append(marker);
  }
  layer.append(fragment);
  updateMapOverlayPositions();
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
    document.querySelector('#map-detail-dialog').close();
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
    document.querySelector('#map-detail-dialog').close();
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
  const {planeSize} = mapViewportGeometry();
  mapView.panX = -((position.left - 50) / 100) * planeSize * mapView.zoom;
  mapView.panY = -((position.top - 50) / 100) * planeSize * mapView.zoom;
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

function openMapDetail() {
  const dialog = document.querySelector('#map-detail-dialog');
  if (!dialog.open) showModalWithFocus(dialog);
}

function selectMapPlayer(playerUid) {
  selectedMapPlayerId = playerUid;
  selectedMapBaseId = null;
  renderMapPlayers();
  renderBaseCampMarkers();
  renderMapPlayerDetail(playerUid);
  openMapDetail();
}

function selectMapBase(baseId) {
  selectedMapBaseId = baseId;
  selectedMapPlayerId = null;
  renderMapPlayers();
  renderBaseCampMarkers();
  renderMapBaseDetail(baseId);
  openMapDetail();
}

async function loadWorldMap() {
  if (mapRequest) return mapRequest;
  const requestedWorld = activeWorld;
  const empty = document.querySelector('#map-empty');
  const result = document.querySelector('#map-result');
  empty.classList.remove('hidden');
  empty.querySelector('strong').textContent = '正在读取服务器玩家位置';
  empty.querySelector('p').textContent = '直接请求 palworld-server Palworld REST 在线玩家接口。';
  result.textContent = '';
  mapRequest = (async () => {
    try {
      const guildPromise = requestedWorld
        ? fetch(`/api/world/guilds?path=${encodeURIComponent(requestedWorld)}`).then(async response => {
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
        world_path: requestedWorld,
      };
      syncMapPlayersFromServer(onlinePlayers);
      renderFastTravelMarkers();
      renderBossTowerMarkers();
      updateMapTransform();
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

async function ensureMapSaveData() {
  if (mapRequest) {
    try { await mapRequest; } catch (_) { /* loadWorldMap 已负责展示错误。 */ }
  }
  if (!mapData || mapData.world_path !== activeWorld) {
    mapData = null;
    await loadWorldMap();
  }
}

async function loadUsers() {
  if (!activeWorld) return;
  userPanel.classList.remove('hidden');
  usersNode.innerHTML = '<div class="empty">正在关联用户、玩家文件与帕鲁…</div>';
  const response = await fetch(`/api/world/users?path=${encodeURIComponent(activeWorld)}`);
  const data = await response.json();
  if (!response.ok) { usersNode.innerHTML = `<div class="empty">${data.detail}</div>`; return; }
  activeWorldHash = data.level_sha256;
  loadedUsers = data.users;
  renderUserNavigation();
  if (document.querySelector('[data-resource-tab="users"]').classList.contains('active')) selectUser(selectedUserId);
}

function selectUser(playerUid) {
  selectedUserId = playerUid;
  [...usersNode.children].forEach((node, index) => node.classList.toggle('active', loadedUsers[index]?.player_uid === playerUid));
  const user = loadedUsers.find(row => row.player_uid === playerUid);
  playerDetail.innerHTML = '';
  if (user) playerDetail.append(renderUser(user));
  if (user) openMobileWorldDetail();
}

const OWNED_PAL_PAGE_SIZE = 40;

function createSkillRankBadge(rank) {
  const value = Number(rank);
  if (!Number.isInteger(value) || value === 0) return null;
  const direction = value > 0 ? 'positive' : 'negative';
  const badge = document.createElement('span');
  badge.className = `skill-rank-badge skill-rank-${direction} skill-rank-${Math.abs(value)}`;
  badge.textContent = `${value > 0 ? '▲' : '▼'} ${Math.abs(value)}`;
  badge.title = `${value > 0 ? '正向' : '负向'}品级 ${Math.abs(value)}`;
  badge.setAttribute('aria-label', badge.title);
  return badge;
}

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
    const nameLine = document.createElement('span'); nameLine.className = 'passive-skill-name';
    const name = document.createElement('strong'); name.textContent = skill.name_zh;
    const rank = createSkillRankBadge(skill.rank);
    const skillId = document.createElement('code'); skillId.textContent = skill.skill_id;
    nameLine.append(name); if (rank) nameLine.append(rank);
    title.append(nameLine, skillId);
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
  card.querySelector('.owner-badge').classList.toggle('hidden', user.player_uid.toLowerCase() !== OWNER_PLAYER_UID);
  const form = card.querySelector('form');
  const editableFields = ['nickname','level','experience','unused_status_points','satiety','technology_points'];
  for (const field of editableFields) form.elements[field].value = user[field] ?? 0;
  const baseline = Object.fromEntries(editableFields.map(field => [field, String(form.elements[field].value)]));
  const saveButton = form.querySelector('.save-user');
  const saveStatus = form.querySelector('.save-result');
  const changedFields = () => editableFields.filter(field => String(form.elements[field].value) !== baseline[field]);
  const syncDirty = () => {
    const count = changedFields().length;
    saveButton.disabled = count === 0;
    saveStatus.textContent = count ? `${count} 项待保存` : '尚无变更';
  };
  form.addEventListener('input', syncDirty);
  form.addEventListener('change', syncDirty);
  card.querySelector('.readonly-data').textContent = `生命值 ${user.hp} · 护盾 ${user.shield_hp} · 声音 ${user.voice_id} · 实例 ${user.instance_id}`;
  renderOwnedPals(card, user);
  renderInventory(card, user);
  card.querySelectorAll('.detail-tabs button').forEach(button => button.addEventListener('click', () => {
    card.querySelectorAll('.detail-tabs button').forEach(node => {
      const active = node === button; node.classList.toggle('active', active); node.setAttribute('aria-selected', String(active));
    });
    card.querySelectorAll('.tab-pane').forEach(pane => pane.classList.toggle('hidden', pane.dataset.pane !== button.dataset.tab));
  }));
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('.save-user'); const status = form.querySelector('.save-result');
    button.disabled = true; status.textContent = '正在备份、写入并重新解析…';
    const body = {expected_sha256: activeWorldHash, expected_player_sha256:user.player_file_sha256};
    for (const field of changedFields()) body[field] = form.elements[field].type === 'number' ? Number(form.elements[field].value) : form.elements[field].value;
    let saved = false;
    try {
      const response = await fetch(`/api/world/users/${user.player_uid}?path=${encodeURIComponent(activeWorld)}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const data = await response.json(); if (!response.ok) throw new Error(data.detail);
      activeWorldHash = data.level_sha256; backupData = null; status.textContent = `已保存，备份：${data.backup_path}`;
      saved = true;
      await loadUsers();
    } catch (error) { status.textContent = error.message; }
    finally { if (!saved) syncDirty(); }
  });
  return card;
}

function inventorySlotOccupied(slot) {
  return slot.item_id !== 'None' && Number(slot.count) > 0;
}

function inventorySearchText(category, slot) {
  return [category, slot.name_zh, slot.item_id, slot.description, slot.count]
    .filter(value => value !== undefined && value !== null)
    .join(' ')
    .toLocaleLowerCase('zh-CN');
}

function renderInventory(card, user) {
  const inventoryBox = card.querySelector('.inventory-list');
  const inventories = Object.entries(user.inventories || {});
  const allSlots = inventories.flatMap(([, slots]) => slots);
  const occupiedSlots = allSlots.filter(inventorySlotOccupied);
  const totalItems = occupiedSlots.reduce((total, slot) => total + Number(slot.count || 0), 0);

  const header = document.createElement('header'); header.className = 'inventory-overview';
  const heading = document.createElement('div'); heading.className = 'inventory-heading';
  heading.innerHTML = '<span class="inventory-heading-icon"><i class="ph ph-backpack" aria-hidden="true"></i></span><span><strong>角色背包</strong><small>浏览道具，展开卡片后可修改内部 ID 与数量</small></span>';
  const stats = document.createElement('div'); stats.className = 'inventory-stats';
  stats.innerHTML = `<span><strong>${occupiedSlots.length.toLocaleString()}</strong><small>已用槽位</small></span><span><strong>${totalItems.toLocaleString()}</strong><small>道具总量</small></span><span><strong>${inventories.length.toLocaleString()}</strong><small>背包分类</small></span>`;
  header.append(heading, stats);

  const toolbar = document.createElement('div'); toolbar.className = 'inventory-toolbar';
  const search = document.createElement('label'); search.className = 'search inventory-search';
  search.innerHTML = '<i class="ph ph-magnifying-glass" aria-hidden="true"></i><span class="sr-only">搜索背包道具</span>';
  const searchInput = document.createElement('input'); searchInput.type = 'search'; searchInput.placeholder = '搜索道具名称、分类或内部 ID';
  search.append(searchInput);
  const emptyToggle = document.createElement('label'); emptyToggle.className = 'inventory-empty-toggle';
  const emptyCheckbox = document.createElement('input'); emptyCheckbox.type = 'checkbox';
  const emptyCopy = document.createElement('span'); emptyCopy.textContent = '显示空槽位';
  emptyToggle.append(emptyCheckbox, emptyCopy);
  const resultSummary = document.createElement('span'); resultSummary.className = 'inventory-result-summary';
  toolbar.append(search, emptyToggle, resultSummary);

  const groups = document.createElement('div'); groups.className = 'inventory-groups';
  const groupRows = inventories.map(([category, slots]) => {
    const group = document.createElement('section'); group.className = 'inventory-group';
    const occupied = slots.filter(inventorySlotOccupied);
    const groupHeader = document.createElement('header');
    const groupTitle = document.createElement('div');
    const title = document.createElement('h4'); title.textContent = category;
    const subtitle = document.createElement('p'); subtitle.textContent = `${occupied.length} 个有效道具 · ${slots.length} 个已记录槽位`;
    groupTitle.append(title, subtitle);
    const badge = document.createElement('span'); badge.className = 'inventory-group-badge'; badge.textContent = `${occupied.length}/${slots.length}`;
    groupHeader.append(groupTitle, badge);
    const grid = document.createElement('div'); grid.className = 'inventory-grid';
    const slotRows = slots.map(slot => {
      const node = renderInventorySlot(user, category, slot);
      grid.append(node);
      return {node, slot, searchText:inventorySearchText(category, slot)};
    });
    group.append(groupHeader, grid);
    groups.append(group);
    return {group, slotRows};
  });

  const applyFilters = () => {
    const query = searchInput.value.trim().toLocaleLowerCase('zh-CN');
    const showEmpty = emptyCheckbox.checked;
    let visibleCount = 0;
    for (const {group, slotRows} of groupRows) {
      let groupVisible = 0;
      for (const row of slotRows) {
        const visible = (showEmpty || inventorySlotOccupied(row.slot)) && (!query || row.searchText.includes(query));
        row.node.classList.toggle('hidden', !visible);
        if (visible) groupVisible += 1;
      }
      group.classList.toggle('hidden', groupVisible === 0);
      visibleCount += groupVisible;
    }
    resultSummary.textContent = query || showEmpty
      ? `显示 ${visibleCount} / ${allSlots.length}`
      : `${occupiedSlots.length} 个道具`;
    let emptyState = inventoryBox.querySelector('.inventory-filter-empty');
    if (!emptyState) {
      emptyState = document.createElement('div'); emptyState.className = 'inventory-filter-empty empty hidden';
      emptyState.innerHTML = '<i class="ph ph-magnifying-glass" aria-hidden="true"></i><strong>没有匹配的背包道具</strong><span>换个名称、分类或内部 ID 试试</span>';
      inventoryBox.append(emptyState);
    }
    emptyState.classList.toggle('hidden', visibleCount !== 0);
  };
  searchInput.addEventListener('input', applyFilters);
  emptyCheckbox.addEventListener('change', applyFilters);
  inventoryBox.append(header, toolbar, groups);
  applyFilters();
}

function renderInventorySlot(user, category, slot) {
  const occupied = inventorySlotOccupied(slot);
  const row = document.createElement('article'); row.className = `inventory-card ${occupied ? 'occupied' : 'vacant'}`;
  const preview = document.createElement('div'); preview.className = 'inventory-card-preview';
  const iconWrap = document.createElement('div'); iconWrap.className = 'inventory-card-icon';
  const image = document.createElement('img'); image.alt = ''; image.loading = 'lazy';
  if (slot.icon_url && occupied) image.src = slot.icon_url; else image.classList.add('hidden');
  image.addEventListener('error', () => image.classList.add('hidden'), {once:true});
  const fallback = document.createElement('i'); fallback.className = occupied ? 'ph ph-package' : 'ph ph-plus'; fallback.setAttribute('aria-hidden', 'true');
  iconWrap.append(image, fallback);
  const copy = document.createElement('div'); copy.className = 'inventory-card-copy';
  const name = document.createElement('strong'); name.textContent = occupied ? slot.name_zh : '空槽位'; name.title = slot.description || '';
  const meta = document.createElement('span'); meta.textContent = `槽位 ${Number(slot.slot_index) + 1}`;
  copy.append(name, meta);
  const amount = document.createElement('strong'); amount.className = 'inventory-card-count'; amount.textContent = occupied ? `× ${Number(slot.count).toLocaleString()}` : '可用';
  preview.append(iconWrap, copy, amount);

  const editor = document.createElement('details'); editor.className = 'inventory-editor';
  const editorSummary = document.createElement('summary'); editorSummary.innerHTML = '<span><i class="ph ph-pencil-simple" aria-hidden="true"></i> 编辑槽位</span><i class="ph ph-caret-down" aria-hidden="true"></i>';
  const fields = document.createElement('div'); fields.className = 'inventory-editor-fields';
  const itemField = document.createElement('label'); itemField.innerHTML = '<span>道具内部 ID</span>';
  const item = document.createElement('input'); item.value = slot.item_id; item.spellcheck = false; item.placeholder = '例如 Potion_Extreme';
  itemField.append(item);
  const countField = document.createElement('label'); countField.innerHTML = '<span>数量</span>';
  const count = document.createElement('input'); count.type = 'number'; count.min = '0'; count.max = '999999'; count.value = slot.count;
  countField.append(count);
  fields.append(itemField, countField);
  const actions = document.createElement('div'); actions.className = 'inventory-editor-actions';
  const status = document.createElement('span'); status.className = 'inventory-save-status'; status.textContent = '尚无变更';
  const save = document.createElement('button'); save.type = 'button'; save.className = 'primary'; save.textContent = '保存此槽位'; save.disabled = true;
  actions.append(status, save);
  editor.append(editorSummary, fields, actions);
  const syncDirty = () => {
    const changed = item.value !== String(slot.item_id) || Number(count.value) !== Number(slot.count);
    row.classList.toggle('changed', changed);
    save.disabled = !changed;
    status.classList.remove('error');
    status.textContent = changed ? '有未保存的修改' : '尚无变更';
  };
  item.addEventListener('input', syncDirty);
  count.addEventListener('input', syncDirty);
  save.addEventListener('click', async () => {
    save.disabled = true; save.textContent = '正在保存…'; status.classList.remove('error'); status.textContent = '正在备份并写入';
    try {
      const body = {category,slot_index:slot.slot_index,item_id:item.value,count:Number(count.value),expected_sha256:activeWorldHash};
      const response = await fetch(`/api/world/users/${user.player_uid}/inventory?path=${encodeURIComponent(activeWorld)}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const data = await response.json(); if (!response.ok) throw new Error(data.detail);
      activeWorldHash = data.level_sha256; backupData = null; await loadUsers();
    } catch (error) {
      status.textContent = error.message; status.classList.add('error');
      save.disabled = false; save.textContent = '重试保存';
    }
  });
  row.append(preview, editor); return row;
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

function setCatalogMore(button, state, noun) {
  const remaining = Math.max(0, state.matchCount - state.offset);
  button.classList.toggle('hidden', remaining === 0);
  button.disabled = state.loading;
  button.textContent = state.loading
    ? '正在加载…'
    : `继续加载 ${Math.min(CATALOG_PAGE_SIZE, remaining)} 个${noun}（已显示 ${state.offset.toLocaleString()} / ${state.matchCount.toLocaleString()}）`;
}

function catalogRequest(state, query, append) {
  const normalizedQuery = query.trim();
  const continuing = append && normalizedQuery === state.query;
  if (continuing && (state.loading || state.offset >= state.matchCount)) return null;
  state.query = normalizedQuery;
  if (!continuing) state.offset = 0;
  state.loading = true;
  state.requestId += 1;
  return {append:continuing, offset:state.offset, requestId:state.requestId};
}

function renderItemCategories(categories) {
  itemCategories.replaceChildren(...categories.map(category => {
    const label = document.createElement('label');
    label.className = 'catalog-type-option';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = category.name;
    input.checked = catalogStates.items.categories.has(category.name);
    const name = document.createElement('span'); name.textContent = category.name;
    const count = document.createElement('small'); count.textContent = category.count.toLocaleString();
    label.append(input, name, count);
    return label;
  }));
}

async function loadItems(query = '', append = false) {
  const state = catalogStates.items;
  const request = catalogRequest(state, query, append);
  if (!request) return;
  setCatalogMore(itemMore, state, '道具');
  const params = new URLSearchParams({q:state.query, limit:String(CATALOG_PAGE_SIZE), offset:String(request.offset)});
  for (const category of state.categories) params.append('category', category);
  const response = await fetch(`/api/items?${params}`);
  const data = await response.json();
  if (request.requestId !== state.requestId) return;
  renderItemCategories(data.categories);
  if (!request.append) itemResults.innerHTML = '';
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
  state.offset += data.results.length;
  state.matchCount = data.match_count;
  state.loading = false;
  const progress = state.query || state.categories.size ? `匹配 ${data.match_count.toLocaleString()} 个 · ` : '';
  itemSummary.textContent = `${data.total_items.toLocaleString()} 个内部 ID · ${progress}已显示 ${state.offset.toLocaleString()} 个 · ${data.localized_items.toLocaleString()} 个中文名称`;
  setCatalogMore(itemMore, state, '道具');
  if (!data.results.length) itemResults.innerHTML = '<div class="empty">没有匹配的道具 ID</div>';
}
itemQuery.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadItems(itemQuery.value), 180);
});
itemMore.addEventListener('click', () => loadItems(itemQuery.value, true));
itemCategories.addEventListener('change', event => {
  if (!(event.target instanceof HTMLInputElement)) return;
  if (event.target.checked) catalogStates.items.categories.add(event.target.value);
  else catalogStates.items.categories.delete(event.target.value);
  loadItems(itemQuery.value);
});
let palSearchTimer;
async function loadPals(query = '', append = false) {
  const state = catalogStates.pals;
  const request = catalogRequest(state, query, append);
  if (!request) return;
  setCatalogMore(palMore, state, '帕鲁');
  const response = await fetch(`/api/pals?q=${encodeURIComponent(state.query)}&limit=${CATALOG_PAGE_SIZE}&offset=${request.offset}`);
  const data = await response.json();
  if (request.requestId !== state.requestId) return;
  if (!request.append) palResults.innerHTML = '';
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
  state.offset += data.results.length;
  state.matchCount = data.match_count;
  state.loading = false;
  const progress = state.query ? `匹配 ${data.match_count.toLocaleString()} 个 · ` : '';
  palSummary.textContent = `${data.total_pals.toLocaleString()} 个 CharacterID · ${progress}已显示 ${state.offset.toLocaleString()} 个 · ${data.localized_pals.toLocaleString()} 个中文名称`;
  setCatalogMore(palMore, state, '帕鲁');
  if (!data.results.length) palResults.innerHTML = '<div class="empty">没有匹配的 CharacterID</div>';
}
palQuery.addEventListener('input', () => {
  clearTimeout(palSearchTimer);
  palSearchTimer = setTimeout(() => loadPals(palQuery.value), 180);
});
palMore.addEventListener('click', () => loadPals(palQuery.value, true));
let skillSearchTimer;
async function loadSkills(query = '', append = false) {
  const state = catalogStates.skills;
  const request = catalogRequest(state, query, append);
  if (!request) return;
  setCatalogMore(skillMore, state, '技能');
  const response = await fetch(`/api/skills?q=${encodeURIComponent(state.query)}&limit=${CATALOG_PAGE_SIZE}&offset=${request.offset}`);
  const data = await response.json();
  if (request.requestId !== state.requestId) return;
  if (!request.append) skillResults.innerHTML = '';
  for (const skill of data.results) {
    const row = itemTemplate.content.firstElementChild.cloneNode(true);
    setCatalogImage(row, '', 'ph-sparkle');
    row.querySelector('.item-name').textContent = skill.name_zh;
    row.querySelector('.item-description').textContent = skill.description || '暂无效果说明。';
    row.querySelector('.item-id').textContent = skill.skill_id;
    const category = row.querySelector('.item-category'); category.textContent = '被动技能';
    const rank = createSkillRankBadge(skill.rank); if (rank) category.append(rank);
    row.querySelector('.localization').textContent = '中文';
    row.addEventListener('click', () => navigator.clipboard.writeText(skill.skill_id));
    skillResults.append(row);
  }
  state.offset += data.results.length;
  state.matchCount = data.match_count;
  state.loading = false;
  const progress = state.query ? `匹配 ${data.match_count.toLocaleString()} 个 · ` : '';
  skillSummary.textContent = `${data.total_skills.toLocaleString()} 个被动技能 · ${progress}已显示 ${state.offset.toLocaleString()} 个`;
  setCatalogMore(skillMore, state, '技能');
  if (!data.results.length) skillResults.innerHTML = '<div class="empty">没有匹配的被动技能</div>';
}
skillQuery.addEventListener('input', () => {
  clearTimeout(skillSearchTimer);
  skillSearchTimer = setTimeout(() => loadSkills(skillQuery.value), 180);
});
skillMore.addEventListener('click', () => loadSkills(skillQuery.value, true));
[
  [itemResults, () => loadItems(itemQuery.value, true)],
  [palResults, () => loadPals(palQuery.value, true)],
  [skillResults, () => loadSkills(skillQuery.value, true)],
].forEach(([results, loadMore]) => results.addEventListener('scroll', () => {
  if (results.scrollHeight - results.scrollTop - results.clientHeight < 160) loadMore();
}));
containerQuery.addEventListener('input', renderContainers);
let worldSearchTimer;
worldSearchQuery.addEventListener('input', () => {
  clearTimeout(worldSearchTimer);
  worldSearchTimer = setTimeout(() => loadWorldSearch(worldSearchQuery.value), 220);
});
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
const backupDeleteDialog = document.querySelector('#backup-delete-dialog');
const backupDeleteConfirm = document.querySelector('#backup-delete-confirm');
const backupDeleteButton = document.querySelector('#confirm-backup-delete');
backupDeleteConfirm.addEventListener('change', () => { backupDeleteButton.disabled = !backupDeleteConfirm.checked; });
backupDeleteDialog.addEventListener('close', async () => {
  if (backupDeleteDialog.returnValue !== 'confirm') {
    pendingBackupDelete = null;
    setBackupResult('已取消删除，备份未受影响。');
    return;
  }
  const pending = pendingBackupDelete; pendingBackupDelete = null;
  if (!pending) { setBackupResult('删除确认已失效，请重新扫描备份。', 'error'); return; }
  setBackupResult(`正在删除 ${pending.name}…`);
  try {
    const response = await fetch(`/api/backups/${encodeURIComponent(pending.backup_id)}`, {method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({expected_created_at:pending.created_at, expected_size_bytes:pending.size_bytes, confirmed:true})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '备份删除失败');
    backupData = null;
    await loadBackups();
    setBackupResult(`已删除 ${data.backup_name} · 释放 ${formatBytes(data.freed_bytes)}`, 'ok');
  } catch (error) {
    setBackupResult(error.message, 'error');
  } finally {
    backupDeleteConfirm.checked = false;
    backupDeleteButton.disabled = true;
  }
});

document.querySelector('#reload-map').addEventListener('click', () => { mapData = null; loadWorldMap(); });
document.querySelector('#show-map-players').addEventListener('change', event => document.querySelector('#map-player-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#show-base-camps').addEventListener('change', event => document.querySelector('#base-camp-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#show-fast-travel').addEventListener('change', event => document.querySelector('#fast-travel-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#show-boss-towers').addEventListener('change', event => document.querySelector('#boss-tower-layer').classList.toggle('hidden', !event.target.checked));
document.querySelector('#map-focus-query').addEventListener('input', renderMapFocusResults);
document.querySelector('#map-zoom-in').addEventListener('click', () => setMapZoom(mapView.zoom + 0.5));
document.querySelector('#map-zoom-out').addEventListener('click', () => setMapZoom(mapView.zoom - 0.5));
document.querySelector('#map-reset-view').addEventListener('click', resetMapView);
const mapStage = document.querySelector('#map-stage');
const mapWorkspace = document.querySelector('.map-workspace');
const mapControlsToggle = document.querySelector('#map-controls-toggle');
function setMapControlsOpen(open) {
  mapWorkspace.classList.toggle('controls-open', open);
  mapControlsToggle.setAttribute('aria-expanded', String(open));
}
mapControlsToggle.addEventListener('click', () => setMapControlsOpen(!mapWorkspace.classList.contains('controls-open')));
document.querySelector('#map-controls-close').addEventListener('click', () => {
  setMapControlsOpen(false);
  mapControlsToggle.focus();
});
setMapControlsOpen(false);
mapStage.addEventListener('wheel', event => {
  event.preventDefault();
  setMapZoom(mapView.zoom + (event.deltaY < 0 ? 0.35 : -0.35), event);
}, {passive:false});
mapStage.addEventListener('dblclick', event => {
  if (event.target.closest('button')) return;
  setMapZoom(mapView.zoom + 1, event);
});
mapStage.addEventListener('pointerdown', event => {
  if (event.button !== 0 || event.target.closest('button,input,label,.map-player-marker,.map-base-marker')) return;
  mapView.drag = {pointerId:event.pointerId, x:event.clientX, y:event.clientY, panX:mapView.panX, panY:mapView.panY};
  mapStage.setPointerCapture(event.pointerId);
  mapStage.classList.add('dragging');
});
mapStage.addEventListener('pointermove', event => {
  if (mapView.drag && mapView.drag.pointerId === event.pointerId) {
    mapView.panX = mapView.drag.panX + event.clientX - mapView.drag.x;
    mapView.panY = mapView.drag.panY + event.clientY - mapView.drag.y;
    updateMapTransform();
  }
  const position = mapWorldPositionAt(event.clientX, event.clientY);
  document.querySelector('#map-coordinate').textContent = position
    ? `X ${Math.round(position.x).toLocaleString()} · Y ${Math.round(position.y).toLocaleString()}`
    : 'X — · Y —';
});
mapStage.addEventListener('pointerleave', () => { document.querySelector('#map-coordinate').textContent = 'X — · Y —'; });
mapStage.addEventListener('keydown', event => {
  const panStep = event.shiftKey ? 120 : 48;
  if (event.key === '+' || event.key === '=') setMapZoom(mapView.zoom + 0.5);
  else if (event.key === '-' || event.key === '_') setMapZoom(mapView.zoom - 0.5);
  else if (event.key === '0') resetMapView();
  else if (event.key === 'ArrowLeft') mapView.panX += panStep;
  else if (event.key === 'ArrowRight') mapView.panX -= panStep;
  else if (event.key === 'ArrowUp') mapView.panY += panStep;
  else if (event.key === 'ArrowDown') mapView.panY -= panStep;
  else return;
  event.preventDefault();
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
new ResizeObserver(updateMapTransform).observe(mapStage);

document.querySelectorAll('[data-route]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.route)));
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
    showModalWithFocus(restartDialog, configRestartButton);
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
document.querySelector('#refresh-chat').addEventListener('click', () => loadChat());
document.querySelector('#chat-query').addEventListener('input', renderChat);
window.addEventListener('hashchange', () => applyRoute());
document.querySelectorAll('[data-history-hours]').forEach(button => button.addEventListener('click', () => {
  historyHours = Number(button.dataset.historyHours);
  document.querySelectorAll('[data-history-hours]').forEach(option => option.classList.toggle('active', option === button));
  void loadServerHistory();
}));
window.addEventListener('resize', () => { if (serverHistory && currentRoute() === 'overview') renderServerHistory(); });
document.querySelector('#mobile-world-back').addEventListener('click', () => document.querySelector('.world-workspace')?.classList.remove('mobile-detail-open'));
initSidebar();
if (!location.hash) location.hash = '#/world/containers'; else applyRoute();
scan();
loadItems();
loadPals();
loadSkills();
loadBackups();
loadServerContext();
void loadServerHistory();
void loadChat({showLoading: false});
window.setInterval(refreshServerContextInBackground, SERVER_CONTEXT_REFRESH_MS);
window.setInterval(refreshChatInBackground, CHAT_REFRESH_MS);
window.setInterval(persistChatInBackground, CHAT_BACKGROUND_REFRESH_MS);
document.addEventListener('visibilitychange', refreshServerContextInBackground);
document.addEventListener('visibilitychange', refreshChatInBackground);
