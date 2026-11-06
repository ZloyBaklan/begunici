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
    let busy = false;
    const showError = message => { error.textContent = message; error.hidden = false; error.focus(); };
    const updateRemove = () => rows.querySelectorAll('[data-barn-feed-remove]').forEach(button => { button.disabled = rows.children.length === 1; });
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
    const setKind = () => {
        const writeoff = form.elements.kind.value === 'writeoff';
        dialog.querySelector('#barn-feed-title').textContent = writeoff ? 'Списание кормов на овчарне' : 'Поставка на овчарню';
        dialog.querySelector('[data-barn-feed-hint]').textContent = writeoff ? 'Корм списывается с остатка выбранной овчарни по подтверждающему акту.' : 'Корм переносится с центрального склада на выбранную овчарню.';
        dialog.querySelector('[data-barn-feed-note-label]').textContent = writeoff ? 'Причина списания' : 'Комментарий (необязательно)';
        form.elements.note.required = writeoff;
        const file = dialog.querySelector('[data-barn-feed-file]');
        file.hidden = !writeoff; form.elements.file.disabled = !writeoff; form.elements.file.required = writeoff;
        submit.textContent = writeoff ? 'Провести списание' : 'Провести поставку';
        form.elements.verified.checked = false; error.hidden = true;
    };
    document.querySelectorAll('[data-barn-feed-open]').forEach(button => button.addEventListener('click', () => dialog.showModal()));
    dialog.querySelectorAll('[data-barn-feed-close]').forEach(button => button.addEventListener('click', () => { if (!busy) dialog.close(); }));
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.querySelector('[data-barn-feed-add]').addEventListener('click', () => addRow());
    form.querySelectorAll('[name=kind]').forEach(input => input.addEventListener('change', setKind));
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        error.hidden = true;
        const data = new FormData(form);
        data.set('lines', JSON.stringify([...rows.children].map(row => ({
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
