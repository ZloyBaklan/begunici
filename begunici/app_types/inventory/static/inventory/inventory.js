/* Isolated inventory UI. No patches to existing animal/archive JavaScript. */
(() => {
    'use strict';
    const root = document.getElementById('inventory-app');
    if (!root) return;
    const $ = (selector, parent = root) => parent.querySelector(selector);
    const $$ = (selector, parent = root) => [...parent.querySelectorAll(selector)];
    const json = id => { const node = document.getElementById(id); return node ? JSON.parse(node.textContent) : null; };
    const products = json('iv-products-data') || [];
    const payload = json('iv-payload-data') || {};
    const doc = $('#iv-document');
    const revision = () => Number(doc?.dataset.revision);
    const errorBox = $('#iv-error');
    let busy = false;
    let documentDirty = false;
    doc?.addEventListener('input', event => { if (event.target.id !== 'iv-verified') documentDirty = true; });
    doc?.addEventListener('change', event => { if (event.target.id !== 'iv-verified') documentDirty = true; });
    const fieldLabels = {product: 'Номенклатура', animal_id: 'Животное', weight: 'Вес, кг', quantity: 'Количество',
        animal_type: 'Тип животного', age_min: 'Возраст от, мес.', age_max: 'Возраст до, мес.', purity_min: 'Кровность от, %', purity_max: 'Кровность до, %'};
    function error(message) { errorBox.textContent = message; errorBox.hidden = false; errorBox.focus(); }
    async function run(action) {
        if (busy) return;
        busy = true;
        errorBox.hidden = true;
        root.setAttribute('aria-busy', 'true');
        try { await action(); } catch (err) { error(err.message || 'Не удалось выполнить действие. Повторите после обновления страницы.'); }
        finally { busy = false; root.removeAttribute('aria-busy'); }
    }
    async function post(url, data, file) {
        const headers = {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content};
        let body;
        if (file) { body = new FormData(); body.append('data', JSON.stringify(data)); body.append('file', file); }
        else { headers['Content-Type'] = 'application/json'; body = JSON.stringify(data); }
        const response = await fetch(url, {method: 'POST', credentials: 'same-origin', headers, body});
        let result;
        try { result = await response.json(); } catch { throw new Error('Сервер не вернул ответ. Проверьте вход в программу и обновите страницу.'); }
        if (!response.ok) { const err = new Error(result.error || 'Ошибка запроса.'); err.result = result; throw err; }
        return result;
    }
    const follow = result => { if (result.url) window.location.assign(result.url); };
    function element(tag, text, attrs = {}) {
        const node = document.createElement(tag);
        if (text !== undefined && text !== null) node.textContent = text;
        for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
        return node;
    }
    function input(field, value, type = 'text', attributes = {}) {
        const node = element('input', null, {type, class: 'form-control', 'data-field': field, 'aria-label': fieldLabels[field] || field, ...attributes});
        node.value = value ?? '';
        return node;
    }
    function select(field, choices, value) {
        const node = element('select', null, {class: 'form-select', 'data-field': field, 'aria-label': fieldLabels[field] || field});
        for (const [key, label] of choices) node.append(element('option', label, {value: key}));
        if (value !== undefined && value !== null) node.value = String(value);
        return node;
    }
    function cell(row, node) { const td = element('td'); td.append(node); row.append(td); }
    function removeButton(row) { const button = element('button', 'Удалить', {type: 'button', class: 'btn btn-outline-secondary btn-sm'}); button.addEventListener('click', () => { if (doc?.contains(row)) documentDirty = true; row.remove(); }); return button; }
    function fields(row) {
        return Object.fromEntries($$('[data-field]', row).map(node => [node.dataset.field, node.type === 'checkbox' ? node.checked : node.value]));
    }
    function confirmReplacement(file) {
        if (!file) return true;
        return window.confirm('Вы уверены, что хотите заменить текущий документ? Старый файл останется в истории. Проверьте соответствие нового файла количественным данным.');
    }
    $$('.iv-nav a').forEach(link => { if (window.location.pathname === new URL(link.href).pathname) link.setAttribute('aria-current', 'page'); });
    $$('[data-filter-table]').forEach(field => field.addEventListener('input', () => {
        const search = field.value.toLocaleLowerCase();
        document.querySelectorAll(`#${field.dataset.filterTable} tbody tr`).forEach(row => { row.hidden = !row.textContent.toLocaleLowerCase().includes(search); });
    }));
    $$('.iv-source-link').forEach(link => { link.href = `/animals/${encodeURIComponent(link.dataset.type)}/${encodeURIComponent(link.dataset.tag)}/info/`; });
    $$('[data-prepare-tag]').forEach(button => button.addEventListener('click', () => run(async () => {
        follow(await post(button.dataset.url, {kind: 'sp54', tags: [Number(button.dataset.prepareTag)]}));
    })));
    const slaughter = $('#iv-slaughter-select');
    slaughter?.addEventListener('submit', event => { event.preventDefault(); run(async () => {
        const tags = $$('input[name="tag"]:checked', slaughter).map(node => Number(node.value));
        if (!tags.length) throw new Error('Выберите животных.');
        const choice = $('[name="document_id"]', slaughter);
        follow(await post(slaughter.dataset.url, {kind: 'sp55', tags, document_id: choice.value || null, revision: choice.selectedOptions[0].dataset.revision || null}));
    }); });

    const outputs = $('#iv-outputs');
    function addOutput(value = {}) {
        const row = element('tr', null, {class: 'iv-output-row'});
        const animalChoices = [...document.querySelectorAll('#iv-animal-options option')].map(option => [option.value, option.textContent]);
        const kind = doc?.dataset.kind;
        const choices = products.filter(p => (p.category === 'live') === (kind === 'sp54'));
        cell(row, select('animal_id', animalChoices, value.animal_id));
        const productField = select('product', choices.map(p => [p.code, p.name]), value.product);
        cell(row, productField);
        cell(row, input('weight', value.weight, 'number', {step: '0.001', min: '0.001', 'aria-label': 'Вес, кг'}));
        const quantity = input('quantity', value.quantity ?? 1, 'number', {step: '1', min: '0', 'aria-label': 'Количество, шт.'});
        cell(row, quantity);
        const rejected = input('rejected', '', 'checkbox', {class: 'form-check-input', 'aria-label': 'Забраковано'}); rejected.checked = value.rejected === true;
        cell(row, rejected);
        cell(row, input('reason', value.reason || '', 'text', {class: 'form-control iv-reason', 'aria-label': 'Причина брака'}));
        cell(row, removeButton(row));
        productField.addEventListener('change', () => { if (!products.find(p => p.code === productField.value)?.counted) quantity.value = '0'; });
        if (outputs.dataset.readonly) $$('input,select,button', row).forEach(node => { node.disabled = true; });
        outputs.append(row);
    }
    if (outputs) (payload.outputs || []).forEach(addOutput);
    $('#iv-add-output')?.addEventListener('click', () => { documentDirty = true; addOutput(); });
    const receiptForm = $('#iv-receipt-save');
    receiptForm?.addEventListener('submit', event => { event.preventDefault(); const submit = event.submitter?.value === 'submit'; run(async () => {
        const file = receiptForm.elements.file.files[0];
        if (!confirmReplacement(file)) return;
        const animals = Object.fromEntries($$('#iv-receipt-animals tr').map(row => [row.dataset.animalId, fields(row)]));
        follow(await post(receiptForm.dataset.url, {revision: revision(), number: receiptForm.elements.number.value,
            payload: {animals, outputs: $$('tr', outputs).map(fields)}, submit,
            reason: receiptForm.elements.reason.value, replace_confirmed: Boolean(file)}, file));
    }); });
    $('#iv-confirm')?.addEventListener('click', event => run(async () => {
        if (documentDirty) throw new Error('В форме есть несохранённые изменения. Сначала сохраните новую версию документа или отмените изменения обновлением страницы.');
        const numbersVerified = $('#iv-verified').checked;
        if (!numbersVerified) throw new Error('Скачайте и проверьте документ, затем отметьте подтверждение проверки.');
        const data = {revision: revision(), numbers_verified: true};
        try { follow(await post(event.target.dataset.url, data)); }
        catch (err) {
            if (!err.result?.needs_keep_open) throw err;
            if (window.confirm(err.message)) follow(await post(event.target.dataset.url, {...data, keep_open: true}));
        }
    }));
    $$('.iv-file-replace').forEach(form => form.addEventListener('submit', event => { event.preventDefault(); run(async () => {
        const file = form.elements.file.files[0]; if (!confirmReplacement(file)) return;
        follow(await post(form.dataset.url, {revision: revision(), reason: form.elements.reason.value, replace_confirmed: true}, file));
    }); }));
    $$('[data-return-url]').forEach(button => button.addEventListener('click', () => run(async () => {
        const reason = window.prompt('Причина возврата СП-55 ветврачу:');
        if (reason === null) return;
        follow(await post(button.dataset.returnUrl, {revision: revision(), reason}));
    })));
    $('#iv-reverse')?.addEventListener('click', event => run(async () => {
        const reason = window.prompt('Причина сторно товарной накладной:');
        if (reason === null) return;
        if (!window.confirm('Сторнировать накладную, вернуть продукцию на склад и пересчитать заявку?')) return;
        follow(await post(event.target.dataset.url, {revision: revision(), reason}));
    }));

    const invoiceForm = $('#iv-invoice-form');
    if (invoiceForm) {
        const orders = json('iv-orders-data') || [];
        const orderField = $('#iv-invoice-order');
        orders.forEach(order => orderField.append(element('option', `№ ${order.id} · ${order.customer}`, {value: order.id})));
        orderField.value = orderField.dataset.selected || '';
        const oldLines = new Map((payload.lines || []).map(line => [String(line.lot_id), line]));
        const selected = new Set(json('iv-selected-lots') || []);
        const lotRows = $$('#iv-invoice-lots tr[data-lot-id]');
        for (const row of lotRows) {
            const old = oldLines.get(row.dataset.lotId);
            $('[data-field="selected"]', row).checked = Boolean(old) || selected.has(row.dataset.lotId);
            $('[data-field="weight"]', row).value = old?.weight ?? row.dataset.weight;
            $('[data-field="quantity"]', row).value = old?.quantity ?? row.dataset.quantity;
        }
        function updateOrder(initial = false) {
            const order = orders.find(item => String(item.id) === orderField.value);
            if (order && (!initial || !$('#iv-invoice-customer').value)) $('#iv-invoice-customer').value = order.customer;
            for (const row of lotRows) {
                const field = $('[data-field="order_line_id"]', row);
                field.replaceChildren(element('option', '—', {value: ''}));
                const matches = (order?.lines || []).filter(line => line.product === row.dataset.product);
                for (const line of matches) {
                    const quality = line.animal_type || line.age_min !== null || line.age_max !== null || line.purity_min !== '' || line.purity_max !== ''
                        ? ` · ${line.animal_type || 'Любой тип'}, ${line.age_min ?? '—'}–${line.age_max ?? '—'} мес., ${line.purity_min || '—'}–${line.purity_max || '—'}%` : '';
                    field.append(element('option', `№ ${line.id}: ${line.name}, ${line.weight} кг / ${line.quantity} шт.${quality}`, {value: line.id}));
                }
                if (matches.length === 1) field.value = String(matches[0].id);
                if (initial && oldLines.get(row.dataset.lotId)?.order_line_id) field.value = String(oldLines.get(row.dataset.lotId).order_line_id);
            }
        }
        updateOrder(true);
        orderField.addEventListener('change', () => updateOrder());
        invoiceForm.addEventListener('submit', event => { event.preventDefault(); run(async () => {
            const lines = lotRows.filter(row => $('[data-field="selected"]', row).checked).map(row => ({...fields(row), lot_id: Number(row.dataset.lotId)}));
            const file = invoiceForm.elements.file?.files[0];
            if (!confirmReplacement(file)) return;
            follow(await post(invoiceForm.dataset.url, {
                document_id: doc ? Number(doc.dataset.id) : null, revision: doc ? revision() : null,
                order_id: orderField.value || null, number: invoiceForm.elements.number.value,
                payload: {customer: $('#iv-invoice-customer').value, lines},
                reason: invoiceForm.elements.reason?.value || '', replace_confirmed: Boolean(file),
            }, file));
        }); });
    }

    const orderForm = $('#iv-order-form');
    if (orderForm) {
        const container = $('#iv-order-lines');
        function labeled(parent, title, node) { const label = element('label', title); label.append(node); parent.append(label); }
        function addLine() {
            const kind = orderForm.elements.kind.value;
            const block = element('div', null, {class: 'iv-panel iv-order-line'});
            const grid = element('div', null, {class: 'iv-fields'});
            const choices = products.filter(p => (p.category === 'live') === (kind === 'live'));
            labeled(grid, 'Номенклатура', select('product', choices.map(p => [p.code, p.name])));
            labeled(grid, 'Общий вес, кг', input('weight', 0, 'number', {min: '0', step: '0.001'}));
            labeled(grid, kind === 'live' ? 'Количество голов' : 'Количество, шт.', input('quantity', kind === 'live' ? 1 : 0, 'number', {min: '0', step: '1'}));
            if (kind === 'live') {
                labeled(grid, 'Тип животного', select('animal_type', json('iv-animal-types-data')));
                for (const [field, title, max] of [['age_min', 'Возраст от, мес.', '1000000'], ['age_max', 'Возраст до, мес.', '1000000'], ['purity_min', 'Кровность от, %', '100'], ['purity_max', 'Кровность до, %', '100']])
                    labeled(grid, title, input(field, '', 'number', {min: '0', max, step: field.startsWith('purity') ? '0.00001' : '1'}));
            }
            block.append(grid, removeButton(block)); container.append(block);
        }
        addLine();
        $('#iv-add-order-line').addEventListener('click', addLine);
        orderForm.elements.kind.addEventListener('change', () => { container.replaceChildren(); addLine(); });
        orderForm.addEventListener('submit', event => { event.preventDefault(); run(async () => {
            follow(await post(orderForm.dataset.url, {
                kind: orderForm.elements.kind.value, customer: orderForm.elements.customer.value,
                contact: orderForm.elements.contact.value, note: orderForm.elements.note.value,
                required_heads: orderForm.elements.required_heads.value,
                lines: $$('.iv-order-line', container).map(fields),
            }));
        }); });
    }
    $$('[data-close-order]').forEach(button => button.addEventListener('click', () => run(async () => { follow(await post(button.dataset.closeOrder, {})); })));

    const cutForm = $('#iv-cut-form');
    if (cutForm) {
        const container = $('#iv-cut-outputs');
        function addCut() {
            const row = element('tr');
            const productField = select('product', products.filter(p => p.code !== 'carcass').map(p => [p.code, p.name]));
            cell(row, productField);
            cell(row, input('weight', '', 'number', {min: '0.001', step: '0.001'}));
            const quantity = input('quantity', 1, 'number', {min: '0', step: '1'});
            cell(row, quantity); cell(row, removeButton(row)); container.append(row);
            productField.addEventListener('change', () => { if (!products.find(p => p.code === productField.value)?.counted) quantity.value = '0'; });
        }
        addCut(); $('#iv-add-cut-output').addEventListener('click', addCut);
        cutForm.addEventListener('submit', event => { event.preventDefault(); run(async () => {
            follow(await post(cutForm.dataset.url, {weight: cutForm.elements.weight.value, quantity: cutForm.elements.quantity.value,
                expected_weight: cutForm.dataset.weight, expected_quantity: cutForm.dataset.quantity,
                loss_weight: cutForm.elements.loss_weight.value, reason: cutForm.elements.reason.value, outputs: $$('tr', container).map(fields)}));
        }); });
    }
})();
