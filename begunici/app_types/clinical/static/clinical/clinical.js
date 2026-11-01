(() => {
  'use strict';
  const read = id => {const el=document.getElementById(id);return el?JSON.parse(el.textContent):[];};
  const products=read('clinical-products');
  const error=document.getElementById('clinical-error');
  const showError=message=>{error.textContent=typeof message==='string'?message:JSON.stringify(message);error.hidden=false;error.scrollIntoView({behavior:'smooth',block:'center'});};
  document.getElementById('clinical-select-all')?.addEventListener('change', e=>document.querySelectorAll('.clinical-selected').forEach(el=>el.checked=e.target.checked));
  document.getElementById('clinical-bulk-care')?.addEventListener('click',()=>{
    const ids=[...document.querySelectorAll('.clinical-selected:checked')].map(el=>el.value);
    if(!ids.length){showError('Выберите животных в журнале.');return;}
    location.href='/animals/treatment/care/?episodes='+ids.join(',');
  });
  function addLine(form, initial={}) {
    const row=document.createElement('tr');
    const productCell=row.insertCell();
    const search=document.createElement('input');search.type='search';search.className='form-control form-control-sm mb-1';search.placeholder='Поиск препарата';search.setAttribute('aria-label','Поиск препарата');
    const select=document.createElement('select');select.className='form-select';select.required=true;select.dataset.product='';select.setAttribute('aria-label','Препарат / материал');
    select.add(new Option('Выберите препарат / материал',''));
    for(const product of products){const option=new Option(`${product.name} · остаток ${product.available} ${product.unit}`,String(product.id));select.add(option);}
    select.value=String(initial.product||'');productCell.append(search,select);
    search.addEventListener('input',()=>{const q=search.value.toLocaleLowerCase();[...select.options].forEach(option=>option.hidden=!!option.value&&option.value!==select.value&&!option.text.toLocaleLowerCase().includes(q));});
    const quantity=document.createElement('input');quantity.type='number';quantity.className='form-control';quantity.min='0';quantity.step='0.001';quantity.value=initial.amount||'';quantity.required=true;quantity.dataset.amount='';quantity.setAttribute('aria-label','Количество');row.insertCell().append(quantity);
    const unit=row.insertCell();
    const updateUnit=()=>{unit.textContent=products.find(p=>String(p.id)===select.value)?.unit||'—';updateTotal(form);};select.addEventListener('change',updateUnit);quantity.addEventListener('input',()=>updateTotal(form));updateUnit();
    const remove=document.createElement('button');remove.type='button';remove.className='btn btn-sm btn-outline-danger';remove.textContent='×';remove.setAttribute('aria-label','Убрать препарат');remove.addEventListener('click',()=>{row.remove();updateTotal(form);});row.insertCell().append(remove);
    form.querySelector('[data-clinical-lines]').append(row);updateTotal(form);
  }
  function getLines(form){return [...form.querySelectorAll('[data-clinical-lines] tr')].map(row=>({product:row.querySelector('[data-product]').value,amount:row.querySelector('[data-amount]').value,packages:'0'}));}
  function updateTotal(form){
    const output=form.querySelector('[data-clinical-total]');if(!output)return;
    const count=form.querySelectorAll('[data-episode-id]').length;
    const perHead=form.elements.mode?.value==='head';
    const totals=[...form.querySelectorAll('[data-clinical-lines] tr')].map(row=>{const p=products.find(p=>String(p.id)===row.querySelector('[data-product]').value);const amount=Number(row.querySelector('[data-amount]').value)*(perHead?count:1);return p?`${p.name}: ${amount.toLocaleString('ru-RU',{maximumFractionDigits:3})} ${p.unit}`:'';}).filter(Boolean);
    output.textContent=totals.length?'Итого на выбранных животных: '+totals.join('; '):'';
  }
  document.querySelectorAll('[data-clinical-form]').forEach(form=>{
    const kind=form.dataset.clinicalForm;
    if(form.querySelector('[data-clinical-lines]')){
      const initial=kind==='close'?read('clinical-totals'):[];
      initial.forEach(line=>addLine(form,line));
      form.querySelector('[data-clinical-add-line]').addEventListener('click',()=>addLine(form));
      form.elements.mode?.addEventListener('change',()=>updateTotal(form));
    }
    const status=form.querySelector('[data-clinical-status]');
    function toggleArchive(){
      const fieldset=form.querySelector('[data-clinical-archive]');if(!fieldset)return;
      const selected=status.selectedOptions[0];const archived=selected?.dataset.archive==='1';fieldset.hidden=!archived;fieldset.disabled=!archived;
      fieldset.querySelectorAll('[data-archive-required]').forEach(el=>el.required=archived);
      const death=archived&&selected.textContent.trim()==='Падеж';const deathLabel=fieldset.querySelector('[data-death-reason]');deathLabel.hidden=!death;deathLabel.querySelector('select').required=death;deathLabel.querySelector('select').disabled=!death;
    }
    status?.addEventListener('change',toggleArchive);toggleArchive();
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(form.dataset.saving)return;
      const data=Object.fromEntries(new FormData(form));
      if(kind==='care')data.episodes=[...form.querySelectorAll('[data-episode-id]')].map(el=>({id:el.dataset.episodeId,revision:el.dataset.revision}));
      if(kind==='care'||kind==='close')data.lines=getLines(form);
      data.confirm_status=!!form.elements.confirm_status?.checked;
      data.confirm_expense=!!form.elements.confirm_expense?.checked;
      data.confirm_group_move=!!form.elements.confirm_group_move?.checked;
      if(kind==='close')data.archive=Object.fromEntries(Object.entries(data).filter(([key])=>key.startsWith('archive_')||key==='carcass_weight'));
      const button=form.querySelector('button[type=submit],button:not([type])');form.dataset.saving='1';if(button)button.disabled=true;error.hidden=true;
      try{const response=await fetch(form.dataset.url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw new Error(typeof result.error==='string'?result.error:JSON.stringify(result.error||result));location.href=result.url;}
      catch(exc){showError(exc.message);delete form.dataset.saving;if(button)button.disabled=false;}
    });
  });
  if(new URLSearchParams(location.search).get('finish'))document.getElementById('finish')?.scrollIntoView();
})();
