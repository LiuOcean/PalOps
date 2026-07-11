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
let activeWorld = null;
let activeWorldHash = null;
let loadedUsers = [];
let selectedUserId = null;

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
      await loadUsers();
    } catch (error) {
      result.className = 'result error'; result.textContent = error.message;
    } finally { button.disabled = false; }
  });
  return node;
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
  const itemName = document.createElement('span'); itemName.textContent = slot.name_zh;
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
document.querySelector('#reload-users').addEventListener('click', loadUsers);
let searchTimer;
async function loadItems(query = '') {
  const response = await fetch(`/api/items?q=${encodeURIComponent(query)}&limit=100`);
  const data = await response.json();
  itemSummary.textContent = `${data.total_items.toLocaleString()} 个内部 ID · ${data.localized_items.toLocaleString()} 个中文名称 · PalDB 1.0 数据`;
  itemResults.innerHTML = '';
  for (const item of data.results) {
    const row = itemTemplate.content.firstElementChild.cloneNode(true);
    row.querySelector('.item-name').textContent = item.name_zh;
    row.querySelector('.item-id').textContent = item.id;
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
    row.querySelector('.item-name').textContent = pal.name_zh;
    row.querySelector('.item-id').textContent = pal.character_id;
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
scan();
loadItems();
loadPals();
