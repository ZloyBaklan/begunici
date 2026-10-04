import { apiRequest, formatDateToOutput, getApiErrorMessage, getCSRFToken } from './utils.js';

const root = document.getElementById('barn-calculator');
const form = document.getElementById('calculator-form');
const barnSelect = document.getElementById('calculator-barn');
const modeSelect = document.getElementById('calculator-mode');
const state = { config: null, barn: '1', mode: 'manual', manual: {}, factual: null, drafts: new Map(), busy: false, hasResult: false };
const formatter = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 });

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

function number(value) {
    return Number.isFinite(Number(value)) ? formatter.format(Number(value)) : '-';
}

function message(text, type = 'danger') {
    const container = document.getElementById('calculator-message');
    container.textContent = text;
    container.className = `alert alert-${type}`;
    container.hidden = !text;
}

function updateControls() {
    const disabled = state.busy || !state.config;
    form.querySelectorAll('input, select, button').forEach(control => { control.disabled = disabled; });
    root.setAttribute('aria-busy', String(disabled));
    document.getElementById('calc-wall_passage_width').disabled = disabled || !document.getElementById('calc-include_wall_passages').checked;
    form.querySelectorAll('.calculator-heads').forEach(input => { input.disabled = disabled || state.mode === 'factual'; });
    document.getElementById('calculator-save').hidden = state.barn === 'arbitrary';
    document.getElementById('calculator-export').disabled = disabled || !state.hasResult;
    modeSelect.querySelector('[value="factual"]').disabled = state.barn === 'arbitrary';
    document.getElementById('calculator-submit').disabled = disabled || state.mode === 'factual' && !state.factual;
}

function setBusy(busy) {
    state.busy = busy;
    updateControls();
}

function readParameters() {
    const parameters = {};
    form.querySelectorAll('[data-parameter]').forEach(input => {
        parameters[input.dataset.parameter] = input.type === 'checkbox' ? input.checked : input.value;
    });
    return parameters;
}

function applyParameters(parameters) {
    form.querySelectorAll('[data-parameter]').forEach(input => {
        if (input.type === 'checkbox') input.checked = parameters[input.dataset.parameter];
        else input.value = parameters[input.dataset.parameter];
    });
}

function readManual() {
    if (state.mode !== 'manual') return state.manual;
    const composition = structuredClone(state.config.empty_composition);
    form.querySelectorAll('.calculator-heads').forEach(input => {
        composition[input.dataset.group][input.dataset.side] = input.value;
    });
    return composition;
}

function rememberDraft() {
    state.manual = readManual();
    state.drafts.set(state.barn, { parameters: readParameters(), manual_composition: structuredClone(state.manual) });
}

function invalidateResult() {
    state.hasResult = false;
    document.getElementById('calculator-export').disabled = true;
    document.getElementById('calculator-result').hidden = true;
    document.getElementById('calculator-composition-total').hidden = true;
    document.querySelectorAll('[data-calculated]').forEach(cell => { cell.textContent = '-'; });
}

function renderComposition(composition) {
    document.getElementById('calculator-composition').innerHTML = state.config.norms.map(group => `
        <tr data-group-row="${group.key}">
            <td>${escapeHtml(group.label)}</td>
            ${['left', 'right'].map(side => `<td><input type="number" min="0" max="1000000" step="1" required class="form-control calculator-heads" data-group="${group.key}" data-side="${side}" value="${escapeHtml(composition[group.key]?.[side] ?? 0)}" aria-label="${escapeHtml(group.label)}, ${side === 'left' ? 'слева' : 'справа'}"></td>`).join('')}
            ${['area-left', 'area-right', 'feeding-left', 'feeding-right', 'sections-left', 'sections-right'].map(key => `<td data-calculated="${key}">-</td>`).join('')}
        </tr>`).join('');
    updateControls();
}

function renderNorms() {
    if (!state.config) return;
    const parameters = readParameters();
    const premium = parameters.breeding_premium_percent === '' ? NaN : Number(parameters.breeding_premium_percent) / 100;
    document.getElementById('calculator-norms').innerHTML = state.config.norms.map(group => {
        const free = parameters.feeding_mode === 'free_access' && ['fattening_young', 'fattening_adults'].includes(group.key);
        return `<tr><td>${escapeHtml(group.label)}</td><td>${number(group.base_area)}</td><td>${number(Number(group.base_area) * (1 + premium))}</td><td>${number(group.base_front)}</td><td>${number(Number(group.base_front) / (free ? 2 : 1))}</td><td>${number(group.section_limit)}</td></tr>`;
    }).join('');
}

