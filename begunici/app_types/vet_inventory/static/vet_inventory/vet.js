(() => {
    'use strict';
    document.querySelectorAll('.vet-stock nav[aria-label="Разделы склада"] a').forEach(link => {
        const path = new URL(link.href).pathname;
        if (window.location.pathname === path || (path.endsWith('/treatments/') && window.location.pathname.startsWith(path))) {
            link.classList.replace('btn-outline-secondary', 'btn-secondary');
            link.setAttribute('aria-current', 'page');
        }
    });
    document.querySelectorAll('.vet-stock form, .vet-technical form').forEach(form => {
        form.addEventListener('submit', event => {
            if (form.dataset.vetAsk && !window.confirm(form.dataset.vetAsk)) { event.preventDefault(); return; }
            if (form.hasAttribute('data-vet-confirm') && document.querySelector('[data-vet-draft][data-dirty]')) {
                event.preventDefault(); window.alert('Сначала сохраните исправления черновика.'); return;
            }
            if (form.dataset.submitting) { event.preventDefault(); return; }
            form.dataset.submitting = 'yes';
        });
        if (form.hasAttribute('data-vet-draft')) form.addEventListener('input', () => { form.dataset.dirty = 'yes'; });
    });
    document.querySelectorAll('[data-vet-lines]').forEach(table => {
        const calculate = row => {
            const size = row.querySelector('[name=line_size]');
            const packages = row.querySelector('[name=line_packages]');
            const total = row.querySelector('[name=line_amount]');
            packages.step = Number(size.value) > 0 ? '1' : '0.001';
            const automatic = Number(size.value) > 0 && Number(packages.value) > 0;
            total.readOnly = automatic;
            if (automatic) total.value = String(Math.round(Number(size.value) * Number(packages.value) * 1000) / 1000);
        };
        table.addEventListener('input', event => {
            if (event.target.matches('[name=line_size], [name=line_packages]')) calculate(event.target.closest('tr'));
        });
        table.addEventListener('click', event => {
            const button = event.target.closest('[data-vet-copy-line]');
            if (!button || table.querySelectorAll('tbody tr').length >= 200) return;
            const row = button.closest('tr').cloneNode(true);
            row.querySelectorAll('input:not([type=hidden])').forEach(input => { input.value = ''; input.readOnly = false; });
            button.closest('tr').after(row);
            row.querySelector('[name=line_size]').focus();
            table.dispatchEvent(new Event('input', {bubbles: true}));
        });
        table.querySelectorAll('tbody tr').forEach(calculate);
    });
    document.querySelectorAll('[data-vet-product-fields]').forEach(group => {
        const name = group.querySelector('[name=name]');
        const concentration = group.querySelector('[name=concentration]');
        const kind = group.querySelector('[name=concentration_unit]');
        const size = group.querySelector('[name=package_size]');
        const unit = group.querySelector('select[name=unit]');
        const fullName = group.querySelector('[data-vet-full-name]');
        const numeric = value => value.trim() === '' ? '' : Number(value.replace(',', '.'));
        const display = value => {
            const amount = numeric(value);
            return Number.isFinite(amount) && amount > 0
                ? amount.toLocaleString('ru-RU', {useGrouping: false, maximumFractionDigits: 6}) : '';
        };
        const update = () => {
            const base = name.value.trim();
            const legacyUnchanged = group.dataset.vetLegacyName && base === group.dataset.vetOriginalName
                && numeric(concentration.value) === numeric(group.dataset.vetOriginalConcentration)
                && kind.value === group.dataset.vetOriginalConcentrationUnit
                && numeric(size.value) === numeric(group.dataset.vetOriginalSize)
                && unit.value === group.dataset.vetOriginalUnit;
            let result = base;
            if (legacyUnchanged) result = group.dataset.vetLegacyName;
            else if (base) {
                if (display(concentration.value) && kind.value) {
                    const suffix = kind.value.startsWith('percent_') ? '%'
                        : ' ' + kind.selectedOptions[0].textContent.replace(' (сохранённое значение)', '');
                    result += ' ' + display(concentration.value) + suffix;
                }
                if (display(size.value)) {
                    const label = unit.selectedOptions[0].textContent.replace(' (сохранённое значение)', '');
                    result += ' (' + display(size.value) + ' ' + label + ')';
                }
            }
            fullName.value = result;
            name.setCustomValidity(result.length > 120 ? 'Полное наименование должно быть не длиннее 120 символов.' : '');
        };
        group.addEventListener('input', update);
        group.addEventListener('change', update);
        update();
    });
    document.querySelectorAll('[data-vet-expenses]').forEach(editor => {
        const groups = JSON.parse(editor.querySelector('#vet-expense-groups').textContent);
        const update = (row, reset = false) => {
            const group = groups.find(item => item.id === row.querySelector('[name=expense_group]').value);
            const select = row.querySelector('[name=expense_variant]');
            const selected = reset ? '' : select.value;
            const automatic = document.createElement('option');
            automatic.value = '';
            automatic.textContent = 'Автоматически';
            const options = (group?.variants || []).map(variant => {
                const option = document.createElement('option');
                option.value = variant.id;
                option.textContent = `${variant.name} · ${variant.available} ${variant.unit}`;
                return option;
            });
            select.replaceChildren(automatic, ...options);
            select.value = options.some(option => option.value === selected) ? selected : '';
            row.querySelector('[data-vet-expense-unit]').textContent = group?.unit_label || '—';
            row.querySelector('[data-vet-expense-help]').textContent = group
                ? `${group.basis === 'active' ? 'Действующее вещество' : 'Сам препарат'} · Остаток: ${group.available} ${group.unit_label}` : '';
        };
        const clear = row => {
            row.querySelectorAll('input, select').forEach(input => { input.value = ''; });
            update(row, true);
        };
        editor.addEventListener('change', event => {
            if (event.target.matches('[name=expense_group]')) {
                const row = event.target.closest('[data-vet-expense-row]');
                row.querySelector('[name=expense_quantity]').value = '';
                update(row, true);
            }
        });
        editor.addEventListener('click', event => {
            const rows = editor.querySelectorAll('[data-vet-expense-row]');
            if (event.target.closest('[data-vet-add-expense]') && rows.length < 200) {
                const row = rows[0].cloneNode(true);
                clear(row);
                editor.querySelector('tbody').append(row);
            }
            if (event.target.closest('[data-vet-remove-expense]')) {
                const row = event.target.closest('[data-vet-expense-row]');
                if (rows.length > 1) row.remove(); else clear(row);
            }
        });
        editor.querySelectorAll('[data-vet-expense-row]').forEach(row => update(row));
    });
    document.querySelectorAll('[data-vet-physical]').forEach(editor => {
        const groups = JSON.parse(document.getElementById('vet-physical-groups').textContent);
        const groupOf = row => groups.find(group => group.id === row.querySelector('[name=physical_group]').value);
        const status = editor.querySelector('[data-vet-calculation-status]');
        const weight = editor.querySelector('[data-vet-expense-weight]');
        const weightGroup = editor.querySelector('[data-vet-weight-field]');
        let generation = 0;
        let manualRevision = 0;
        let weightTimer;
        const showWeight = needed => {
            if (!weight || !weightGroup) return;
            weightGroup.hidden = !needed;
            weight.disabled = !needed;
        };
        const cancelCalculation = () => {
            clearTimeout(weightTimer);
            weightTimer = undefined;
            generation++;
        };
        const update = (row, reset = false) => {
            const group = groupOf(row);
            const select = row.querySelector('[data-vet-physical-product]');
            const selected = reset ? '' : select.value;
            const choices = [['', 'Выберите препарат'], ...(group?.variants || []).map(variant =>
                [variant.id, `${variant.name} · ${variant.available} ${variant.unit}`])];
            select.replaceChildren(...choices.map(([value, label]) => {
                const option = document.createElement('option');
                option.value = value; option.textContent = label;
                return option;
            }));
            select.value = choices.some(([value]) => value === selected) ? selected : '';
            const variant = group?.variants.find(variant => variant.id === select.value);
            row.querySelector('[data-vet-physical-unit]').textContent = variant?.unit || '—';
            row.querySelector('[data-vet-physical-help]').textContent = variant ? `Остаток: ${variant.available} ${variant.unit}` : '';
            if (status) showWeight(Boolean(variant?.requires_weight));
        };
        const calculate = async () => {
            const current = ++generation;
            if (!status) return;
            const row = editor.querySelector('[data-vet-physical-row]');
            const product = row.querySelector('[data-vet-physical-product]').value;
            const quantity = row.querySelector('[data-vet-physical-quantity]');
            if (!product) { status.textContent = ''; return; }
            const revision = manualRevision;
            const params = new URLSearchParams({product, weight: weight && !weight.disabled ? weight.value : ''});
            status.textContent = 'Расчёт по норме…';
            try {
                const response = await fetch(editor.dataset.vetEstimate + '?' + params.toString(), {credentials: 'same-origin', headers: {'Accept': 'application/json'}});
                const result = await response.json();
                if (current !== generation || revision !== manualRevision) return;
                if (!response.ok) {
                    if (result.requires_weight) showWeight(true);
                    status.textContent = result.requires_weight ? '' : result.error || 'Норма недоступна. Укажите количество вручную.';
                    return;
                }
                if (typeof result.requires_weight === 'boolean') showWeight(result.requires_weight);
                quantity.value = result.quantity;
                status.textContent = '';
            } catch (error) {
                if (current === generation && revision === manualRevision) status.textContent = 'Не удалось получить норму. Повторите расчёт или укажите количество вручную.';
            }
        };
        editor.addEventListener('change', event => {
            const row = event.target.closest('[data-vet-physical-row]');
            if (row && event.target.matches('[name=physical_group], [data-vet-physical-product]')) {
                cancelCalculation();
                row.querySelector('[data-vet-physical-quantity]').value = '';
                update(row, event.target.matches('[name=physical_group]'));
                calculate();
            }
        });
        editor.addEventListener('input', event => {
            if (event.target.matches('[data-vet-expense-weight]') && !weight.disabled) {
                cancelCalculation();
                editor.querySelector('[data-vet-physical-quantity]').value = '';
                if (status) status.textContent = '';
                weightTimer = setTimeout(calculate, 250);
            }
            if (event.target.matches('[data-vet-physical-quantity]')) {
                cancelCalculation();
                manualRevision++;
                if (status) status.textContent = '';
            }
        });
        editor.addEventListener('click', event => {
            const rows = editor.querySelectorAll('[data-vet-physical-row]');
            if (event.target.closest('[data-vet-add-physical]') && rows.length < 200) {
                const row = rows[0].cloneNode(true);
                row.querySelectorAll('select, input[type=number]').forEach(input => { input.value = ''; });
                update(row, true);
                editor.querySelector('tbody').append(row);
            }
            if (event.target.closest('[data-vet-remove-physical]')) {
                const row = event.target.closest('[data-vet-physical-row]');
                if (rows.length > 1) row.remove();
                else { row.querySelectorAll('select, input[type=number]').forEach(input => { input.value = ''; }); update(row, true); }
            }
        });
        editor.querySelectorAll('[data-vet-physical-row]').forEach(row => update(row));
        if (editor.dataset.initialCalculate === 'yes') calculate();
    });
    document.querySelectorAll('[data-vet-product-rules]').forEach(form => {
        const group = form.querySelector('[data-vet-rule-group]');
        const conditions = form.querySelector('[data-vet-product-conditions]');
        let dirty = false;
        const showModes = () => {
            form.querySelectorAll('[data-vet-product-rule]').forEach(row => {
                const hasConditions = conditions && [...conditions.querySelectorAll('[name=condition_product]')].some(select => select.value === row.dataset.product);
                const mode = row.querySelector('[name=norm_mode]').value;
                const step = row.querySelector('[name=norm_weight_step]');
                row.querySelector('[data-vet-product-step]').hidden = mode !== 'step';
                step.required = mode === 'step' && (hasConditions || row.querySelector('[name=norm_rate]').value !== '');
                row.querySelector('[data-vet-product-rule-help]').textContent = hasConditions ? 'Используются нормы из условий ниже.' : mode === 'bands' ? 'Задайте диапазоны и нормы в условиях ниже.' : '';
            });
        };
        form.addEventListener('input', () => { dirty = true; showModes(); });
        form.addEventListener('change', event => { if (event.target !== group) { dirty = true; showModes(); } });
        group.addEventListener('change', () => {
            if (dirty && !window.confirm('Перейти к другому препарату без сохранения изменений?')) { group.value = new URL(window.location.href).searchParams.get('group') || group.dataset.initial; return; }
            const url = new URL(window.location.href);
            url.searchParams.set('group', group.value);
            window.location.assign(url.toString());
        });
        group.dataset.initial = group.value;
        form.querySelector('[data-vet-add-product-condition]')?.addEventListener('click', () => {
            if (conditions.children.length >= 200) return;
            const row = conditions.firstElementChild.cloneNode(true);
            row.querySelectorAll('input, select').forEach(input => { input.value = ''; });
            conditions.append(row); dirty = true;
        });
        conditions?.addEventListener('click', event => {
            if (!event.target.closest('[data-vet-remove-product-condition]')) return;
            const row = event.target.closest('tr');
            if (conditions.children.length > 1) row.remove();
            else row.querySelectorAll('input, select').forEach(input => { input.value = ''; });
            dirty = true; showModes();
        });
        showModes();
    });
    const form = document.querySelector('[data-vet-rule]');
    if (!form) return;
    const product = form.querySelector('[name=product]');
    const basis = form.querySelector('[name=dose_basis]');
    const doseUnit = form.querySelector('[name=dose_unit]');
    const unitHelp = form.querySelector('[data-vet-unit-help]');
    const unitWarning = form.querySelector('[data-vet-unit-change]');
    const unitOptions = JSON.parse(document.getElementById('vet-dose-unit-options').textContent);
    const normGroup = form.querySelector('[name=norm_group]');
    const normVariant = form.querySelector('[name=norm_variant]');
    const normGroups = normGroup ? JSON.parse(document.getElementById('vet-norm-groups').textContent) : [];
    const loadedContext = [normVariant?.value, basis.value, doseUnit.value];
    const selectedGroup = () => normGroups.find(group => group.id === normGroup?.value);
    const automatic = () => normGroup && !normVariant.value;
    const contextKey = () => (automatic() ? 'group:' + normGroup.value : product.value) + ':' + basis.value;
    let unitBaseline = [product.value, basis.value, doseUnit.value];
    let clearedRates = false;
    const selections = new Map();
    let unitContext = contextKey();
    const warnAboutUnits = () => {
        const hasRates = [...form.querySelectorAll('[name=rate], [name=condition_rate]')]
            .some(input => input.value.trim() !== '');
        const current = [product.value, basis.value, doseUnit.value];
        if (!hasRates) unitBaseline = current;
        unitWarning.hidden = normGroup ? !clearedRates
            : !hasRates || current.every((value, index) => value === unitBaseline[index]);
    };
    const clearRates = () => {
        const rates = [...form.querySelectorAll('[name=rate], [name=condition_rate], [name=band_amount]')];
        if (rates.some(input => input.value.trim() !== '')) {
            rates.forEach(input => { input.value = ''; });
            clearedRates = true;
        }
        showMode();
    };
    const showUnits = () => {
        selections.set(unitContext, doseUnit.value);
        unitContext = contextKey();
        const choices = automatic() ? selectedGroup()?.auto_units || [] : unitOptions[product.value]?.[basis.value] || [];
        const selected = selections.get(unitContext);
        const nodes = choices.map(([value, label]) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            return option;
        });
        if (!nodes.length) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = product.value ? 'Нет совместимых единиц' : 'Сначала выберите препарат';
            nodes.push(option);
        }
        doseUnit.replaceChildren(...nodes);
        if (choices.some(([value]) => value === selected)) doseUnit.value = selected;
        unitHelp.textContent = !product.value ? 'Сначала выберите препарат.'
            : basis.value === 'product' ? 'Используется основная единица выбранного препарата. Сохранённые единицы старых норм остаются доступными.'
            : choices.length ? 'Доступны только единицы действующего вещества, совместимые с концентрацией препарата.'
            : 'Для расчёта по действующему веществу укажите корректную концентрацию и её тип в карточке препарата.';
        warnAboutUnits();
    };
    const syncSelection = rebuild => {
        const group = selectedGroup();
        if (rebuild) {
            const previous = normVariant.value;
            const choices = [['', 'Автоматически'], ...(group?.variants || []).map(variant => [variant.id, variant.name])];
            normVariant.replaceChildren(...choices.map(([value, label]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = label;
                option.disabled = !value && Boolean(group && !group.auto_units.length);
                return option;
            }));
            normVariant.value = group?.variants.some(variant => variant.id === previous) ? previous : '';
        }
        normVariant.disabled = !group;
        normVariant.required = Boolean(group && !group.auto_units.length);
        product.value = normVariant.value || group?.id || '';
        const forcedBasis = group && automatic() && group.auto_units.length ? group.basis : null;
        basis.querySelectorAll('option').forEach(option => { option.disabled = Boolean(forcedBasis && option.value !== forcedBasis); });
        if (forcedBasis) basis.value = forcedBasis;
        const help = form.querySelector('[data-vet-norm-selection-help]');
        help.textContent = !group ? 'Выберите общее название препарата.'
            : normVariant.value ? 'Будет списываться только выбранный вариант. Основа нормы — по препарату или по действующему веществу.'
            : !group.auto_units.length ? 'Для автоматического выбора нужна концентрация. Укажите её в карточке или выберите конкретный вариант.'
            : group.basis === 'active' ? 'Автоматически: норма по действующему веществу. Сначала расходуются вскрытые упаковки, затем более ранние поступления.'
            : 'Автоматически: расход материала в указанной единице, сначала из вскрытых упаковок, затем по дате поступления.';
    };
    product.addEventListener('change', showUnits);
    basis.addEventListener('change', () => { if (normGroup) clearRates(); showUnits(); });
    doseUnit.addEventListener('change', () => { if (normGroup) clearRates(); warnAboutUnits(); });
    form.addEventListener('input', warnAboutUnits);
    if (normGroup) {
        normGroup.addEventListener('change', () => { clearRates(); syncSelection(true); showUnits(); });
        normVariant.addEventListener('change', () => { clearRates(); syncSelection(false); showUnits(); });
        syncSelection(true);
        unitContext = contextKey();
    }
    showUnits();
    const mode = form.querySelector('[data-vet-rule-mode]');
    const rows = form.querySelector('[data-vet-condition-rows]');
    const showMode = () => {
        const conditional = [...rows.querySelectorAll('input')].some(input => input.value !== '');
        const rate = form.querySelector('[name=rate]');
        rate.disabled = conditional || mode.value === 'bands';
        rate.required = !rate.disabled;
        form.querySelector('[data-vet-rate]').hidden = rate.disabled;
        const step = form.querySelector('[name=weight_step]');
        step.disabled = mode.value !== 'step';
        step.required = !step.disabled;
        form.querySelector('[data-vet-step]').hidden = step.disabled;
    };
    mode.addEventListener('change', showMode);
    rows.addEventListener('input', showMode);
    form.querySelector('[data-vet-add-condition]')?.addEventListener('click', () => {
        if (rows.children.length >= 50) return;
        const row = rows.firstElementChild.cloneNode(true);
        row.querySelectorAll('input').forEach(input => { input.value = ''; });
        rows.append(row);
    });
    rows.addEventListener('click', event => {
        if (!event.target.closest('[data-vet-remove-condition]')) return;
        if (rows.children.length > 1) event.target.closest('tr').remove();
        else event.target.closest('tr').querySelectorAll('input').forEach(input => { input.value = ''; });
        showMode();
    });
    showMode();
    if (normGroup && ((loadedContext[0] && loadedContext[0] !== normVariant.value)
        || loadedContext[1] !== basis.value || (loadedContext[2] && loadedContext[2] !== doseUnit.value))) {
        clearRates();
        warnAboutUnits();
    }
})();
