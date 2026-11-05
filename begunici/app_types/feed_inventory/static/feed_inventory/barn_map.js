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
            flow.append(element('span',`Прибыло ${item.weekly.arrived}`),element('span',`Убыло ${item.weekly.left}`),element('span',`Между отсеками ${item.weekly.transferred}`));
            area.append(element('small',`За ${item.weekly.from}–${item.weekly.to}`),flow);
            const table=element('table'); const head=element('tr');
            ['Тип','Норма / сутки','Учёт / оценка*'].forEach(t=>head.append(element('th',t)));table.append(head);
            item.rows.forEach(row=>{ const tr=element('tr');[row.name,`${qty(row.daily)} ${row.unit}`,`${qty(row.balance)} / ~${qty(row.estimate)} ${row.unit}`].forEach(t=>tr.append(element('td',t)));table.append(tr); });
            area.append(table,element('small',`*Учётный остаток / оценка по норме с ${item.estimate_from}. Факт — после сверки.`));
            const details=element('details');details.addEventListener('click',event=>event.stopPropagation());
            details.append(element('summary','Расход по группам животных'));
            item.groups.forEach(group=>{ const block=element('p');block.append(element('strong',`${group.label} · ${group.count} голов`));
                block.append(element('div',group.cells.filter(c=>Number(c.daily)>0).map(c=>`${c.product_name}: ${qty(c.daily)} / сутки`).join('; ')));details.append(block); });
            area.append(details);
            if(item.unclassified||item.missing) area.append(element('p',`Без группы: ${item.unclassified}; незаполненных норм: ${item.missing}.`,'text-warning'));
            const link=element('a','Остатки и поставка','btn btn-outline-primary btn-sm');link.href=config.dataset.base+n+'/';link.addEventListener('click',event=>event.stopPropagation());area.append(link);card.append(area);
        });
        new MutationObserver(decorate).observe(list,{childList:true,subtree:true});decorate();
    }).catch(error=>{ const notice=element('p',error.message,'text-warning');config.append(notice); });
})();
