// Stable text entry lives beside the SVG, never inside a render() replacement.
// var deliberately allows the app's first render before this module initializes.
var previewEditorState = {
  editing: false,
  composing: false,
  finishAfterComposition: false,
  pendingExternal: null,
  lastSyncedText: null,
  selection: null
};
const PREVIEW_TEXT_LIMIT = 20000;

function previewEditorSelection() {
  const field = $('reading-editor');
  return {
    start: field.selectionStart ?? field.value.length,
    end: field.selectionEnd ?? field.value.length,
    direction: field.selectionDirection || 'none',
    top: field.scrollTop || 0,
    left: field.scrollLeft || 0
  };
}

function setPreviewEditorText(text, selection = previewEditorSelection()) {
  const field = $('reading-editor');
  if (field.value === text) return;
  field.value = text;
  // External edits/reset/import may shorten the text. Keep the current range
  // where possible, clamping only to the new length, and do not move focus.
  field.setSelectionRange?.(Math.min(selection.start, text.length), Math.min(selection.end, text.length), selection.direction);
  field.scrollTop = selection.top;
  field.scrollLeft = selection.left;
}

function syncPreviewEditor(forceExternal = false) {
  if (!previewEditorState) return;
  const state = previewEditorState, field = $('reading-editor'), source = $('sample').value;
  $('reading-editor-region').hidden = !state.editing;
  $('finish-preview-edit').hidden = !state.editing;
  $('edit-preview').hidden = state.editing;
  $('preview-edit-hint').hidden = state.editing;
  $('reading-shell').classList.toggle('editing', state.editing);
  $('reading').setAttribute('aria-expanded', String(state.editing));
  $('edit-preview').setAttribute('aria-expanded', String(state.editing));
  if (forceExternal || source !== state.lastSyncedText || (state.composing && state.pendingExternal !== null)) {
    if (state.composing) {
      // Explicit resets/imports are deferred until the IME commits, rather
      // than replacing an active composition and destroying its caret.
      state.pendingExternal = source;
    } else {
      setPreviewEditorText(source);
      state.lastSyncedText = source;
    }
  }
  // No value assignment on ordinary glyph/style/dock renders. The input DOM
  // node, selection, scroll position, focus, and native undo stack survive.
}

// Reset/import are actions, not merely changed values. Call this after
// replacing #sample.value and before render(), even if the value is unchanged.
// During composition this queues the explicit replacement instead of allowing
// the later IME commit to overwrite it.
function notifyPreviewTextReplacement() {
  syncPreviewEditor(true);
}

function beginPreviewEditing() {
  const state = previewEditorState, field = $('reading-editor');
  if (!state.editing) {
    state.editing = true;
    syncPreviewEditor();
    render();
  }
  field.focus({preventScroll: true});
  if (state.selection) {
    const {start, end, direction, top, left} = state.selection;
    field.setSelectionRange?.(Math.min(start, field.value.length), Math.min(end, field.value.length), direction);
    field.scrollTop = top; field.scrollLeft = left;
    state.selection = null;
  }
}

function publishPreviewEditor() {
  const state = previewEditorState, field = $('reading-editor');
  if (state.composing) return;
  if (field.value.length > PREVIEW_TEXT_LIMIT) setPreviewEditorText(field.value.slice(0, PREVIEW_TEXT_LIMIT));
  if ($('sample').value !== field.value) $('sample').value = field.value;
  state.lastSyncedText = field.value;
  render();
}

function finishPreviewEditing() {
  const state = previewEditorState;
  if (state.composing) { state.finishAfterComposition = true; return; }
  publishPreviewEditor();
  state.selection = previewEditorSelection();
  state.editing = false;
  syncPreviewEditor();
  render();
  $('edit-preview').focus({preventScroll: true});
}

$('sample').maxLength = PREVIEW_TEXT_LIMIT;
$('reading-editor').maxLength = PREVIEW_TEXT_LIMIT;
$('reading-editor').addEventListener('input', event => {
  if (!event.isComposing && !previewEditorState.composing) publishPreviewEditor();
});
$('reading-editor').addEventListener('compositionstart', () => {
  previewEditorState.composing = true;
});
$('reading-editor').addEventListener('compositionend', () => {
  const state = previewEditorState;
  state.composing = false;
  if (state.pendingExternal !== null) {
    setPreviewEditorText(state.pendingExternal);
    $('sample').value = state.pendingExternal;
    state.pendingExternal = null;
  }
  publishPreviewEditor();
  if (state.finishAfterComposition) {
    state.finishAfterComposition = false;
    finishPreviewEditing();
  }
});
$('reading-editor').addEventListener('keydown', event => {
  // An IME's Enter/Escape belongs to the composition, not the editor toolbar.
  if (event.isComposing || previewEditorState.composing || event.keyCode === 229) return;
  if (event.key === 'Escape' || (event.key === 'Enter' && (event.ctrlKey || event.metaKey))) {
    event.preventDefault();
    finishPreviewEditing();
  }
});
$('reading').addEventListener('click', beginPreviewEditing);
$('reading').addEventListener('keydown', event => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    beginPreviewEditing();
  }
});
$('edit-preview').addEventListener('click', beginPreviewEditing);
$('finish-preview-edit').addEventListener('click', finishPreviewEditing);
syncPreviewEditor();
