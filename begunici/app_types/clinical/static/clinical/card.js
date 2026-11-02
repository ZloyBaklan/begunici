(() => {
  const checkbox=document.getElementById('is_in_treatment');
  if(!checkbox?.dataset.finishUrl)return;
  checkbox.addEventListener('change',()=>{
    if(checkbox.checked)return;
    checkbox.checked=true;
    if(confirm('Чтобы снять назначение «Лечение», нужно подтвердить исход болезни и расход препаратов. Перейти к завершению лечения?'))location.href=checkbox.dataset.finishUrl;
  });
})();
