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
    saveQuoteContext(form);
    dirtyForm = null;
  });
}
window.addEventListener('beforeunload', event => {
  if (dirtyForm) { event.preventDefault(); event.returnValue = ''; }
});
for (const form of document.querySelectorAll('.item-form')) {
  const type = form.elements.type, finish = form.elements.subtype;
  function update() {
    const dado = type.value.startsWith('DADO_');
    const stair = type.value === 'PANELLING_STAIR_HALF' || type.value === 'DADO_STAIR';
    for (const option of finish.options) {
      option.disabled = option.dataset.family !== (dado ? 'dado' : 'panelling') ||
        (type.value === 'PANELLING_FULL' && option.value.includes('ledge')) ||
        (dado && !['Dado','Dado Squares Bottom'].includes(option.value));
    }
    if (finish.selectedOptions[0]?.dataset.family !== (dado ? 'dado' : 'panelling') || (type.value === 'PANELLING_FULL' && finish.value.includes('ledge'))) finish.value = dado ? 'Dado' : 'plain';
    const show = (selector, visible) => form.querySelectorAll(selector).forEach(el => el.hidden = !visible);
    show('.stair-fields', stair);
    show('.mdf-stair-note', !dado);
    show('.bead-fields', !dado && finish.value.includes('bead'));
    show('.ledge-fields', !dado && finish.value.includes('ledge'));
    show('.dado-toggle-fields', !dado);
    show('.rail-fields', dado || form.elements.dado_enabled.checked);
    show('.dado-gap-fields', dado && finish.value !== 'Dado');
    show('.dado-layout-fields', dado && finish.value !== 'Dado');
    show('.dado-top-fields', finish.value.includes('Top & Bottom'));
    show('.dado-inner-fields', finish.value.includes('Double'));
    for (const name of ['slat_width','mdf_id']) form.elements[name].closest('label').hidden = dado;
    for (const name of ['height','horizontal_squares','vertical_squares']) form.elements[name].closest('label').hidden = dado;
    const use = stair ? 'stair_dado' : 'continuous_dado';
    for (const option of form.elements.dado_rail_id.options) option.disabled = !!option.value && !option.dataset.uses.split(' ').includes(use);

  }
  type.addEventListener('change',update); finish.addEventListener('change',update); form.elements.dado_enabled.addEventListener('change',update); update();
  form.elements.ledge_choice.addEventListener('change', () => {
    const multiplier = {'2x':2,'3x':3}[form.elements.ledge_choice.value];
    if (multiplier) form.elements.ledge_width.value = Number(form.elements.mdf_id.selectedOptions[0].dataset.thickness)*multiplier;
  });
}

// Save only UI context, never measurements, credentials or quotation data.
const quoteContextKey = 'timber:quote-context:' + window.location.pathname;
let lastFocusedField = null;
document.addEventListener('focusin', event => {
  if (event.target.matches('.item-form input:not([type="hidden"]), .item-form select, .item-form textarea')) {
    lastFocusedField = {item: event.target.closest('.work-item').id, name: event.target.name};
  }
});
function saveQuoteContext(form) {
  if (!document.querySelector('.work-item')) return;
  const item = form.closest('.work-item');
  const state = {at: Date.now(), y: window.scrollY,
    open: [...document.querySelectorAll('details[id][open]')].map(el => el.id),
    item: item?.id, top: item?.getBoundingClientRect().top, focus: lastFocusedField};
  if (item && !state.open.includes(item.id)) state.open.push(item.id);
  try { sessionStorage.setItem(quoteContextKey, JSON.stringify(state)); } catch (_) { /* redirect anchor remains */ }
}
function restoreQuoteContext() {
  let state;
  try {
    state = JSON.parse(sessionStorage.getItem(quoteContextKey));
    sessionStorage.removeItem(quoteContextKey);
  } catch (_) { /* private storage can be disabled */ }
  if (state && Date.now() - state.at < 10 * 60 * 1000) {
    history.scrollRestoration = 'manual';
    document.querySelectorAll('details[id]').forEach(el => el.open = state.open.includes(el.id));
    const item = document.getElementById(state.item);
    if (item) item.open = true;
    const focusItem = document.getElementById(state.focus?.item);
    const field = focusItem?.querySelector('form.item-form')?.elements.namedItem(state.focus?.name);
    if (field && !field.closest('[hidden]')) field.focus({preventScroll: true});
    requestAnimationFrame(() => requestAnimationFrame(() => {
      window.scrollTo(0, item ? window.scrollY + item.getBoundingClientRect().top - state.top : state.y);
      history.scrollRestoration = 'auto';
    }));
  } else if (/^#item-\d+$/.test(location.hash)) {
    const item = document.getElementById(location.hash.slice(1));
    if (item) { item.open = true; item.scrollIntoView(); }
  }
}
if (document.readyState === 'complete') restoreQuoteContext();
else window.addEventListener('load', restoreQuoteContext, {once: true});
