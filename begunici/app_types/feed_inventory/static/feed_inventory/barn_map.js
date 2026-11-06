/* Independent map extension: existing placement and animal handlers are unchanged. */
(() => {
    'use strict';
    const config = document.getElementById('barn-feed-bridge');
    const list = document.getElementById('barns-list');
    if (!config || !list) return;
    const element = (tag, text, className) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(className)e.className=className; return e; };
    const qty = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits:3});
    let data;
    const decorate = () => list.querySelectorAll('.barn-selector-card').forEach(card => {
            if (!data) return;
            if(card.dataset.feedBound) return;
            const n=Number(card.querySelector('h3')?.textContent.match(/\d+/)?.[0]);
            const item=data.barns.find(b=>b.barn===n);
            if(!item) return;
            card.dataset.feedBound='1';
            const area=element('section', undefined, 'bf-map');
            area.append(element('strong', `${item.heads} голов · корма`));
            const flow=element('div', undefined, 'bf-map-flow');
            flow.append(element('span',`Прибыло ${item.weekly.arrived}`),element('span',`Переведено ${item.weekly.transferred}`),element('span',`Убыло ${item.weekly.left}`));
            area.append(element('small',`За ${item.weekly.from}–${item.weekly.to}`),flow);
            const table=element('table'); const head=element('tr');
            ['Тип','Норма / месяц','Остаток'].forEach(t=>head.append(element('th',t)));table.append(head);
            item.rows.filter(row=>Number(row.monthly)>0).forEach(row=>{ const tr=element('tr');[row.name,`${qty(row.monthly)} ${row.unit}`,`${qty(row.balance)} ${row.unit}`].forEach(t=>tr.append(element('td',t)));table.append(tr); });
            area.append(table);card.append(area);
    });
    const refresh = async () => {
        try {
            const response = await fetch(config.dataset.url, {credentials:'same-origin'});
            if (!response.ok) throw new Error('Не удалось обновить кормовую сводку. Обновите карту.');
            data = await response.json();
            config.replaceChildren();
            list.querySelectorAll('.barn-selector-card').forEach(card => { card.querySelector('.bf-map')?.remove(); delete card.dataset.feedBound; });
            decorate();
        } catch (error) { config.replaceChildren(element('p', error.message, 'text-warning')); }
    };
    new MutationObserver(decorate).observe(list,{childList:true,subtree:true});
    document.addEventListener('barn-feed-updated', refresh);
    refresh();
})();
