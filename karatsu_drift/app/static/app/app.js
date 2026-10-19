(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const yen = (value) => `¥${Number(value || 0).toLocaleString('ja-JP')}`;
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
  const avatarContent = (photoUrl, name) => photoUrl
    ? `<img src="${esc(photoUrl)}" alt="" loading="lazy">`
    : esc([...String(name || 'U')][0] || 'U');
  const today = () => {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 10);
  };
  const month = () => today().slice(0, 7);
  const state = { user: null, vehicles: [], costs: [], posts: [], categories: [], carSearchResults: [] };
  const validViews = new Set(['home', 'costs', 'cars', 'community', 'profile']);
  let currentView = 'home';
  let postPollBusy = false;
  let confirmAction = null;

  function toast(message) {
    const element = $('#toast');
    element.textContent = message;
    element.classList.add('show');
    window.setTimeout(() => element.classList.remove('show'), 2600);
  }

  function getCookie(name) {
    const cookie = document.cookie.split('; ').find((item) => item.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
  }

  async function api(path, { method = 'GET', body, formData = false } = {}) {
    const headers = { Accept: 'application/json' };
    if (method !== 'GET') headers['X-CSRFToken'] = getCookie('csrftoken');
    if (body && !formData) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {
      method,
      headers,
      cache: method === 'GET' ? 'no-store' : 'default',
      credentials: 'same-origin',
      body: body ? (formData ? body : JSON.stringify(body)) : undefined,
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
      showAuth();
      throw new Error(payload.error || 'ログインしてください。');
    }
    if (!response.ok) throw new Error(payload.error || '処理に失敗しました。');
    return payload;
  }

  function showAuth() {
    $('#startupScreen').hidden = true;
    $('#authScreen').hidden = false;
    $('#appHeader').hidden = true;
    $('#appMain').hidden = true;
    $('#appFooter').hidden = true;
  }

  function showApp() {
    $('#startupScreen').hidden = true;
    $('#authScreen').hidden = true;
    $('#appHeader').hidden = false;
    $('#appMain').hidden = false;
    $('#appFooter').hidden = false;
    $('#userAvatar').innerHTML = avatarContent(state.user.photoUrl, state.user.name);
    $('#profileButton').setAttribute('aria-label', `マイページ（${state.user.name}）`);
  }

  function switchView(name, { updateHistory = true } = {}) {
    if (!validViews.has(name)) return;
    currentView = name;
    if (updateHistory && window.location.hash !== `#${name}`) {
      window.history.pushState({ view: name }, '', `#${name}`);
    }
    $$('.view').forEach((view) => view.classList.toggle('active', view.id === `view-${name}`));
    $$('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.view === name));
    window.scrollTo({ top: 0, behavior: 'smooth' });
    render();
    if (name === 'community') refreshPosts();
  }

  function restoreViewFromLocation() {
    const requestedView = window.location.hash.slice(1);
    switchView(validViews.has(requestedView) ? requestedView : 'home', { updateHistory: false });
  }

  function setOptions(select, rows, allLabel = '') {
    const previous = select.value;
    const all = allLabel ? `<option value="all">${esc(allLabel)}</option>` : '';
    select.innerHTML = all + rows.map((row) => `<option value="${esc(row.value)}">${esc(row.label)}</option>`).join('');
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  }

  async function loadData() {
    const data = await api('/api/bootstrap/');
    state.user = data.user;
    state.vehicles = data.vehicles;
    state.costs = data.costs;
    state.posts = data.posts;
    state.categories = data.categories;
    showApp();
    render();
  }

  function selectedCosts(view) {
    let rows = [...state.costs];
    const isHome = view === 'home';
    const selectedMonth = isHome ? $('#summaryMonth').value : $('#costMonth').value;
    const selectedYear = isHome ? $('#summaryYear').value : '';
    const annual = isHome && $('#summaryMode').value === 'year';
    const selectedCategory = isHome ? $('#summaryCategory').value : $('#costCategory').value;
    const selectedVehicle = isHome ? $('#homeCar').value : $('#costCar').value;
    if (annual && selectedYear) rows = rows.filter((row) => row.date.slice(0, 4) === selectedYear);
    else if (selectedMonth) rows = rows.filter((row) => row.date.slice(0, 7) === selectedMonth);
    if (selectedCategory && selectedCategory !== 'all') rows = rows.filter((row) => row.categoryCode === selectedCategory);
    if (selectedVehicle && selectedVehicle !== 'all') rows = rows.filter((row) => row.carId === selectedVehicle);
    return rows.sort((a, b) => b.date.localeCompare(a.date));
  }

  function vehicleName(id) {
    const vehicle = state.vehicles.find((item) => item.id === id);
    return vehicle ? `${vehicle.make} ${vehicle.model}${vehicle.nickname ? `（${vehicle.nickname}）` : ''}` : '車両不明';
  }

  function costHtml(record) {
    const actions = `<div class="inline-actions"><span class="row-amount">${yen(record.amount)}</span><button class="text-button" data-edit-cost="${esc(record.id)}">編集</button><button class="text-button" data-delete-cost="${esc(record.id)}">削除</button></div>`;
    return `<div class="cost-row"><div><span class="row-title">${esc(record.category)}　${esc(vehicleName(record.carId))}</span><div class="row-sub">${esc(record.date)}${record.memo ? `　｜　${esc(record.memo)}` : ''}</div></div>${actions}</div>`;
  }

  function render() {
    if (!state.user) return;
    const vehicleOptions = state.vehicles.map((vehicle) => ({ value: vehicle.id, label: vehicleName(vehicle.id) }));
    setOptions($('#homeCar'), vehicleOptions, 'すべての車');
    setOptions($('#costCar'), vehicleOptions, 'すべての車');
    const selectedVehicleId = $('#homeCar').value;
    const selectedVehicle = state.vehicles.find((vehicle) => vehicle.id === selectedVehicleId);
    const photoVehicle = selectedVehicle || (state.vehicles.length === 1 ? state.vehicles[0] : null);
    const defaultCarImage = '/static/app/default-car.png';
    $('#garageVehicleImage').src = photoVehicle?.photoUrl || defaultCarImage;
    $('#garageVehicleImage').alt = photoVehicle ? `${photoVehicle.make} ${photoVehicle.model}の画像` : '黄色い車のイラスト';
    $('#vehiclePhotoInput').dataset.vehicleId = photoVehicle?.id || '';
    $('#changeVehiclePhoto').disabled = !photoVehicle;
    $('#changeVehiclePhoto').title = photoVehicle ? '車の画像を変更' : '画像を変更する車両を選択してください';
    $('#resetVehiclePhoto').hidden = !photoVehicle?.photoUrl;
    const garageCosts = selectedVehicleId && selectedVehicleId !== 'all'
      ? state.costs.filter((record) => record.carId === selectedVehicleId)
      : state.costs;
    $('#garageVehicleTitle').textContent = selectedVehicle
      ? `${selectedVehicle.make} ${selectedVehicle.model}`
      : state.vehicles.length ? 'ガレージの全車両' : '車両がありません';
    $('#garageVehicleSub').textContent = selectedVehicle
      ? (selectedVehicle.nickname || 'MY GARAGE')
      : state.vehicles.length ? `${state.vehicles.length}台の車両を管理中` : '車両を登録してガレージをつくりましょう';
    $('#garageVehicleStatus').textContent = selectedVehicle
      ? (selectedVehicle.shareForStats ? '統計共有中' : '登録済み')
      : state.vehicles.length ? '複数台を管理中' : '未登録';
    $('#garageVehicleYear').textContent = selectedVehicle?.year ? `${selectedVehicle.year}年` : selectedVehicle ? '未登録' : '—';
    $('#garageVehicleExpense').textContent = yen(garageCosts.reduce((sum, record) => sum + record.amount, 0));
    $('#garageVehicleRecords').textContent = `${garageCosts.length}件`;
    const garageDate = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'short', day: 'numeric' })
      .format(new Date()).toUpperCase();
    $('#garageDate').textContent = `MY GARAGE / ${garageDate}`;
    setOptions($('#summaryCategory'), state.categories.map((item) => ({ value: item.code, label: item.label })), 'すべての費目');
    setOptions($('#costCategory'), state.categories.map((item) => ({ value: item.code, label: item.label })), 'すべての費目');
    setOptions($('#costForm').elements.category, state.categories.map((item) => ({ value: item.code, label: item.label })));
    $('#summaryMonth').value ||= month();
    $('#summaryYear').value ||= today().slice(0, 4);
    $('#costMonth').value ||= month();
    const annual = $('#summaryMode').value === 'year';
    $('#summaryMonthWrap').hidden = annual;
    $('#summaryYearWrap').hidden = !annual;
    $('#summaryTotalLabel').textContent = annual ? '年間の支出' : '今月の支出';

    const summary = selectedCosts('home');
    const total = summary.reduce((sum, row) => sum + row.amount, 0);
    $('#monthTotal').textContent = yen(total);
    $('#entryCount').textContent = `${summary.length}件`;
    $('#carCount').textContent = `${state.vehicles.length}台`;
    const breakdown = state.categories.map((category) => [category.label, summary
      .filter((row) => row.categoryCode === category.code)
      .reduce((sum, row) => sum + row.amount, 0)]).filter((row) => row[1] > 0);
    $('#categoryBreakdown').className = breakdown.length ? '' : 'empty-state';
    $('#categoryBreakdown').innerHTML = breakdown.length
      ? breakdown.map(([label, amount]) => `<div class="breakdown-row"><span>${esc(label)}</span><span class="bar"><i style="width:${Math.max(4, Math.round(amount / Math.max(...breakdown.map((row) => row[1])) * 100))}%"></i></span><b>${yen(amount)}</b></div>`).join('')
      : 'まだ記録がありません。最初の支出を登録しましょう。';
    $('#recentCosts').className = summary.length ? '' : 'empty-state';
    $('#recentCosts').innerHTML = summary.length ? summary.slice(0, 5).map(costHtml).join('') : '支出を登録すると、ここに表示されます。';

    const filtered = selectedCosts('costs');
    $('#filteredTotal').textContent = yen(filtered.reduce((sum, row) => sum + row.amount, 0));
    $('#costList').className = filtered.length ? '' : 'empty-state';
    $('#costList').innerHTML = filtered.length ? filtered.map(costHtml).join('') : '記録がありません。';

    renderPosts();

    $('#vehicleList').className = state.vehicles.length ? '' : 'empty-state';
    $('#vehicleList').innerHTML = state.vehicles.length ? state.vehicles.map((vehicle) => `<div class="vehicle-row"><div><span class="row-title">${esc(vehicleName(vehicle.id))}</span><span class="row-sub">${vehicle.year ? `　${esc(vehicle.year)}年式` : ''}　${vehicle.shareForStats ? '匿名統計に共有中' : '統計共有なし'}</span></div><div class="inline-actions"><button class="text-button" data-toggle-share="${esc(vehicle.id)}">${vehicle.shareForStats ? '統計共有を解除' : '統計共有に同意'}</button><button class="text-button" data-remove-car="${esc(vehicle.id)}">削除</button></div></div>`).join('') : '車両が登録されていません。';
    $('#profileForm').elements.name.value = state.user.name;
    $('#profileForm').elements.email.value = state.user.email;
    $('#userAvatar').innerHTML = avatarContent(state.user.photoUrl, state.user.name);
    $('#profilePhotoPreview').innerHTML = avatarContent(state.user.photoUrl, state.user.name);
    $('#resetProfilePhoto').hidden = !state.user.photoUrl;
  }

  async function refresh() {
    await loadData();
  }

  async function refreshPosts() {
    if (!state.user || currentView !== 'community' || document.hidden || postPollBusy) return;
    postPollBusy = true;
    try {
      const data = await api('/api/posts/feed/');
      state.posts = data.posts;
      if (currentView === 'community') renderPosts();
    } catch (error) {
      // Keep the current feed during temporary connection errors; retry on the next poll.
    } finally {
      postPollBusy = false;
    }
  }

  function renderPosts() {
    if (!state.user) return;
    const term = $('#postSearch').value.trim().toLocaleLowerCase('ja-JP');
    const posts = state.posts.filter((post) => `${post.model} ${post.text} ${post.author}`.toLocaleLowerCase('ja-JP').includes(term));
    $('#postList').innerHTML = posts.length ? posts.map((post) => `<article class="post-card"><div class="post-meta"><div class="post-author"><span class="post-avatar">${avatarContent(post.authorPhotoUrl, post.author)}</span><span class="post-author-info"><strong>${esc(post.author)}</strong><small>${esc(post.model)}</small></span></div><time>${esc(post.createdAt.slice(0, 10))}</time></div><p class="post-body">${esc(post.text)}</p>${post.photoUrl ? `<img class="post-image" src="${esc(post.photoUrl)}" alt="${esc(post.model)}の投稿写真" loading="lazy">` : ''}${post.photo ? `<p class="row-sub">写真メモ：${esc(post.photo)}</p>` : ''}<div class="inline-actions"><button class="like-button ${post.liked ? 'liked' : ''}" data-like="${esc(post.id)}">${post.liked ? '♥' : '♡'} いいね　${post.likes}</button>${post.authorId === state.user.id ? `<button class="text-button" data-delete-post="${esc(post.id)}">投稿を削除</button>` : ''}</div></article>`).join('') : '<div class="panel empty-state">投稿がありません。最初の投稿をしてみましょう。</div>';
  }

  function openCost(record = null) {
    if (!state.vehicles.length) {
      toast('先に車両を登録してください。');
      switchView('profile');
      $('#carDialog').showModal();
      return;
    }
    const form = $('#costForm');
    setOptions(form.elements.carId, state.vehicles.map((vehicle) => ({ value: vehicle.id, label: vehicleName(vehicle.id) })));
    setOptions(form.elements.category, state.categories.map((item) => ({ value: item.code, label: item.label })));
    form.reset();
    form.elements.id.value = record?.id || '';
    form.elements.carId.value = record?.carId || state.vehicles[0].id;
    form.elements.category.value = record?.categoryCode || state.categories[0]?.code || '';
    form.elements.amount.value = record?.amount || '';
    form.elements.date.value = record?.date || today();
    form.elements.memo.value = record?.memo || '';
    $('#costDialogTitle').textContent = record ? '支出を編集' : '支出を記録';
    $('#costDialog').showModal();
  }

  function askConfirm({ title, message, button = '実行する', password = false, action }) {
    $('#confirmTitle').textContent = title;
    $('#confirmMessage').textContent = message;
    $('#confirmAction').textContent = button;
    $('#confirmPasswordWrap').hidden = !password;
    $('#confirmPassword').value = '';
    confirmAction = action;
    $('#confirmDialog').showModal();
  }

  function showAuthMode(mode) {
    const loginMode = mode === 'login';
    $('#loginForm').hidden = !loginMode;
    $('#registerForm').hidden = loginMode;
    $('#authHeading').textContent = loginMode ? 'ログイン' : '新規登録';
    $('#showLogin').className = `button ${loginMode ? 'primary' : 'secondary'}`;
    $('#showRegister').className = `button ${loginMode ? 'secondary' : 'primary'}`;
    $('#loginError').textContent = '';
    $('#registerError').textContent = '';
  }

  async function initialLoad() {
    try {
      const status = await api('/api/session/');
      if (status.authenticated) {
        await loadData();
        restoreViewFromLocation();
      } else showAuth();
    } catch (error) {
      showAuth();
      $('#loginError').textContent = error.message;
    }
  }

  $('#showLogin').addEventListener('click', () => showAuthMode('login'));
  $('#showRegister').addEventListener('click', () => showAuthMode('register'));
  $('#loginForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api('/api/login/', { method: 'POST', body: Object.fromEntries(new FormData(form)) });
      form.reset();
      await refresh();
      restoreViewFromLocation();
    } catch (error) { $('#loginError').textContent = error.message; }
  });
  $('#registerForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api('/api/register/', { method: 'POST', body: Object.fromEntries(new FormData(form)) });
      form.reset();
      await refresh();
      restoreViewFromLocation();
      toast('アカウントを作成しました。');
    } catch (error) { $('#registerError').textContent = error.message; }
  });
  $('#logoutButton').addEventListener('click', async () => {
    try { await api('/api/logout/', { method: 'POST' }); state.user = null; showAuth(); showAuthMode('login'); }
    catch (error) { toast(error.message); }
  });

  window.addEventListener('hashchange', restoreViewFromLocation);
  window.addEventListener('popstate', restoreViewFromLocation);
  window.setInterval(refreshPosts, 15000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshPosts(); });
  $$('.nav-item').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.view)));
  $$('[data-view-link]').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.viewLink)));
  $('#profileButton').addEventListener('click', () => switchView('profile'));
  ['summaryMonth', 'summaryYear', 'summaryMode', 'summaryCategory', 'homeCar', 'costMonth', 'costCategory', 'costCar', 'postSearch']
    .forEach((id) => { $(`#${id}`).addEventListener('input', render); $(`#${id}`).addEventListener('change', render); });
  $('#searchCars').addEventListener('click', async () => {
    try {
      const query = encodeURIComponent($('#carSearch').value.trim());
      const data = await api(`/api/cars/search/?q=${query}`);
      state.carSearchResults = data.results;
      $('#carResults').innerHTML = data.results.length ? data.results.map((car) => `<article class="car-card"><h3>${esc(car.make)} ${esc(car.model)} ${car.year ? `${esc(car.year)}年式` : ''}</h3><strong>${yen(car.avg)}<small>/月</small></strong><p>共有記録 ${car.count}件・記録月数 ${car.months}か月</p><p>総額 ${yen(car.total)}</p></article>`).join('') : '<div class="panel empty-state">該当する共有車種データがありません。車両の統計共有に同意した利用者の記録が蓄積されると表示されます。</div>';
    } catch (error) { toast(error.message); }
  });
  $('#carSearch').addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); $('#searchCars').click(); } });
  $$('[data-open-cost]').forEach((button) => button.addEventListener('click', () => openCost()));
  $$('[data-open-post]').forEach((button) => button.addEventListener('click', () => { $('#postForm').reset(); $('#postDialog').showModal(); }));
  $('#addCar').addEventListener('click', () => $('#carDialog').showModal());
  $('#dashboardAddCar').addEventListener('click', () => $('#carDialog').showModal());
  $('#changeVehiclePhoto').addEventListener('click', () => $('#vehiclePhotoInput').click());
  $('#vehiclePhotoInput').addEventListener('change', async (event) => {
    const input = event.currentTarget;
    const file = input.files[0];
    const vehicleId = input.dataset.vehicleId;
    if (!file || !vehicleId) return;
    const body = new FormData();
    body.set('photoFile', file);
    try {
      const result = await api(`/api/vehicles/${vehicleId}/photo/`, { method: 'POST', body, formData: true });
      const vehicle = state.vehicles.find((item) => item.id === vehicleId);
      if (vehicle) vehicle.photoUrl = result.photoUrl;
      render();
      toast('車の画像を変更しました。');
    } catch (error) { toast(error.message); }
    finally { input.value = ''; }
  });
  $('#resetVehiclePhoto').addEventListener('click', async () => {
    const vehicleId = $('#vehiclePhotoInput').dataset.vehicleId;
    if (!vehicleId) return;
    const body = new FormData();
    body.set('reset', 'true');
    try {
      await api(`/api/vehicles/${vehicleId}/photo/`, { method: 'POST', body, formData: true });
      const vehicle = state.vehicles.find((item) => item.id === vehicleId);
      if (vehicle) vehicle.photoUrl = '';
      render();
      toast('デフォルトのイラストに戻しました。');
    } catch (error) { toast(error.message); }
  });
  $$('[data-close]').forEach((button) => button.addEventListener('click', () => button.closest('dialog').close()));

  $('#profileForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try { await api('/api/profile/', { method: 'POST', body: data }); await refresh(); toast('プロフィールを保存しました。'); }
    catch (error) { toast(error.message); }
  });
  $('#changeProfilePhoto').addEventListener('click', () => $('#profilePhotoInput').click());
  $('#profilePhotoInput').addEventListener('change', async (event) => {
    const input = event.currentTarget;
    const file = input.files[0];
    if (!file) return;
    const body = new FormData();
    body.set('photoFile', file);
    try {
      await api('/api/profile/photo/', { method: 'POST', body, formData: true });
      await refresh();
      toast('プロフィール写真を変更しました。');
    } catch (error) { toast(error.message); }
    finally { input.value = ''; }
  });
  $('#resetProfilePhoto').addEventListener('click', async () => {
    const body = new FormData();
    body.set('reset', 'true');
    try {
      await api('/api/profile/photo/', { method: 'POST', body, formData: true });
      await refresh();
      toast('プロフィール写真を削除しました。');
    } catch (error) { toast(error.message); }
  });
  $('#costForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const id = data.id;
    delete data.id;
    data.amount = Number(data.amount);
    try {
      await api(id ? `/api/costs/${id}/update/` : '/api/costs/', { method: 'POST', body: data });
      $('#costDialog').close();
      await refresh();
      toast(id ? '維持費を更新しました。' : '維持費を記録しました。');
    } catch (error) { toast(error.message); }
  });
  $('#carForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    data.shareForStats = event.currentTarget.elements.shareForStats.checked;
    try { await api('/api/vehicles/', { method: 'POST', body: data }); $('#carDialog').close(); event.currentTarget.reset(); await refresh(); toast('車両を登録しました。'); }
    catch (error) { toast(error.message); }
  });
  $('#postForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try { await api('/api/posts/', { method: 'POST', body: formData, formData: true }); $('#postDialog').close(); event.currentTarget.reset(); await refresh(); switchView('community'); toast('投稿しました。'); }
    catch (error) { toast(error.message); }
  });
  $('#confirmForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!confirmAction) return;
    try { await confirmAction($('#confirmPassword').value); $('#confirmDialog').close(); confirmAction = null; }
    catch (error) { toast(error.message); }
  });

  $('#costList').addEventListener('click', async (event) => {
    const edit = event.target.closest('[data-edit-cost]');
    if (edit) { const record = state.costs.find((item) => item.id === edit.dataset.editCost); if (record) openCost(record); return; }
    const remove = event.target.closest('[data-delete-cost]');
    if (remove) askConfirm({ title: '支出記録を削除', message: 'この記録を削除します。よろしいですか？', button: '削除する', action: async () => { await api(`/api/costs/${remove.dataset.deleteCost}/delete/`, { method: 'POST' }); await refresh(); toast('記録を削除しました。'); } });
  });
  $('#recentCosts').addEventListener('click', (event) => {
    const edit = event.target.closest('[data-edit-cost]');
    if (edit) { const record = state.costs.find((item) => item.id === edit.dataset.editCost); if (record) openCost(record); }
    const remove = event.target.closest('[data-delete-cost]');
    if (remove) askConfirm({ title: '支出記録を削除', message: 'この記録を削除します。よろしいですか？', button: '削除する', action: async () => { await api(`/api/costs/${remove.dataset.deleteCost}/delete/`, { method: 'POST' }); await refresh(); toast('記録を削除しました。'); } });
  });
  $('#vehicleList').addEventListener('click', (event) => {
    const share = event.target.closest('[data-toggle-share]');
    if (share) {
      const vehicle = state.vehicles.find((item) => item.id === share.dataset.toggleShare);
      if (!vehicle) return;
      api(`/api/vehicles/${vehicle.id}/share/`, { method: 'POST', body: { shareForStats: !vehicle.shareForStats } })
        .then(refresh).then(() => toast('統計共有の設定を更新しました。')).catch((error) => toast(error.message));
      return;
    }
    const remove = event.target.closest('[data-remove-car]');
    if (remove) askConfirm({ title: '車両を削除', message: 'この車両を削除します。維持費記録がある車両は削除できません。', button: '削除する', action: async () => { await api(`/api/vehicles/${remove.dataset.removeCar}/delete/`, { method: 'POST' }); await refresh(); toast('車両を削除しました。'); } });
  });
  $('#postList').addEventListener('click', async (event) => {
    const like = event.target.closest('[data-like]');
    if (like) {
      const post = state.posts.find((item) => item.id === like.dataset.like);
      if (!post) return;
      try {
        const result = await api(`/api/posts/${post.id}/${post.liked ? 'unlike' : 'like'}/`, { method: 'POST' });
        post.liked = result.liked;
        post.likes = result.likes;
        render();
      } catch (error) { toast(error.message); }
      return;
    }
    const remove = event.target.closest('[data-delete-post]');
    if (remove) askConfirm({ title: '投稿を削除', message: 'この投稿を削除します。よろしいですか？', button: '削除する', action: async () => { await api(`/api/posts/${remove.dataset.deletePost}/delete/`, { method: 'POST' }); await refresh(); toast('投稿を削除しました。'); } });
  });
  $('#profileForm').insertAdjacentHTML('afterend', '<button type="button" id="deleteAccount" class="button danger-outline">アカウントを削除</button>');
  $('#deleteAccount').addEventListener('click', () => askConfirm({ title: 'アカウントを削除', message: 'アカウント、車両、維持費記録、投稿を削除します。この操作は取り消せません。', button: 'アカウント削除', password: true, action: async (password) => { await api('/api/account/delete/', { method: 'POST', body: { password } }); state.user = null; showAuth(); showAuthMode('login'); toast('アカウントを削除しました。'); } }));

  initialLoad();
})();
