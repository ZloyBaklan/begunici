/* The map dialog sends movements and reconciliations to the barn ledger. */
(() => {
    'use strict';
    const dialog = document.getElementById('barn-feed-dialog');
    if (!dialog || dialog.dataset.bound) return;
    dialog.dataset.bound = '1';

    const find = selector => dialog.querySelector(selector);
    const form = find('[data-barn-feed-form]');
    const deliveries = find('[data-delivery-groups]');
    const manual = find('[data-feed-manual]');
    const closing = find('[data-barn-feed-closing]');
    const closeRows = find('[data-barn-close-rows]');
    const closeStatus = find('[data-barn-close-status]');
    const closeHerd = find('[data-barn-close-herd]');
    const applyEstimate = find('[data-apply-week-estimate]');
    const error = find('[data-barn-feed-error]');
    const result = document.querySelector('[data-barn-feed-result]');
    const submit = find('[data-barn-feed-submit]');
    const qty = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 3});
    const localDate = value => value.split('-').reverse().join('.');
    const operation = () => {
        const kind = form.elements.kind.value;
        return kind === 'writeoff' && form.elements.writeoff_mode.value === 'week' ? 'week' : kind;
    };
    const isReconciliation = () => ['close', 'week'].includes(operation());
    let closingVersion = 0;
    let closingReady = false;
    let busy = false;

    function showError(message) {
        error.textContent = message;
        error.hidden = false;
        error.focus();
    }

    function showFieldset(element, show) {
        element.hidden = !show;
        element.disabled = !show;
    }

    function showField(wrapper, input, show) {
        find(wrapper).hidden = !show;
        input.disabled = !show;
    }

    function addFeedRow(rows, focus = true) {
        if (rows.children.length >= 200) return;
        const row = find('[data-barn-feed-row]').content.firstElementChild.cloneNode(true);
        const product = row.querySelector('[data-feed-product]');
        const weight = row.querySelector('[data-feed-weight]');
        const packs = row.querySelector('[data-feed-packages]');
        const total = row.querySelector('[data-feed-amount]');
        const updateRemove = () => rows.querySelectorAll('[data-barn-feed-remove]').forEach(button => {
            button.disabled = rows.children.length === 1;
        });
        const calculate = () => {
            const automatic = !weight.disabled && Number(weight.value) > 0 && Number(packs.value) > 0;
            total.readOnly = automatic;
            if (automatic) total.value = String(Math.round(Number(weight.value) * Number(packs.value) * 1000) / 1000);
        };
        product.addEventListener('change', () => {
            const option = product.selectedOptions[0];
            weight.disabled = option.dataset.weighted !== 'yes';
            packs.disabled = option.dataset.packaged !== 'yes';
            weight.value = weight.disabled ? '' : option.dataset.weight;
            packs.value = '';
            total.value = '';
            total.readOnly = false;
            row.querySelector('[data-feed-unit]').textContent = option.dataset.unit || 'кг';
        });
        weight.addEventListener('input', calculate);
        packs.addEventListener('input', calculate);
        row.querySelector('[data-barn-feed-remove]').addEventListener('click', () => {
            row.remove();
            updateRemove();
        });
        rows.append(row);
        updateRemove();
        if (focus) product.focus();
    }

    function setupFeedRows(section) {
        const rows = section.querySelector('[data-barn-feed-rows]');
        section.querySelector('[data-barn-feed-add]').addEventListener('click', () => addFeedRow(rows));
        addFeedRow(rows, false);
    }

    function updateDestinations() {
        const selects = [...deliveries.querySelectorAll('[data-delivery-barn]')];
        const selected = selects.map(select => select.value).filter(Boolean);
        for (const select of selects) {
            for (const option of select.options) {
                option.disabled = option.value !== select.value && selected.includes(option.value);
            }
        }
        deliveries.querySelectorAll('[data-remove-delivery]').forEach(button => {
            button.disabled = selects.length === 1;
        });
        find('[data-add-delivery]').disabled = selects.length === 4;
    }

    function addDelivery(focus = true) {
        if (deliveries.children.length === 4) return;
        const group = find('[data-delivery-template]').content.firstElementChild.cloneNode(true);
        const barn = group.querySelector('[data-delivery-barn]');
        barn.addEventListener('change', updateDestinations);
        group.querySelector('[data-remove-delivery]').addEventListener('click', () => {
            group.remove();
            updateDestinations();
        });
        setupFeedRows(group);
        deliveries.append(group);
        updateDestinations();
        if (focus) barn.focus();
    }

    function movementLines(section) {
        return [...section.querySelectorAll('[data-barn-feed-rows] tr')].map(row => ({
            product: row.querySelector('[data-feed-product]').value,
            amount: row.querySelector('[data-feed-amount]').value,
            unit_amount: row.querySelector('[data-feed-weight]').value,
            packages: row.querySelector('[data-feed-packages]').value,
        }));
    }

    function renderClosingRow(item, ready) {
        const row = find('[data-barn-close-row]').content.firstElementChild.cloneNode(true);
        row.dataset.product = item.product;
        row.querySelector('[data-close-name]').textContent = item.name;
        row.querySelector('[data-close-unit]').textContent = item.unit;
        row.querySelector('[data-close-available]').textContent = `${qty(item.available)} ${item.unit}`;
        const remaining = row.querySelector('[data-close-amount]');
        const packages = row.querySelector('[data-close-packages]');
        remaining.value = item.remaining;
        remaining.max = item.available;
        remaining.disabled = !ready || item.recorded_only;
        remaining.setAttribute('aria-label', `${item.name}: фактический остаток`);
        packages.value = item.remaining_packages;
        packages.max = item.packages;
        packages.required = Boolean(item.package);
        packages.disabled = !ready || item.recorded_only || !item.package;
        packages.setAttribute('aria-label', `${item.name}: осталось упаковок`);
        if (item.estimated_remaining !== undefined) {
            row.dataset.estimate = item.estimated_remaining;
            row.querySelector('[data-close-estimated-use]').textContent = `${qty(item.estimated_use)} ${item.unit}`;
            row.querySelector('[data-close-estimated-remaining]').textContent = `${qty(item.estimated_remaining)} ${item.unit}`;
        }
        if (item.recorded_only) row.dataset.recordedOnly = 'yes';
        const updateUsed = () => {
            const used = Number(item.available) - Number(remaining.value) + Number(item.recorded_use);
            row.querySelector('[data-close-used]').textContent = remaining.value === '' ? '—' : `${qty(used)} ${item.unit}`;
        };
        remaining.addEventListener('input', updateUsed);
        updateUsed();
        closeRows.append(row);
    }

    async function loadClosing() {
        const version = ++closingVersion;
        if (!isReconciliation()) return;
        const weekly = operation() === 'week';
        const periodField = form.elements[weekly ? 'week' : 'month'];
        closingReady = false;
        submit.disabled = true;
        form.elements.verified.checked = false;
        closeRows.replaceChildren();
        closeHerd.hidden = true;
        applyEstimate.hidden = true;
        closeStatus.textContent = 'Выберите овчарню и завершённый период.';
        if (!form.elements.barn.value || !periodField.value || !periodField.checkValidity()) return;
        closeStatus.textContent = 'Загружаем остатки и рассчитываем расход…';
        try {
            const url = new URL(closing.dataset.url, location.href);
            url.searchParams.set('barn', form.elements.barn.value);
            url.searchParams.set('kind', operation());
            url.searchParams.set(periodField.name, periodField.value);
            const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
            const payload = await readResponse(response);
            if (version !== closingVersion) return;
            closeStatus.textContent = `${localDate(payload.start)} — ${localDate(payload.end)}. ${payload.message}`;
            if (payload.estimate) {
                const estimate = payload.estimate;
                const warning = estimate.missing_norms || estimate.unclassified_days ? ' Расчёт частичный: не для всех животных заданы группы или нормы.' : '';
                closeHerd.textContent = `Поголовье на конец периода: ${qty(estimate.heads)}. За период: ${qty(estimate.animal_days)} голово-дней.${warning}`;
                closeHerd.hidden = false;
                applyEstimate.hidden = !weekly || !payload.ready || Boolean(warning);
            }
            payload.rows.forEach(item => renderClosingRow(item, payload.ready));
            closingReady = payload.ready;
            submit.disabled = busy || !closingReady;
        } catch (exc) {
            if (version === closingVersion) closeStatus.textContent = exc.message;
        }
    }

    function setKind() {
        const kind = operation();
        const delivery = kind === 'delivery';
        const writeoff = kind === 'writeoff';
        const weekly = kind === 'week';
        const reconcile = isReconciliation();
        const titles = {delivery: 'Поставка на овчарню', writeoff: 'Списание кормов на овчарне',
            week: 'Расход кормов за неделю', close: 'Фактический расход за месяц'};
        const buttons = {delivery: 'Провести поставку', writeoff: 'Провести списание',
            week: 'Подтвердить расход за неделю', close: 'Подтвердить расход за месяц'};
        const hints = {delivery: 'Укажите корма и количество отдельно для каждой овчарни.',
            writeoff: 'Укажите дополнительное списание и приложите акт.',
            week: 'Расчёт по кормовым нормам за завершённую неделю. На границе месяцев неделя делится по датам месяца.',
            close: 'Расход рассчитывается по поголовью на каждый день. Поставка участвует в расчёте со дня поступления.'};
        find('#barn-feed-title').textContent = titles[kind];
        find('[data-barn-feed-hint]').textContent = hints[kind];
        showFieldset(find('[data-writeoff-options]'), writeoff || weekly);
        showField('[data-barn-feed-date]', form.elements.date, !reconcile);
        showField('[data-barn-feed-month]', form.elements.month, kind === 'close');
        showField('[data-barn-feed-week]', form.elements.week, weekly);
        showField('[data-barn-feed-single]', form.elements.barn, !delivery);
        showFieldset(find('[data-feed-deliveries]'), delivery);
        showFieldset(manual, writeoff);
        showFieldset(closing, reconcile);
        find('[data-feed-packaging-hint]').hidden = reconcile;
        showField('[data-barn-feed-file]', form.elements.file, writeoff);
        form.elements.file.required = writeoff;
        find('[data-barn-feed-note-label]').textContent = writeoff ? 'Причина списания' : 'Комментарий (необязательно)';
        form.elements.note.required = writeoff;
        find('[data-barn-close-help]').textContent = weekly ?
            'Проверьте остаток по каждой позиции, включая число упаковок. Акт не требуется.' :
            'Подтверждённые недели уже учтены в расходе месяца. Фактический остаток вводится по пересчёту. Акт не требуется.';
        find('[data-barn-feed-verified]').textContent = reconcile ?
            'Фактические остатки проверены, подтверждаю расход' : 'Количества проверены, подтверждаю операцию';
        submit.textContent = buttons[kind];
        submit.disabled = reconcile;
        form.elements.verified.checked = false;
        error.hidden = true;
        loadClosing();
    }

    async function readResponse(response) {
        if (!response.headers.get('content-type')?.includes('application/json')) {
            throw new Error('Не удалось получить ответ сервера. Обновите карту.');
        }
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Операция не выполнена.');
        return payload;
    }

    document.querySelectorAll('[data-barn-feed-open]').forEach(button => button.addEventListener('click', () => dialog.showModal()));
    dialog.querySelectorAll('[data-barn-feed-close]').forEach(button => button.addEventListener('click', () => { if (!busy) dialog.close(); }));
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    find('[data-add-delivery]').addEventListener('click', () => addDelivery());
    form.querySelectorAll('[name=kind], [name=writeoff_mode]').forEach(input => input.addEventListener('change', setKind));
    for (const name of ['month', 'week', 'barn']) form.elements[name].addEventListener('change', loadClosing);
    applyEstimate.addEventListener('click', () => {
        for (const row of closeRows.querySelectorAll('[data-estimate]')) {
            const remaining = row.querySelector('[data-close-amount]');
            remaining.value = row.dataset.estimate;
            remaining.dispatchEvent(new Event('input'));
        }
        form.elements.verified.checked = false;
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy || (isReconciliation() && !closingReady)) return;
        error.hidden = true;
        const data = new FormData(form);
        const kind = operation();
        data.set('kind', kind);
        if (kind === 'delivery') {
            data.set('deliveries', JSON.stringify([...deliveries.children].map(group => ({
                barn: group.querySelector('[data-delivery-barn]').value, lines: movementLines(group),
            }))));
        } else if (isReconciliation()) {
            data.set('lines', JSON.stringify([...closeRows.querySelectorAll('tr:not([data-recorded-only])')].map(row => ({
                product: row.dataset.product, amount: row.querySelector('[data-close-amount]').value,
                packages: row.querySelector('[data-close-packages]').value,
            }))));
        } else {
            data.set('lines', JSON.stringify(movementLines(manual)));
        }
        const controls = [...form.elements].map(element => [element, element.disabled]);
        busy = true;
        form.setAttribute('aria-busy', 'true');
        controls.forEach(([element]) => { element.disabled = true; });
        try {
            const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin'});
            const payload = await readResponse(response);
            result.textContent = payload.message;
            result.hidden = false;
            form.reset();
            form.elements.token.value = payload.token;
            deliveries.replaceChildren();
            addDelivery(false);
            const manualRows = manual.querySelector('[data-barn-feed-rows]');
            manualRows.replaceChildren();
            addFeedRow(manualRows, false);
            dialog.close();
            document.dispatchEvent(new CustomEvent('barn-feed-updated'));
        } catch (exc) {
            showError(exc instanceof TypeError ? 'Не удалось получить подтверждение. Повторите отправку с теми же данными.' : exc.message);
        } finally {
            busy = false;
            form.removeAttribute('aria-busy');
            controls.forEach(([element, disabled]) => { element.disabled = disabled; });
            if (!dialog.open) setKind();
        }
    });
    setupFeedRows(manual);
    addDelivery(false);
    setKind();
})();
