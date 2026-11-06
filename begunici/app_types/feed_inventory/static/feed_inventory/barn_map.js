/* Independent map extension: existing placement and animal handlers are unchanged. */
(() => {
    'use strict';
    const config = document.getElementById('barn-feed-bridge');
    const list = document.getElementById('barns-list');
    if (!config || !list) return;
    const element = (tag, text, className) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(className)e.className=className; return e; };
    const qty = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits:3});
    fetch(config.dataset.url, {credentials:'same-origin'}).then(async response => {
        if (!response.ok) throw new Error('Не удалось загрузить кормовую сводку');
        const data=await response.json();
        const decorate = () => list.querySelectorAll('.barn-selector-card').forEach(card => {
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
        new MutationObserver(decorate).observe(list,{childList:true,subtree:true});decorate();
    }).catch(error=>{ const notice=element('p',error.message,'text-warning');config.append(notice); });
})();
