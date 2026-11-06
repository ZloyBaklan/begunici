/* Standalone map dialog; all stock changes go through the existing ledger. */
(() => {
    'use strict';
    const dialog = document.getElementById('barn-feed-dialog');
    if (!dialog || dialog.dataset.bound) return;
    dialog.dataset.bound = '1';
    const form = dialog.querySelector('[data-barn-feed-form]');
    const rows = dialog.querySelector('[data-barn-feed-rows]');
    const template = dialog.querySelector('[data-barn-feed-row]');
    const error = dialog.querySelector('[data-barn-feed-error]');
    const result = document.querySelector('[data-barn-feed-result]');
    const submit = dialog.querySelector('[data-barn-feed-submit]');
    const closing = dialog.querySelector('[data-barn-feed-closing]');
    const closeRows = dialog.querySelector('[data-barn-close-rows]');
    const closeStatus = dialog.querySelector('[data-barn-close-status]');
    const zero = dialog.querySelector('[data-barn-close-zero]');
    const isClosing = () => form.elements.kind.value === 'close';
    const qty = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 3});
    let closingVersion = 0, closingReady = false;
    let busy = false;
    const showError = message => { error.textContent = message; error.hidden = false; error.focus(); };
    const updateRemove = () => rows.querySelectorAll('[data-barn-feed-remove]').forEach(button => { button.disabled = isClosing() || rows.children.length === 1; });
    const addRow = (focus = true) => {
        if (rows.children.length >= 200) return;
        const row = template.content.firstElementChild.cloneNode(true);
        const product = row.querySelector('[data-feed-product]');
        const weight = row.querySelector('[data-feed-weight]');
        const packs = row.querySelector('[data-feed-packages]');
        const total = row.querySelector('[data-feed-amount]');
        const calculate = () => {
            const auto = !weight.disabled && Number(weight.value) > 0 && Number(packs.value) > 0;
            total.readOnly = auto;
            if (auto) total.value = String(Math.round(Number(weight.value) * Number(packs.value) * 1000) / 1000);
        };
        product.addEventListener('change', () => {
            const option = product.selectedOptions[0];
            weight.disabled = option.dataset.weighted !== 'yes';
            packs.disabled = option.dataset.packaged !== 'yes';
            weight.value = weight.disabled ? '' : option.dataset.weight;
            packs.value = ''; total.value = ''; total.readOnly = false;
            row.querySelector('[data-feed-unit]').textContent = option.dataset.unit || 'кг';
        });
        weight.addEventListener('input', calculate);
        packs.addEventListener('input', calculate);
        row.querySelector('[data-barn-feed-remove]').addEventListener('click', () => { row.remove(); updateRemove(); });
        rows.append(row); updateRemove();
        if (focus) product.focus();
    };
    const loadClosing = async () => {
        const version = ++closingVersion;
        if (!isClosing()) return;
        closingReady = false; submit.disabled = true; form.elements.verified.checked = false;
        closeRows.replaceChildren(); zero.checked = false; zero.disabled = true;
        closeStatus.textContent = 'Выберите овчарню и завершённый месяц.';
        if (!form.elements.barn.value || !form.elements.month.value || !form.elements.month.checkValidity()) return;
        closeStatus.textContent = 'Загружаем остатки за месяц…';
        try {
            const url = new URL(closing.dataset.url, location.href);
            url.searchParams.set('barn', form.elements.barn.value); url.searchParams.set('month', form.elements.month.value);
            const response = await fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}});
            if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Не удалось загрузить остатки. Обновите карту.');
            const payload = await response.json();
            if (version !== closingVersion || !isClosing()) return;
            if (!response.ok) throw new Error(payload.error || 'Не удалось загрузить остатки.');
            closeStatus.textContent = payload.message;
            payload.rows.forEach(item => {
                const row = dialog.querySelector('[data-barn-close-row]').content.firstElementChild.cloneNode(true);
                row.dataset.product = item.product;
                row.querySelector('[data-close-name]').textContent = item.name;
                row.querySelector('[data-close-unit]').textContent = item.unit;
                row.querySelector('[data-close-available]').textContent = `${qty(item.available)} ${item.unit}`;
                const amount = row.querySelector('[data-close-amount]');
                const packages = row.querySelector('[data-close-packages]');
                amount.value = item.remaining; amount.max = item.available; amount.disabled = !payload.ready;
                amount.setAttribute('aria-label', `${item.name}: остаток на конец месяца`);
                packages.value = item.remaining_packages; packages.max = item.packages;
                packages.required = Boolean(item.package); packages.disabled = !payload.ready || !item.package;
                packages.setAttribute('aria-label', `${item.name}: осталось упаковок`);
                const updateUsed = () => { row.querySelector('[data-close-used]').textContent = amount.value === '' ? '—' : `${qty(Number(item.available) - Number(amount.value))} ${item.unit}`; };
                amount.addEventListener('input', updateUsed); updateUsed(); closeRows.append(row);
            });
            closingReady = payload.ready; submit.disabled = busy || !closingReady;
            zero.disabled = !closingReady || !payload.rows.length;
            zero.checked = payload.closed && payload.rows.every(item => Number(item.remaining) === 0 && Number(item.remaining_packages) === 0);
        } catch (exc) {
            if (version !== closingVersion || !isClosing()) return;
            closeStatus.textContent = exc.message;
        }
    };
    zero.addEventListener('change', () => closeRows.querySelectorAll('input').forEach(input => {
        if (input.disabled) return;
        input.value = zero.checked ? '0' : ''; input.readOnly = zero.checked;
        input.dispatchEvent(new Event('input'));
        form.elements.verified.checked = false;
    }));
    form.elements.month.addEventListener('change', loadClosing);
    form.elements.barn.addEventListener('change', loadClosing);
    const setKind = () => {
        const writeoff = form.elements.kind.value === 'writeoff';
        const close = isClosing();
        dialog.querySelector('#barn-feed-title').textContent = close ? 'Фактический расход за месяц' : writeoff ? 'Списание кормов на овчарне' : 'Поставка на овчарню';
        dialog.querySelector('[data-barn-feed-hint]').textContent = close ? 'Подтвердите естественное потребление животными по фактическим остаткам на конец месяца.' : writeoff ? 'Корм списывается с остатка выбранной овчарни по подтверждающему акту.' : 'Корм переносится с центрального склада на выбранную овчарню.';
        dialog.querySelector('[data-barn-feed-date]').hidden = close; form.elements.date.disabled = close;
        dialog.querySelector('[data-barn-feed-month]').hidden = !close; form.elements.month.disabled = !close;
        dialog.querySelector('[data-barn-feed-movement]').hidden = close; closing.hidden = !close;
        rows.querySelectorAll('tr').forEach(row => {
            const product = row.querySelector('[data-feed-product]'); const option = product.selectedOptions[0];
            product.disabled = close; row.querySelector('[data-feed-amount]').disabled = close;
            row.querySelector('[data-feed-weight]').disabled = close || option.dataset.weighted !== 'yes';
            row.querySelector('[data-feed-packages]').disabled = close || option.dataset.packaged !== 'yes';
        });
        dialog.querySelector('[data-barn-feed-add]').disabled = close; updateRemove();
        closeRows.querySelectorAll('input').forEach(input => { input.disabled = true; });
        dialog.querySelector('[data-barn-feed-note-label]').textContent = writeoff ? 'Причина списания' : 'Комментарий (необязательно)';
        form.elements.note.required = writeoff;
        const file = dialog.querySelector('[data-barn-feed-file]');
        file.hidden = !writeoff; form.elements.file.disabled = !writeoff; form.elements.file.required = writeoff;
        submit.textContent = close ? 'Подтвердить расход за месяц' : writeoff ? 'Провести списание' : 'Провести поставку';
        submit.disabled = close;
        dialog.querySelector('[data-barn-feed-verified]').textContent = close ? 'Фактические остатки проверены, подтверждаю расход' : 'Количества проверены, подтверждаю операцию';
        form.elements.verified.checked = false; error.hidden = true;
        loadClosing();
    };
    document.querySelectorAll('[data-barn-feed-open]').forEach(button => button.addEventListener('click', () => dialog.showModal()));
    dialog.querySelectorAll('[data-barn-feed-close]').forEach(button => button.addEventListener('click', () => { if (!busy) dialog.close(); }));
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.querySelector('[data-barn-feed-add]').addEventListener('click', () => addRow());
    form.querySelectorAll('[name=kind]').forEach(input => input.addEventListener('change', setKind));
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        if (isClosing() && !closingReady) { showError('Дождитесь загрузки остатков и проверьте выбранный месяц.'); return; }
        error.hidden = true;
        const data = new FormData(form);
        data.set('lines', JSON.stringify(isClosing() ? [...closeRows.children].map(row => ({
            product: row.dataset.product, amount: row.querySelector('[data-close-amount]').value,
            packages: row.querySelector('[data-close-packages]').value,
        })) : [...rows.children].map(row => ({
            product: row.querySelector('[data-feed-product]').value,
            amount: row.querySelector('[data-feed-amount]').value,
            unit_amount: row.querySelector('[data-feed-weight]').disabled ? '' : row.querySelector('[data-feed-weight]').value,
            packages: row.querySelector('[data-feed-packages]').disabled ? '' : row.querySelector('[data-feed-packages]').value,
        }))));
        const controls = [...form.querySelectorAll('input,select,textarea,button')].map(element => [element, element.disabled]);
        busy = true; form.setAttribute('aria-busy', 'true'); controls.forEach(([element]) => { element.disabled = true; });
        try {
            const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
            if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Сессия истекла или сервер недоступен. Обновите страницу и проверьте операцию.');
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || 'Не удалось провести операцию.');
            result.textContent = payload.message; result.hidden = false;
            form.reset(); form.elements.token.value = payload.token;
            rows.replaceChildren(); addRow(false); dialog.close();
            document.dispatchEvent(new CustomEvent('barn-feed-updated'));
        } catch (exc) {
            showError(exc instanceof TypeError ? 'Не удалось получить подтверждение от сервера. Повторите отправку: повторное движение не создастся.' : exc.message);
        } finally {
            busy = false; form.removeAttribute('aria-busy'); controls.forEach(([element, disabled]) => { element.disabled = disabled; });
            if (!dialog.open) setKind();
        }
    });
    addRow(false); setKind();
})();
