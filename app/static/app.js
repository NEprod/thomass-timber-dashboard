'use strict';
let dirtyForm = null;
for (const form of document.querySelectorAll('form[data-dirty]')) {
  form.addEventListener('input', () => {
    form.classList.add('is-dirty');
    dirtyForm = form;
    document.body.classList.add('has-unsaved');
    document.querySelectorAll('.unsaved').forEach(el => el.hidden = false);
  });
}
for (const form of document.querySelectorAll('form')) {
  form.addEventListener('submit', event => {
    const dirty = [...document.querySelectorAll('form.is-dirty')];
    if (dirty.some(other => other !== form) && !confirm('Other sections have unsaved changes. Continue and discard those changes?')) {
      event.preventDefault(); return;
    }
    if (form.dataset.confirm && !confirm(form.dataset.confirm)) { event.preventDefault(); return; }
    dirtyForm = null;
  });
}
window.addEventListener('beforeunload', event => {
  if (dirtyForm) { event.preventDefault(); event.returnValue = ''; }
});
for (const form of document.querySelectorAll('.item-form')) {
  const type = form.elements.type, finish = form.elements.subtype;
  function update() {
    const stair = type.value === 'PANELLING_STAIR_HALF';
    form.querySelectorAll('.stair-fields').forEach(el => el.hidden = !stair);
    for (const option of finish.options) option.disabled = type.value === 'PANELLING_FULL' && option.value.includes('ledge');
    if (finish.selectedOptions[0]?.disabled) finish.value = 'plain';
    form.querySelectorAll('.bead-fields').forEach(el => el.hidden = !finish.value.includes('bead'));
    form.querySelectorAll('.ledge-fields').forEach(el => el.hidden = !finish.value.includes('ledge'));
  }
  type.addEventListener('change',update); finish.addEventListener('change',update); update();
  form.elements.ledge_choice.addEventListener('change', () => {
    const multiplier = {'2x':2,'3x':3}[form.elements.ledge_choice.value];
    if (multiplier) form.elements.ledge_width.value = Number(form.elements.mdf_id.selectedOptions[0].dataset.thickness)*multiplier;
  });
}
