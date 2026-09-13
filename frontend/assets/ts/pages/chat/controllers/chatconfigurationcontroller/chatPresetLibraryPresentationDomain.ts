/* SoAI - Chat preset library collection and editor presentation [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isChatPresetNameValid } from '@core/api/contracts/webuiChatPresetContracts.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { createSearchTextIndex, matchesSearchFilterQuery } from '@core/search/searchQuery.ts';
import { CHAT_ACTIONS, CHAT_CONFIGURATION_MODAL_ID, CHAT_PRESET_SECTION_DEFINITIONS, translateChatPresetSection, type ChatPresetSectionId } from '@features/chat/public.ts';
import type { WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import type { ChatPresetEditorDraft, ChatPresetLibraryViewState, ChatPresetSectionChoice } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { createIconSlot, setIconSlot } from '@core/ui/icons/view.ts';
import { checkerboardService, dom } from '@core/dom/dom.ts';
import { captureChatPresetLibraryFocus, focusChatPresetEditorTransition, readChatPresetEditorFocusTarget, restoreChatPresetLibraryFocus } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryFocusDomain.ts';
import { renderChatPresetStatus } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetStatusPresentationDomain.ts';

const CHAT_PRESET_ROW_SELECTOR = '.chat-preset-row';

const resolveElement = (root: Element, token: string): HTMLElement => {
    const element = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, token), root);
    if (!(element instanceof HTMLElement)) throw new Error(`Chat preset library is missing ${token}.`);
    return element;
};

const hydrateStaticIcons = (root: Element): void => {
    setIconSlot(resolveElement(root, 'preset-search-icon'), getIconSync('search', { size: 16, strokeWidth: 1.5 }), { className: 'searchbar-icon' });
    setIconSlot(resolveElement(root, 'preset-add-icon'), getIconSync('add', { size: 16, strokeWidth: 1.7 }));
};

type PresetRowActionPresentation = Readonly<{ className: string; icon: IconName; strokeWidth: number }>;

const presetRowActionPresentation = (action: string): PresetRowActionPresentation | null => {
    if (action === CHAT_ACTIONS.REMOVE_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--delete', icon: 'close', strokeWidth: 1.5 };
    if (action === CHAT_ACTIONS.REPLACE_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--settings ui-round-button--modal-close', icon: 'replace', strokeWidth: 1.5 };
    if (action === CHAT_ACTIONS.RENAME_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--edit', icon: 'rename', strokeWidth: 1 };
    if (action === CHAT_ACTIONS.APPLY_PRESET) return { className: 'ui-round-button ui-round-button--inline ui-round-button--success chat-preset-apply-action', icon: 'play', strokeWidth: 1.5 };
    return null;
};

const createButton = (documentValue: Document, action: string, label: string, presetId: string | null, disabled: boolean): HTMLButtonElement => {
    const button = documentValue.createElement('button');
    button.type = 'button';
    const rowPresentation = presetRowActionPresentation(action);
    button.className = rowPresentation ? rowPresentation.className : action === CHAT_ACTIONS.SUBMIT_PRESET_EDITOR ? 'ui-button ui-variant-accent' : action === CHAT_ACTIONS.CANCEL_PRESET_EDITOR ? 'ui-button ui-variant-neutral' : 'ui-button ui-button--sm';
    button.dataset['action'] = action;
    if (presetId) button.dataset['presetId'] = presetId;
    button.disabled = disabled;
    button.dataset['presetBaseDisabled'] = disabled ? 'true' : 'false';
    button.setAttribute('aria-label', label);
    button.dataset['tooltip'] = label;
    if (rowPresentation) button.append(createIconSlot(documentValue, getIconSync(rowPresentation.icon, { strokeWidth: rowPresentation.strokeWidth })));
    else button.textContent = label;
    return button;
};

const renderBadges = (record: WebuiChatPresetRecord, container: HTMLElement): void => {
    for (const definition of CHAT_PRESET_SECTION_DEFINITIONS) {
        if (!(definition.id in record.sections)) continue;
        const badge = container.ownerDocument.createElement('span');
        badge.className = 'settings-record-badge';
        badge.textContent = translateChatPresetSection(definition.id);
        container.append(badge);
    }
};

const createPresetRow = (record: WebuiChatPresetRecord, state: ChatPresetLibraryViewState, documentValue: Document): HTMLElement => {
    const row = documentValue.createElement('article');
    row.className = 'collection-list-item chat-preset-row glass-surface-interactive';
    row.setAttribute('role', 'listitem');
    if (!record.applicable) row.classList.add('is-unavailable');
    row.dataset['presetId'] = record.id;
    const info = documentValue.createElement('div');
    info.className = 'collection-list-item-main';
    const title = documentValue.createElement('h3');
    title.className = 'collection-list-item-title';
    title.textContent = record.name;
    const meta = documentValue.createElement('div');
    meta.className = 'collection-list-item-meta';
    meta.textContent = i18n.t('chat.configuration.presetLibrary.modifiedAt', { value: formatDateTime(record.modifiedAtMs, false) });
    const badges = documentValue.createElement('div');
    badges.className = 'chat-preset-badges';
    renderBadges(record, badges);
    info.append(title, meta, badges);
    if (record.omittedSettingsCount > 0) {
        const warning = documentValue.createElement('div');
        warning.className = 'chat-configuration-hint is-warning';
        warning.textContent = i18n.t('chat.configuration.presetLibrary.omittedSettings', { count: record.omittedSettingsCount });
        info.append(warning);
    }
    if (!record.applicable) {
        const unavailable = documentValue.createElement('div');
        unavailable.className = 'chat-configuration-hint';
        unavailable.textContent = i18n.t('chat.configuration.presetLibrary.notApplicable');
        info.append(unavailable);
    }
    const actions = documentValue.createElement('div');
    actions.className = 'ui-collection-list__actions chat-preset-row-actions';
    const revisionsBlocked = state.stale;
    actions.append(createButton(documentValue, CHAT_ACTIONS.REMOVE_PRESET, i18n.t('common.delete'), record.id, revisionsBlocked), createButton(documentValue, CHAT_ACTIONS.RENAME_PRESET, i18n.t('chat.configuration.presetLibrary.renameAction'), record.id, revisionsBlocked), createButton(documentValue, CHAT_ACTIONS.REPLACE_PRESET, i18n.t('chat.configuration.presetLibrary.replaceAction'), record.id, revisionsBlocked), createButton(documentValue, CHAT_ACTIONS.APPLY_PRESET, i18n.t('chat.configuration.presetLibrary.applyAction'), record.id, revisionsBlocked || !record.applicable));
    row.append(info, actions);
    return row;
};

const matchingRecords = (state: ChatPresetLibraryViewState): readonly WebuiChatPresetRecord[] => {
    if (!state.searchQuery) return state.records;
    return state.records.filter((record) => matchesSearchFilterQuery(createSearchTextIndex([record.name]), state.searchQuery));
};

const choiceLabel = (choice: ChatPresetSectionChoice): string => {
    const definition = CHAT_PRESET_SECTION_DEFINITIONS.find((candidate) => candidate.id === choice.id);
    if (!definition) throw new Error(`Unknown chat preset section: ${choice.id}`);
    return translateChatPresetSection(definition.id);
};

const sectionDescription = (sectionId: ChatPresetSectionId): string => {
    if (sectionId === 'general') return i18n.t('chat.configuration.presetLibrary.editor.sectionDescriptions.general');
    if (sectionId === 'appearance') return i18n.t('chat.configuration.presetLibrary.editor.sectionDescriptions.appearance');
    if (sectionId === 'completion') return i18n.t('chat.configuration.presetLibrary.editor.sectionDescriptions.completion');
    if (sectionId === 'voice') return i18n.t('chat.configuration.presetLibrary.editor.sectionDescriptions.voice');
    if (sectionId === 'files') return i18n.t('chat.configuration.presetLibrary.editor.sectionDescriptions.files');
    if (sectionId === 'knowledge') return i18n.t('chat.configuration.presetLibrary.editor.sectionDescriptions.knowledge');
    return i18n.t('chat.configuration.presetLibrary.editor.sectionDescriptions.tools');
};

const editorTitle = (mode: ChatPresetEditorDraft['mode']): string => {
    if (mode === 'create') return i18n.t('chat.configuration.presetLibrary.editor.createTitle');
    if (mode === 'rename') return i18n.t('chat.configuration.presetLibrary.editor.renameTitle');
    return i18n.t('chat.configuration.presetLibrary.editor.replaceTitle');
};

const editorDescription = (mode: ChatPresetEditorDraft['mode']): string => {
    if (mode === 'create') return i18n.t('chat.configuration.presetLibrary.editor.createDescription');
    if (mode === 'rename') return i18n.t('chat.configuration.presetLibrary.editor.renameDescription');
    return i18n.t('chat.configuration.presetLibrary.editor.replaceDescription');
};

const editorActionLabel = (mode: ChatPresetEditorDraft['mode']): string => {
    if (mode === 'create') return i18n.t('chat.configuration.presetLibrary.editor.createAction');
    if (mode === 'rename') return i18n.t('chat.configuration.presetLibrary.editor.renameAction');
    return i18n.t('chat.configuration.presetLibrary.editor.replaceAction');
};

const resolveEditorNameState = (state: ChatPresetLibraryViewState): Readonly<{ showError: boolean; hint: string; submitDisabled: boolean }> => {
    const draft = state.editor;
    if (!draft) throw new Error('Chat preset editor name state requires an editor draft.');
    const valid = isChatPresetNameValid(draft.name);
    const showError = draft.nameConflict || (draft.name.length > 0 && !valid);
    const hint = draft.nameConflict ? i18n.t('chat.configuration.presetLibrary.errors.name_conflict') : showError ? i18n.t('chat.configuration.presetLibrary.editor.nameInvalid') : i18n.t('chat.configuration.presetLibrary.editor.nameHint');
    return { showError, hint, submitDisabled: state.stale || draft.targetUnavailable || draft.reviewRequired || !valid || (draft.mode !== 'rename' && draft.selectedSections.size === 0) };
};

const renderSectionChoice = (choice: ChatPresetSectionChoice, draft: ChatPresetEditorDraft, container: HTMLElement): void => {
    const label = container.ownerDocument.createElement('label');
    label.className = 'chat-preset-section-choice setting-change-surface glass-surface-interactive';
    const input = container.ownerDocument.createElement('input');
    input.type = 'checkbox';
    input.className = 'visually-hidden';
    input.dataset['chatPresetSection'] = choice.id;
    input.checked = draft.selectedSections.has(choice.id);
    input.disabled = !choice.eligible || !choice.hydrated;
    const copy = container.ownerDocument.createElement('span');
    copy.className = 'chat-preset-section-choice-copy';
    const text = container.ownerDocument.createElement('strong');
    text.textContent = choiceLabel(choice);
    const description = container.ownerDocument.createElement('small');
    description.textContent = sectionDescription(choice.id);
    copy.append(text, description);
    label.append(input, copy);
    if (choice.reason) {
        const reason = container.ownerDocument.createElement('small');
        reason.textContent = choice.reason;
        reason.className = 'chat-preset-section-unavailable';
        copy.append(reason);
    }
    container.append(label);
};

const renderEditor = (state: ChatPresetLibraryViewState, editor: HTMLElement): void => {
    editor.replaceChildren();
    const draft = state.editor;
    editor.classList.toggle('u-hidden', draft === null);
    if (!draft) {
        delete editor.dataset['presetEditorMode'];
        delete editor.dataset['presetEditorTargetId'];
        return;
    }
    editor.dataset['presetEditorMode'] = draft.mode;
    if (draft.targetId) editor.dataset['presetEditorTargetId'] = draft.targetId;
    else delete editor.dataset['presetEditorTargetId'];
    const title = editor.ownerDocument.createElement('h3');
    title.textContent = editorTitle(draft.mode);
    const description = editor.ownerDocument.createElement('p');
    description.className = 'chat-preset-editor-description';
    description.textContent = editorDescription(draft.mode);
    const surface = editor.ownerDocument.createElement('div');
    const nameState = resolveEditorNameState(state);
    surface.className = `form-group setting-change-surface${nameState.showError ? ' is-invalid' : ''}`;
    const nameLabel = editor.ownerDocument.createElement('label');
    nameLabel.htmlFor = `${CHAT_CONFIGURATION_MODAL_ID}-preset-editor-name`;
    nameLabel.textContent = i18n.t('chat.configuration.presetLibrary.editor.nameLabel');
    const nameInput = editor.ownerDocument.createElement('input');
    nameInput.id = `${CHAT_CONFIGURATION_MODAL_ID}-preset-editor-name`;
    nameInput.type = 'text';
    nameInput.className = 'form-input';
    nameInput.autocomplete = 'off';
    nameInput.spellcheck = false;
    nameInput.value = draft.name;
    nameInput.dataset['chatPresetEditorName'] = 'true';
    const nameHint = editor.ownerDocument.createElement('small');
    nameHint.id = `${nameInput.id}-hint`;
    nameHint.textContent = nameState.hint;
    nameInput.setAttribute('aria-describedby', nameHint.id);
    nameInput.setAttribute('aria-invalid', nameState.showError ? 'true' : 'false');
    surface.append(nameLabel, nameInput, nameHint);
    editor.append(title, description, surface);
    if (draft.mode !== 'rename') {
        const choices = editor.ownerDocument.createElement('fieldset');
        choices.className = 'chat-preset-section-choices';
        const legend = editor.ownerDocument.createElement('legend');
        legend.textContent = i18n.t('chat.configuration.presetLibrary.editor.sectionsLabel');
        choices.append(legend);
        state.sectionChoices.forEach((choice) => renderSectionChoice(choice, draft, choices));
        const count = editor.ownerDocument.createElement('p');
        count.className = 'ui-chip chat-preset-selection-summary';
        count.textContent = i18n.t('chat.configuration.presetLibrary.editor.selectedCount', { count: draft.selectedSections.size });
        choices.append(count);
        editor.append(choices);
    }
    if (draft.targetUnavailable || draft.reviewRequired) {
        const warning = editor.ownerDocument.createElement('div');
        warning.className = 'chat-configuration-hint is-warning';
        warning.textContent = draft.targetUnavailable ? i18n.t('chat.configuration.presetLibrary.editor.targetUnavailable') : i18n.t('chat.configuration.presetLibrary.editor.revisionChanged');
        editor.append(warning);
        if (draft.reviewRequired && !draft.targetUnavailable) editor.append(createButton(editor.ownerDocument, CHAT_ACTIONS.REVIEW_PRESET_EDITOR, i18n.t('chat.configuration.presetLibrary.editor.reviewAction'), null, false));
    }
    const actions = editor.ownerDocument.createElement('div');
    actions.className = 'chat-configuration-actions';
    actions.append(createButton(editor.ownerDocument, CHAT_ACTIONS.SUBMIT_PRESET_EDITOR, editorActionLabel(draft.mode), null, nameState.submitDisabled), createButton(editor.ownerDocument, CHAT_ACTIONS.CANCEL_PRESET_EDITOR, i18n.t('common.cancel'), null, false));
    editor.append(actions);
};

const syncChatPresetEditorNamePresentation = (root: HTMLElement, state: ChatPresetLibraryViewState): void => {
    if (!state.editor) return;
    const input = dom.resolve('[data-chat-preset-editor-name="true"]', root);
    const submit = dom.resolve(`[data-action="${CHAT_ACTIONS.SUBMIT_PRESET_EDITOR}"]`, root);
    if (!(input instanceof HTMLInputElement) || !(submit instanceof HTMLButtonElement)) throw new Error('Chat preset editor name controls are unavailable.');
    const hint = dom.resolve(`#${input.id}-hint`, root);
    const surface = input.closest('.setting-change-surface');
    if (!(hint instanceof HTMLElement) || !(surface instanceof HTMLElement)) throw new Error('Chat preset editor name presentation is incomplete.');
    const nameState = resolveEditorNameState(state);
    if (input.value !== state.editor.name) input.value = state.editor.name;
    input.setAttribute('aria-invalid', nameState.showError ? 'true' : 'false');
    hint.textContent = nameState.hint;
    surface.classList.toggle('is-invalid', nameState.showError);
    submit.disabled = state.operationPending || nameState.submitDisabled;
    submit.dataset['presetBaseDisabled'] = nameState.submitDisabled ? 'true' : 'false';
};

const applyChatPresetLibraryOperationState = (root: HTMLElement, operationPending: boolean): void => {
    root.toggleAttribute('inert', operationPending);
    const candidate = dom.resolve('.chat-preset-library', root);
    const stateSurface = candidate instanceof HTMLElement ? candidate : root;
    const loading = stateSurface.dataset['chatPresetState'] === 'loading';
    stateSurface.setAttribute('aria-busy', operationPending || loading ? 'true' : 'false');
    for (const element of dom.resolveAll('[data-preset-base-disabled]', root)) {
        if (element instanceof HTMLButtonElement) element.disabled = operationPending || element.dataset['presetBaseDisabled'] === 'true';
    }
};

const renderChatPresetLibrary = (root: HTMLElement, state: ChatPresetLibraryViewState): void => {
    hydrateStaticIcons(root);
    const focus = captureChatPresetLibraryFocus(root);
    const editor = resolveElement(root, 'preset-editor');
    const previousEditor = readChatPresetEditorFocusTarget(editor);
    resolveElement(root, 'preset-toolbar').classList.toggle('u-hidden', state.editor !== null);
    const candidate = dom.resolve('.chat-preset-library', root);
    const stateSurface = candidate instanceof HTMLElement ? candidate : root;
    stateSurface.dataset['chatPresetState'] = state.phase === 'loading' ? 'loading' : state.stale ? 'stale' : state.phase;
    const search = resolveElement(root, 'preset-search');
    if (search instanceof HTMLInputElement && search.value !== state.searchQuery) search.value = state.searchQuery;
    const records = matchingRecords(state);
    renderChatPresetStatus(state, records.length, resolveElement(root, 'preset-status'));
    renderEditor(state, editor);
    const list = resolveElement(root, 'preset-list');
    list.replaceChildren(...records.map((record) => createPresetRow(record, state, root.ownerDocument)));
    checkerboardService.applyCheckerboard(list, CHAT_PRESET_ROW_SELECTOR);
    applyChatPresetLibraryOperationState(root, state.operationPending);
    if (!focusChatPresetEditorTransition(root, previousEditor, state.editor)) restoreChatPresetLibraryFocus(root, focus);
};

const disconnectChatPresetLibraryPresentation = (root: HTMLElement): void => {
    const list = resolveElement(root, 'preset-list');
    checkerboardService.disconnect(checkerboardService.getContainerId(list));
};

const readPresetId = (actionElement: HTMLElement): string | null => {
    const value = actionElement.dataset['presetId'];
    return value && value.trim() ? value.trim() : null;
};

const readPresetSectionId = (input: HTMLInputElement): ChatPresetSectionId | null => {
    const value = input.dataset['chatPresetSection'];
    const definition = CHAT_PRESET_SECTION_DEFINITIONS.find((candidate) => candidate.id === value);
    return definition?.id ?? null;
};

export { applyChatPresetLibraryOperationState, disconnectChatPresetLibraryPresentation, readPresetId, readPresetSectionId, renderChatPresetLibrary, syncChatPresetEditorNamePresentation };
