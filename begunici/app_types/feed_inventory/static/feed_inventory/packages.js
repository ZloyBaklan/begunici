(() => {
    'use strict';
    document.querySelectorAll('[data-package-row]').forEach(row => {
        if (row.dataset.packageBound) return;
        row.dataset.packageBound = '1';
        const weight = row.querySelector('[data-package-weight]');
        const count = row.querySelector('[data-package-count]');
        const total = row.querySelector('[data-package-total]');
        if (!weight || !count || !total) return;
        const update = () => {
            const calculate = Number(weight.value) > 0 && Number(count.value) > 0;
            total.readOnly = calculate;
            if (calculate) total.value = String(Math.round(Number(weight.value) * Number(count.value) * 1000) / 1000);
        };
        weight.addEventListener('input', update);
        count.addEventListener('input', update);
        update();
    });
})();