function profileNote() {
    const profile = state.config.profiles.find(item => String(item.barn_number) === state.barn);
    document.getElementById('calculator-profile-note').textContent = state.barn === 'arbitrary'
        ? 'Произвольный расчёт. Параметры не сохраняются в настройки овчарен 1–4.'
        : profile?.has_saved_parameters
            ? `Параметры сохранены. Последнее изменение: ${formatDateToOutput(profile.updated_at)}.`
            : 'Параметры ещё не сохранены. Укажите реальные размеры овчарни.';
}

function renderWarnings(factual) {
    const container = document.getElementById('calculator-warnings');
    container.hidden = !factual?.warnings.length;
    if (container.hidden) { container.innerHTML = ''; return; }
    container.innerHTML = `<p>Не удалось определить нормативную группу у ${number(factual.warnings.length)} животных. Они не включены в расчёт площади и фронта. Проверка пока неполная.</p><div class="table-responsive"><table class="table"><thead><tr><th>Бирка</th><th>Овчарня</th><th>Причина</th></tr></thead><tbody>${factual.warnings.map(item => `<tr><td><a href="/animals/${encodeURIComponent(item.animal_type)}/${encodeURIComponent(item.tag_number)}/info/" target="_blank" rel="noopener">${escapeHtml(item.tag_number)}</a></td><td>${escapeHtml(item.place)}</td><td>${escapeHtml(item.reason)}</td></tr>`).join('')}</tbody></table></div>`;
}

function applyFactual(factual) {
    state.factual = factual;
    renderComposition(factual.composition);
    const note = document.getElementById('calculator-factual-note');
    note.hidden = false;
    note.textContent = `По данным на ${formatDateToOutput(factual.as_of_date)}: всего ${number(factual.total_heads)} голов, учтено ${number(factual.classified_heads)}. Нечётные отсеки слева, чётные справа.`;
    renderWarnings(factual);
}

async function refreshFactual() {
    state.factual = null;
    invalidateResult();
    message('');
    setBusy(true);
    try {
        const factual = await apiRequest(`${root.dataset.factualUrl}?barn_number=${state.barn}`);
        applyFactual(factual);
    } catch (error) {
        renderComposition(state.config.empty_composition);
        document.getElementById('calculator-factual-note').hidden = true;
        renderWarnings(null);
        message(error.message);
    } finally { setBusy(false); }
}

async function applySelection() {
    const profile = state.config.profiles.find(item => String(item.barn_number) === state.barn);
    const values = state.drafts.get(state.barn) || profile || { parameters: state.config.defaults, manual_composition: state.config.empty_composition };
    applyParameters(values.parameters);
    state.manual = structuredClone(values.manual_composition);
    state.factual = null;
    if (state.barn === 'arbitrary') state.mode = 'manual';
    modeSelect.value = state.mode;
    message('');
    invalidateResult();
    profileNote();
    renderNorms();
    document.getElementById('calculator-factual-note').hidden = true;
    renderWarnings(null);
    renderComposition(state.manual);
    if (state.mode === 'factual') await refreshFactual();
}

function renderDetails(id, pairs) {
    document.getElementById(id).innerHTML = pairs.map(([label, value, unit = '']) => `<dt>${escapeHtml(label)}</dt><dd>${number(value)}${unit ? ` ${unit}` : ''}</dd>`).join('');
}

