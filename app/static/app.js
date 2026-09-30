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
    const coving = type.value === 'COVING';
    const cabinet = type.value === 'CABINET';
    const stair = type.value === 'PANELLING_STAIR_HALF' || type.value === 'DADO_STAIR';
    for (const option of finish.options) {
      option.disabled = option.dataset.family !== (dado ? 'dado' : 'panelling') ||
        (type.value === 'PANELLING_FULL' && option.value.includes('ledge')) ||
        (dado && !['Dado','Dado Squares Bottom'].includes(option.value));
    }
    if (finish.selectedOptions[0]?.dataset.family !== (dado ? 'dado' : 'panelling') || (type.value === 'PANELLING_FULL' && finish.value.includes('ledge')) || coving) finish.value = dado ? 'Dado' : 'plain';
    const show = (selector, visible) => form.querySelectorAll(selector).forEach(el => el.hidden = !visible);
    form.querySelector('.measurement-panel:not(.cabinet-fields)').hidden = cabinet;
    show('.cabinet-fields', cabinet);
    show('.stair-fields', stair && !coving && !cabinet);
    show('.mdf-stair-note', !dado && !coving && !cabinet);
    show('.bead-fields', !dado && !coving && !cabinet && finish.value.includes('bead'));
    show('.ledge-fields', !dado && !coving && !cabinet && finish.value.includes('ledge'));
    show('.dado-toggle-fields', !dado && !coving && !cabinet);
    show('.rail-fields', !coving && !cabinet && (dado || form.elements.dado_enabled.checked));
    show('.dado-gap-fields', dado && finish.value !== 'Dado');
    show('.dado-layout-fields', dado && finish.value !== 'Dado');
    show('.dado-top-fields', finish.value.includes('Top & Bottom'));
    show('.dado-inner-fields', finish.value.includes('Double'));
    form.querySelector('.subtype-field').hidden = coving || cabinet;
    show('.coving-fields', coving);
    for (const name of ['slat_width','mdf_id']) form.elements[name].closest('label').hidden = dado || coving || cabinet;
    for (const name of ['height','horizontal_squares','vertical_squares']) form.elements[name].closest('label').hidden = dado || coving || cabinet;
    const use = stair ? 'stair_dado' : 'continuous_dado';
    for (const option of form.elements.dado_rail_id.options) option.disabled = !!option.value && !option.dataset.uses.split(' ').includes(use);

  }
  type.addEventListener('change',update); finish.addEventListener('change',update); form.elements.dado_enabled.addEventListener('change',update); update();
  function updateCabinet() {
    const preset = form.elements.cabinet_preset.value;
    const top = ['window_seat','bench'].includes(preset) ||
      (preset === 'custom' && form.elements.construction_mode.value === 'top');
    const show = (selector, visible) => form.querySelectorAll(selector).forEach(el => el.hidden = !visible);
    show('.cabinet-custom', preset === 'custom');
    show('.cabinet-front', !top);
    show('.cabinet-top', top);
    show('.cabinet-sheet-worktop', !top && form.elements.worktop_type.value === 'sheet');
    show('.cabinet-pse-worktop', !top && form.elements.worktop_type.value === 'pse');
    show('.cabinet-shaker', !top && form.elements.door_style.value === 'shaker');
    show('.cabinet-flat-bead', !top && form.elements.door_style.value === 'flat' && !!form.elements.door_bead_id.value);
    show('.cabinet-feet', form.elements.base_type.value === 'legs');
  }
  form.elements.cabinet_preset.addEventListener('change', () => {
    const seat = ['window_seat','bench'].includes(form.elements.cabinet_preset.value);
    const custom = form.elements.cabinet_preset.value === 'custom';
    form.elements.construction_mode.value = seat ? 'top' : 'front';
    form.elements.top_rails.checked = !seat;
    form.elements.full_top.checked = seat;
    form.elements.face_frame.checked = !seat && !custom;
    form.elements.worktop_type.value = !seat && !custom ? 'sheet' : 'none';
    updateCabinet();
  });
  for (const name of ['construction_mode','worktop_type','door_style','door_bead_id','base_type']) {
    form.elements[name].addEventListener('change', updateCabinet);
  }
  updateCabinet();
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
