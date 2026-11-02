(() => {
  'use strict';
  const read = id => {
    const element = document.getElementById(id);
    return element ? JSON.parse(element.textContent) : [];
  };
  const products = read('clinical-products');
  const error = document.getElementById('clinical-error');
  const finishDialog = document.getElementById('clinical-finish-dialog');
  const finishError = finishDialog?.querySelector('[data-clinical-finish-error]');
  const intake = document.getElementById('clinical-intake-form');
  const dirtyForms = new Set();
  const labels = {diagnosis: 'Диагноз', admitted_on: 'Дата поступления', place_id: 'Местонахождение',
    closed_on: 'Дата выписки', outcome: 'Исход лечения', reason: 'Причина корректировки',
    archive_act_date: 'Дата акта', archive_act_fatness: 'Упитанность', archive_act_diagnosis: 'Диагноз / основание',
    archive_act_death_reason: 'Причина падежа', carcass_weight: 'Вес туши', status_id: 'Статус'};
  function errorText(value) {
    if (Array.isArray(value)) return value.map(errorText).filter(Boolean).join('\n');
    if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) =>
      (labels[key] ? labels[key] + ': ' : '') + errorText(item)).join('\n');
    return value == null ? '' : String(value);
  }
  function openFinish() {
    if (!finishDialog) return;
    if (finishDialog.dataset.diagnosisReady !== '1' || dirtyForms.has(intake)) {
      showError('Сначала укажите и сохраните данные поступления и диагноз.');
      intake?.scrollIntoView({behavior: 'smooth', block: 'center'});
      intake?.elements.diagnosis?.focus();
      return;
    }
    window.bootstrap?.Modal.getOrCreateInstance(finishDialog).show();
  }
  document.querySelectorAll('[data-clinical-finish-open]').forEach(button => button.addEventListener('click', openFinish));
  finishDialog?.addEventListener('hide.bs.modal', event => {
    if (document.getElementById('clinical-close-form')?.dataset.saving) event.preventDefault();
  });
  const showError = message => {
    const target = finishDialog?.classList.contains('show') ? finishError : error;
    if (!target) return;
    target.textContent = errorText(message) || 'Не удалось сохранить данные. Повторите попытку.';
    target.hidden = false;
    target.scrollIntoView({behavior: 'smooth', block: 'center'});
  };
  const selectedAnimals = [...document.querySelectorAll('.clinical-selected')];
  const selectAll = document.getElementById('clinical-select-all');
  const bulkButton = document.getElementById('clinical-bulk-care');
  const clearSelection = document.getElementById('clinical-clear-selection');
  const selectionCount = document.getElementById('clinical-selected-count');
  const selectionToolbar = document.querySelector('[data-clinical-selection-toolbar]');
  const selectionKey = document.querySelector('[data-clinical-selection-key]')?.dataset?.clinicalSelectionKey;
  const selectedIds = new Set();
  function restoreSelection() {
    if (!selectionKey) return;
    try {
      const saved = JSON.parse(window.sessionStorage.getItem(selectionKey) || 'null');
      selectedIds.clear();
      if (saved && Date.now() - saved.time >= 0 && Date.now() - saved.time < 45 * 60 * 1000 && Array.isArray(saved.ids)) {
        saved.ids.slice(0, 200).forEach(id => { if (/^[0-9]+$/.test(String(id))) selectedIds.add(String(id)); });
      }
    } catch (_) { /* Selection still works when browser storage is unavailable. */ }
    selectedAnimals.forEach(element => {element.checked = selectedIds.has(element.value);});
  }
  restoreSelection();
  function saveSelection() {
    try {
      if (selectionKey) window.sessionStorage.setItem(selectionKey, JSON.stringify({time: Date.now(), ids: [...selectedIds]}));
    } catch (_) { /* Keep the current page usable without session storage. */ }
  }
  selectedAnimals.forEach(element => {element.checked = selectedIds.has(element.value);});
  function updateAnimalSelection() {
    const count = selectedIds.size;
    if (bulkButton) bulkButton.hidden = count === 0;
    if (selectionToolbar) selectionToolbar.hidden = count === 0;
    if (selectionCount) selectionCount.textContent = count;
    if (selectAll) {
      selectAll.checked = selectedAnimals.length > 0 && selectedAnimals.every(element => element.checked);
      selectAll.indeterminate = false;
    }
    saveSelection();
  }
  function selectAnimal(element) {
    if (element.checked && !selectedIds.has(element.value) && selectedIds.size >= 200) {
      element.checked = false;
      showError('За один раз можно выбрать не более 200 животных.');
    }
    if (element.checked) selectedIds.add(element.value);
    else selectedIds.delete(element.value);
  }
  selectAll?.addEventListener('change', () => {
    selectedAnimals.forEach(element => {element.checked = selectAll.checked; selectAnimal(element);});
    updateAnimalSelection();
  });
  selectedAnimals.forEach(element => element.addEventListener('change', () => {selectAnimal(element); updateAnimalSelection();}));
  clearSelection?.addEventListener('click', () => {
    selectedIds.clear();
    selectedAnimals.forEach(element => {element.checked = false;});
    updateAnimalSelection();
  });
  window.addEventListener('pageshow', () => {restoreSelection(); updateAnimalSelection();});
  updateAnimalSelection();
  bulkButton?.addEventListener('click', () => {
    if (selectedIds.size) location.href = '/animals/treatment/care/?episodes=' + [...selectedIds].join(',') +
      (bulkButton.dataset.returnUrl ? '&return_url=' + encodeURIComponent(bulkButton.dataset.returnUrl) : '');
  });
  function getLines(form) {
    return [...form.querySelectorAll('[data-clinical-lines] tr')].map(row => ({
      product: row.querySelector('[data-product]').value,
      amount: row.querySelector('[data-amount]').value,
      packages: '0',
    }));
  }
  function updateTotal(form) {
    const output = form.querySelector('[data-clinical-total]');
    if (!output) return;
    const count = form.querySelectorAll('[data-episode-id]').length;
    const multiplier = form.elements.mode?.value === 'head' ? count : 1;
    const help = form.querySelector('[data-group-help]');
    if (help) help.hidden = form.elements.mode?.value !== 'group' || count < 2;
    const totals = getLines(form).map(line => {
      const product = products.find(item => String(item.id) === line.product);
      const amount = Number(line.amount) * multiplier;
      return product ? `${product.name}: ${amount.toLocaleString('ru-RU', {maximumFractionDigits: 3})} ${product.unit}` : '';
    }).filter(Boolean);
    output.textContent = totals.length ? 'Итого на выбранных животных: ' + totals.join('; ') : '';
  }
  function setupProductPicker(form) {
    const options = form.querySelector('[data-clinical-product-options]');
    const search = form.querySelector('[data-clinical-product-search]');
    const add = form.querySelector('[data-clinical-add-selected]');
    const empty = form.querySelector('[data-clinical-picker-empty]');
    const picker = form.querySelector('[data-clinical-picker]');
    const toggle = form.querySelector('[data-clinical-picker-toggle]');
    const initial = form.dataset.clinicalForm === 'close' ? read('clinical-totals') : [];
    const choices = [];
    function quantities(lines) {
      return JSON.stringify(lines.filter(line => Number(line.amount) > 0)
        .map(line => [String(line.product), Math.round(Number(line.amount) * 1000)]).sort((a, b) => a[0].localeCompare(b[0])));
    }
    function updateRows() {
      const lines = getLines(form);
      form.querySelector('[data-clinical-lines-table]').hidden = lines.length === 0;
      form.querySelector('[data-clinical-no-lines]').hidden = lines.length > 0;
      const label = form.querySelector('[data-clinical-quantity-label]');
      label.textContent = form.dataset.clinicalForm === 'close' ? 'Фактическое количество' :
        (form.elements.mode?.value === 'group' ? 'Количество на группу' : 'Количество на голову');
      if (form.dataset.clinicalForm === 'close') {
        const changed = quantities(lines) !== quantities(initial);
        form.querySelector('[data-clinical-reason]').hidden = !changed;
        form.elements.reason.required = changed;
      }
      updateTotal(form);
    }
    function refresh() {
      const added = new Set(getLines(form).map(line => line.product));
      const query = search.value.trim().toLocaleLowerCase();
      let visible = 0;
      let checked = 0;
      for (const choice of choices) {
        choice.checkbox.disabled = added.has(String(choice.product.id));
        if (choice.checkbox.disabled) choice.checkbox.checked = false;
        choice.label.hidden = !!query && !choice.product.name.toLocaleLowerCase().includes(query);
        choice.state.textContent = choice.checkbox.disabled ? 'Добавлено' : '';
        if (!choice.label.hidden) visible += 1;
        if (choice.checkbox.checked) checked += 1;
      }
      empty.hidden = visible !== 0;
      add.disabled = checked === 0;
      add.textContent = checked ? `Добавить выбранные (${checked})` : 'Добавить выбранные';
    }
    function addLine(initial) {
      const product = products.find(item => String(item.id) === String(initial.product));
      if (!product || getLines(form).some(line => line.product === String(product.id))) return null;
      const row = document.createElement('tr');
      const productCell = row.insertCell();
      const name = document.createElement('span'); name.textContent = product.name;
      const id = document.createElement('input');
      id.type = 'hidden'; id.dataset.product = ''; id.value = String(product.id);
      productCell.append(name, id);
      const quantity = document.createElement('input');
      quantity.type = 'number'; quantity.className = 'form-control';
      quantity.min = '0'; quantity.step = '0.001'; quantity.required = true;
      quantity.value = initial.amount ?? ''; quantity.dataset.amount = '';
      quantity.setAttribute('aria-label', 'Количество: ' + product.name);
      quantity.addEventListener('input', updateRows);
      row.insertCell().append(quantity); row.insertCell().textContent = product.unit;
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'btn btn-sm btn-outline-danger';
      remove.textContent = '×'; remove.setAttribute('aria-label', 'Убрать ' + product.name);
      remove.addEventListener('click', () => {row.remove(); refresh(); updateRows(); dirtyForms.add(form);});
      row.insertCell().append(remove);
      form.querySelector('[data-clinical-lines]').append(row);
      return quantity;
    }
    for (const product of products) {
      const label = document.createElement('label'); label.className = 'clinical-product-option';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.className = 'form-check-input';
      checkbox.setAttribute('aria-label', 'Выбрать ' + product.name);
      checkbox.addEventListener('change', refresh);
      const description = document.createElement('span');
      const name = document.createElement('span'); name.textContent = product.name;
      const stock = document.createElement('small');
      stock.className = 'text-muted d-block'; stock.textContent = `Остаток: ${product.available} ${product.unit}`;
      description.append(name, stock);
      const state = document.createElement('small'); state.className = 'text-muted ms-auto';
      label.append(checkbox, description, state); options.append(label);
      choices.push({product, checkbox, label, state});
    }
    initial.forEach(addLine);
    search.addEventListener('input', refresh);
    search.addEventListener('keydown', event => {
      if (event.key === 'Enter') {event.preventDefault(); refresh();}
    });
    toggle.addEventListener('click', () => {
      picker.hidden = !picker.hidden;
      toggle.setAttribute('aria-expanded', String(!picker.hidden));
      if (!picker.hidden) search.focus();
    });
    add.addEventListener('click', () => {
      let firstQuantity = null;
      for (const choice of choices.filter(item => item.checkbox.checked)) {
        const quantity = addLine({product: choice.product.id});
        if (!firstQuantity) firstQuantity = quantity;
      }
      search.value = ''; refresh(); updateRows(); firstQuantity?.focus();
      if (firstQuantity) {
        dirtyForms.add(form);
        picker.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
    form.elements.mode?.addEventListener('change', updateRows);
    refresh(); updateRows();
  }
  document.querySelectorAll('[data-clinical-form]').forEach(form => {
    const kind = form.dataset.clinicalForm;
    if (form.querySelector('[data-clinical-lines]')) setupProductPicker(form);
    const status = form.querySelector('[data-clinical-status]');
    function toggleArchive() {
      const fieldset = form.querySelector('[data-clinical-archive]');
      if (!fieldset) return;
      const selected = status.selectedOptions[0];
      const archived = selected?.dataset.archive === '1';
      fieldset.hidden = !archived; fieldset.disabled = !archived;
      fieldset.querySelectorAll('[data-archive-required]').forEach(element => {element.required = archived;});
      const death = archived && selected.textContent.trim() === 'Падеж';
      const deathLabel = fieldset.querySelector('[data-death-reason]');
      deathLabel.hidden = !death; deathLabel.querySelector('select').required = death; deathLabel.querySelector('select').disabled = !death;
    }
    status?.addEventListener('change', toggleArchive); toggleArchive();
    const markDirty = event => {
      if (!event.target.matches('[data-clinical-product-search], [data-clinical-product-options] input')) dirtyForms.add(form);
    };
    form.addEventListener('input', markDirty);
    form.addEventListener('change', markDirty);
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (form.dataset.saving) return;
      const data = Object.fromEntries(new FormData(form));
      if (kind === 'care') data.episodes = [...form.querySelectorAll('[data-episode-id]')].map(element => ({id: element.dataset.episodeId, revision: element.dataset.revision}));
      if (kind === 'care' || kind === 'close') data.lines = getLines(form);
      data.confirm_status = !!form.elements.confirm_status?.checked;
      data.confirm_expense = !!form.elements.confirm_expense?.checked;
      data.confirm_group_move = !!form.elements.confirm_group_move?.checked;
      if (kind === 'close') {
        data.archive = Object.fromEntries(Object.entries(data).filter(([key]) => key.startsWith('archive_') || key === 'carcass_weight'));
        const forSale = form.elements.is_for_sale;
        if (forSale && !forSale.matches(':disabled')) data.archive.is_for_sale = forSale.checked;
      }
      const button = form.querySelector('button[type=submit]');
      form.dataset.saving = '1'; if (button) button.disabled = true; error.hidden = true; if (finishError) finishError.hidden = true;
      try {
        const response = await fetch(form.dataset.url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value}, body: JSON.stringify(data)});
        let result;
        try {result = await response.json();}
        catch (_) {throw new Error('Не удалось получить ответ сервера. Обновите страницу и повторите попытку.');}
        if (!response.ok) throw new Error(errorText(result.error || result));
        dirtyForms.delete(form);
        if (kind === 'care') {
          data.episodes.forEach(episode => selectedIds.delete(String(episode.id)));
          saveSelection();
        } else if (kind === 'close') {
          selectedIds.delete(form.dataset.episodeId);
          saveSelection();
        }
        location.href = result.url;
      } catch (exception) {
        showError(exception.message); delete form.dataset.saving; if (button) button.disabled = false;
      }
    });
  });
  window.addEventListener('beforeunload', event => {
    if (dirtyForms.size) {event.preventDefault(); event.returnValue = '';}
  });
  function followFinishLink() {
    if (!new URLSearchParams(location.search).get('finish') && location.hash !== '#finish') return;
    if (finishDialog) openFinish();
    else document.getElementById('finish')?.scrollIntoView();
  }
  window.addEventListener('hashchange', followFinishLink);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', followFinishLink, {once: true});
  else followFinishLink();
})();