function renderResult(result) {
    if (result.factual) applyFactual(result.factual);
    result.rows.forEach(group => {
        const row = document.querySelector(`[data-group-row="${group.key}"]`);
        for (const side of ['left', 'right']) {
            for (const metric of ['area', 'feeding', 'sections']) {
                row.querySelector(`[data-calculated="${metric}-${side}"]`).textContent = number(group[side][metric]);
            }
        }
    });
    const left = result.sides.left;
    const right = result.sides.right;
    const total = document.getElementById('calculator-composition-total');
    total.innerHTML = `<tr><td>Итого: ${number(result.total_heads)} голов</td>${[left.heads, right.heads, left.area_required, right.area_required, left.feeding_required, right.feeding_required, left.sections_required, right.sections_required].map(value => `<td>${number(value)}</td>`).join('')}</tr>`;
    total.hidden = false;
    const verdict = document.getElementById('calculator-verdict');
    verdict.textContent = result.passed === null ? 'Проверка неполная' : result.passed ? 'Проходит' : 'Не проходит';
    verdict.className = result.passed === null ? 'calculator-verdict-warning' : result.passed ? 'calculator-verdict-good' : 'calculator-verdict-bad';
    document.getElementById('calculator-checks').innerHTML = result.checks.map(check => `<tr><td>${escapeHtml(check.label)}</td><td>${number(check.available)} ${check.unit}</td><td>${number(check.required)} ${check.unit}</td><td class="${check.passed ? 'calculator-check-good' : 'calculator-check-bad'}">${number(check.remaining)} ${check.unit}</td></tr>`).join('');
    renderDetails('calculator-building-details', [
        ['Расчётная ширина', result.building.width, 'м'], ['Максимальная ширина по лимиту', result.building.max_width, 'м'],
        ['Площадь кормового проезда', result.building.central_passage_area, 'м²'], ['Площадь техпроходов', result.building.wall_passages_area, 'м²'],
    ]);
    for (const [side, values] of Object.entries(result.sides)) {
        renderDetails(`calculator-${side}-details`, [
            ['Поголовье', values.heads, 'гол.'], ['Требуется секций по нормам', values.sections_required],
            ['Задано дверей', values.doors], ['Вычет дверных проёмов', values.door_deduction, 'м'],
            ['Полезный кормовой фронт', values.feeding_available, 'м'],
        ]);
    }
    document.getElementById('calculator-result').hidden = false;
    state.hasResult = true;
    updateControls();
}

function calculationPayload() {
    return {
        barn_number: state.barn === 'arbitrary' ? null : state.barn,
        composition_mode: state.mode, parameters: readParameters(), composition: readManual(),
    };
}

form.addEventListener('submit', async event => {
    event.preventDefault();
    if (state.busy || !form.reportValidity()) return;
    const payload = calculationPayload();
    rememberDraft();
    message('');
    invalidateResult();
    setBusy(true);
    try { renderResult(await apiRequest(root.dataset.calculateUrl, 'POST', payload)); }
    catch (error) { message(error.message); }
    finally { setBusy(false); }
});

document.getElementById('calculator-export').addEventListener('click', async () => {
    if (state.busy || !state.hasResult || !form.reportValidity()) return;
    const button = document.getElementById('calculator-export');
    const payload = calculationPayload();
    message('');
    setBusy(true);
    button.textContent = 'Подготовка...';
    try {
        const response = await fetch(root.dataset.exportUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(getApiErrorMessage(data, `Ошибка экспорта: ${response.status}`));
        }
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a');
        link.href = url;
        link.download = `calculator_${state.barn === 'arbitrary' ? 'custom' : state.barn}.xlsx`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { message(error.message || 'Ошибка экспорта'); }
    finally {
        button.textContent = 'Экспорт';
        setBusy(false);
    }
});

document.getElementById('calculator-save').addEventListener('click', async () => {
    if (state.busy || !form.reportValidity() || state.barn === 'arbitrary') return;
    rememberDraft();
    const payload = { barn_number: state.barn, parameters: readParameters(), manual_composition: state.manual };
    message('');
    setBusy(true);
    try {
        const profile = await apiRequest(root.dataset.saveUrl, 'POST', payload);
        state.config.profiles = state.config.profiles.map(item => String(item.barn_number) === state.barn ? profile : item);
        state.drafts.set(state.barn, structuredClone(profile));
        profileNote();
        message(`Параметры и ручная компоновка овчарни ${state.barn} сохранены`, 'success');
    } catch (error) { message(error.message); }
    finally { setBusy(false); }
});

barnSelect.addEventListener('change', async () => {
    rememberDraft();
    state.barn = barnSelect.value;
    await applySelection();
});

modeSelect.addEventListener('change', async () => {
    state.manual = readManual();
    state.mode = modeSelect.value;
    invalidateResult();
    message('');
    if (state.mode === 'factual') await refreshFactual();
    else {
        state.factual = null;
        document.getElementById('calculator-factual-note').hidden = true;
        renderWarnings(null);
        renderComposition(state.manual);
    }
});

form.addEventListener('input', event => {
    if (event.target.matches('[data-parameter], .calculator-heads')) {
        invalidateResult();
        message('');
        updateControls();
        renderNorms();
    }
});

async function initialize() {
    setBusy(true);
    try {
        state.config = await apiRequest(root.dataset.configUrl);
        await applySelection();
    } catch (error) { message(error.message); }
    finally { setBusy(false); }
}

initialize();
