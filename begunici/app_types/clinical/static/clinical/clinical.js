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
  function openFinish() {
    if (finishDialog && !finishDialog.open) finishDialog.showModal();
  }
  document.querySelectorAll('[data-clinical-finish-open]').forEach(button => button.addEventListener('click', openFinish));
  document.querySelectorAll('[data-clinical-finish-close]').forEach(button => button.addEventListener('click', () => finishDialog.close()));
  const showError = message => {
    const target = finishDialog?.open ? finishError : error;
    target.textContent = typeof message === 'string' ? message : JSON.stringify(message);
    target.hidden = false;
    target.scrollIntoView({behavior: 'smooth', block: 'center'});
  };
  const selectedAnimals = [...document.querySelectorAll('.clinical-selected')];
  const selectAll = document.getElementById('clinical-select-all');
  const bulkButton = document.getElementById('clinical-bulk-care');
  function updateAnimalSelection() {
    const count = selectedAnimals.filter(element => element.checked).length;
    if (bulkButton) bulkButton.hidden = count === 0;
    if (selectAll) {
      selectAll.checked = count > 0 && count === selectedAnimals.length;
      selectAll.indeterminate = count > 0 && count < selectedAnimals.length;
    }
  }
  selectAll?.addEventListener('change', () => {
    selectedAnimals.forEach(element => {element.checked = selectAll.checked;});
    updateAnimalSelection();
  });
  selectedAnimals.forEach(element => element.addEventListener('change', updateAnimalSelection));
  window.addEventListener('pageshow', updateAnimalSelection);
  updateAnimalSelection();
  bulkButton?.addEventListener('click', () => {
    const ids = selectedAnimals.filter(element => element.checked).map(element => element.value);
    if (ids.length) location.href = '/animals/treatment/care/?episodes=' + ids.join(',');
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
    const choices = [];
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
      quantity.addEventListener('input', () => updateTotal(form));
      row.insertCell().append(quantity); row.insertCell().textContent = product.unit;
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'btn btn-sm btn-outline-danger';
      remove.textContent = '×'; remove.setAttribute('aria-label', 'Убрать ' + product.name);
      remove.addEventListener('click', () => {row.remove(); refresh(); updateTotal(form);});
      row.insertCell().append(remove);
      form.querySelector('[data-clinical-lines]').append(row);
      return quantity;
    }
    for (const product of products) {
      const label = document.createElement('label'); label.className = 'clinical-product-option';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
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
    const initial = form.dataset.clinicalForm === 'close' ? read('clinical-totals') : [];
    initial.forEach(addLine);
    search.addEventListener('input', refresh);
    add.addEventListener('click', () => {
      let firstQuantity = null;
      for (const choice of choices.filter(item => item.checkbox.checked)) {
        const quantity = addLine({product: choice.product.id});
        if (!firstQuantity) firstQuantity = quantity;
      }
      search.value = ''; refresh(); updateTotal(form); firstQuantity?.focus();
    });
    form.elements.mode?.addEventListener('change', () => updateTotal(form));
    refresh(); updateTotal(form);
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
      const button = form.querySelector('button[type=submit],button:not([type])');
      form.dataset.saving = '1'; if (button) button.disabled = true; error.hidden = true; if (finishError) finishError.hidden = true;
      try {
        const response = await fetch(form.dataset.url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value}, body: JSON.stringify(data)});
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.error === 'string' ? result.error : JSON.stringify(result.error || result));
        location.href = result.url;
      } catch (exception) {
        showError(exception.message); delete form.dataset.saving; if (button) button.disabled = false;
      }
    });
  });
  function followFinishLink() {
    if (!new URLSearchParams(location.search).get('finish') && location.hash !== '#finish') return;
    if (finishDialog) openFinish();
    else document.getElementById('finish')?.scrollIntoView();
  }
  window.addEventListener('hashchange', followFinishLink);
  followFinishLink();
})();
