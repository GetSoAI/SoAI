/* SoAI - Chat preset library collection and editor presentation [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isChatPresetNameValid } from '@core/api/contracts/webuiChatPresetContracts.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { createSearchTextIndex, matchesSearchFilterQuery } from '@core/search/searchQuery.ts';
import { CHAT_ACTIONS, CHAT_CONFIGURATION_MODAL_ID, CHAT_PRESET_SECTION_DEFINITIONS, translateChatPresetSection, type ChatPresetSectionId } from '@features/chat/public.ts';
import type { WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import type { ChatPresetEditorDraft, ChatPresetLibraryViewState, ChatPresetSectionChoice } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';
import { createSearchFieldActions } from '@core/ui/searchField.ts';
import { insertWithPresence, removeWithPresence, isPresenceExiting } from '@core/animations/presence/public.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { CHECKERBOARD_CLASS_NAMES } from '@core/dom/checkerboardAssignment.ts';
import { createPresetActionButton, createPresetRow } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetRecordPresentationDomain.ts';
import { checkerboardService, dom } from '@core/dom/dom.ts';
import { captureChatPresetLibraryFocus, focusChatPresetEditorTransition, readChatPresetEditorFocusTarget, restoreChatPresetLibraryFocus } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryFocusDomain.ts';
import { renderChatPresetStatus } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetStatusPresentationDomain.ts';

const CHAT_PRESET_ROW_SELECTOR = '.chat-preset-row';

const resolveElement = (root: Element, token: string): HTMLElement => {
    const element = dom.resolve(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, token), root);
    if (!(element instanceof HTMLElement)) throw new Error(`Chat preset library is missing ${token}.`);
    return element;
};

const initializeChatPresetLibraryPresentation = (root: HTMLElement): void => {
    const search = resolveElement(root, 'preset-search');
    const surface = search.parentElement;
    if (!surface?.classList.contains('searchbar-container')) throw new Error('Chat preset search requires its searchbar container.');
    surface.replaceChildren(search, ...createSearchFieldActions(root.ownerDocument));
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
    if (sectionId === 'skills') return i18n.t('chat.configuration.skills.description');
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
    const draft = state.editor;
    editor.classList.toggle('u-hidden', draft === null);
    if (!draft) {
        editor.replaceChildren();
        delete editor.dataset['presetEditorMode'];
        delete editor.dataset['presetEditorTargetId'];
        return;
    }
    editor.dataset['presetEditorMode'] = draft.mode;
    if (draft.targetId) editor.dataset['presetEditorTargetId'] = draft.targetId;
    else delete editor.dataset['presetEditorTargetId'];
    const content = editor.ownerDocument.createElement('div');
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
    content.append(title, description, surface);
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
        content.append(choices);
    }
    if (draft.targetUnavailable || draft.reviewRequired) {
        const warning = editor.ownerDocument.createElement('div');
        warning.className = 'chat-configuration-hint is-warning';
        warning.textContent = draft.targetUnavailable ? i18n.t('chat.configuration.presetLibrary.editor.targetUnavailable') : i18n.t('chat.configuration.presetLibrary.editor.revisionChanged');
        content.append(warning);
        if (draft.reviewRequired && !draft.targetUnavailable) content.append(createPresetActionButton(editor.ownerDocument, CHAT_ACTIONS.REVIEW_PRESET_EDITOR, i18n.t('chat.configuration.presetLibrary.editor.reviewAction'), null, false));
    }
    const actions = editor.ownerDocument.createElement('div');
    actions.className = 'chat-configuration-actions';
    actions.append(createPresetActionButton(editor.ownerDocument, CHAT_ACTIONS.SUBMIT_PRESET_EDITOR, editorActionLabel(draft.mode), null, nameState.submitDisabled), createPresetActionButton(editor.ownerDocument, CHAT_ACTIONS.CANCEL_PRESET_EDITOR, i18n.t('common.cancel'), null, false));
    content.append(actions);
    reconcileChildNodes(editor, Array.from(content.childNodes));
    syncChatPresetEditorNamePresentation(editor, state);
    for (const input of dom.resolveAll('[data-chat-preset-section]', editor)) {
        if (!(input instanceof HTMLInputElement)) throw new Error('Chat preset section choice must be an input.');
        const sectionId = readPresetSectionId(input);
        if (sectionId === null) throw new Error('Chat preset section choice is unavailable.');
        input.checked = draft.selectedSections.has(sectionId);
    }
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
    const blockingLoad = stateSurface.dataset['chatLibraryLoading'] === 'true';
    stateSurface.setAttribute('aria-busy', operationPending || loading ? 'true' : 'false');
    for (const element of dom.resolveAll('[data-preset-base-disabled]', root)) {
        if (element instanceof HTMLButtonElement) element.disabled = operationPending || blockingLoad || element.dataset['presetBaseDisabled'] === 'true';
    }
};

const renderChatPresetLibrary = (root: HTMLElement, state: ChatPresetLibraryViewState): void => {
    const focus = captureChatPresetLibraryFocus(root);
    const editor = resolveElement(root, 'preset-editor');
    const previousEditor = readChatPresetEditorFocusTarget(editor);
    resolveElement(root, 'preset-toolbar').classList.toggle('u-hidden', state.editor !== null);
    const candidate = dom.resolve('.chat-preset-library', root);
    const stateSurface = candidate instanceof HTMLElement ? candidate : root;
    stateSurface.dataset['chatLibraryLoading'] = String(state.phase === 'loading' && state.lastSuccessAtMs === null);
    stateSurface.dataset['chatPresetState'] = state.phase === 'loading' ? 'loading' : state.stale ? 'stale' : state.phase;
    const search = resolveElement(root, 'preset-search');
    if (search instanceof HTMLInputElement && search.value !== state.searchQuery) search.value = state.searchQuery;
    const records = matchingRecords(state);
    renderChatPresetStatus(state, records.length, resolveElement(root, 'preset-status'), resolveElement(root, 'preset-empty'));
    if (state.phase !== 'loading' || !editor.hasChildNodes()) renderEditor(state, editor);
    const list = resolveElement(root, 'preset-list');
    list.classList.toggle('u-hidden', records.length === 0);
    const createdParent = root.ownerDocument.createElement('div');
    createdParent.append(...records.map((record) => createPresetRow(record, state, root.ownerDocument)));
    patchOrderedChildren({
        existingParent: list,
        createdParent,
        resolveChildKey: (child) => child.dataset['presetId'] ?? null,
        insertChild: (parent, child, anchor) => {
            insertWithPresence(parent, child, anchor);
            return child;
        },
        patchChild: (existing, created) => {
            const changed = syncElementShell({ target: existing, source: created, preservedClassNames: CHECKERBOARD_CLASS_NAMES });
            if (existing.innerHTML === created.innerHTML) return changed;
            reconcileChildNodes(existing, Array.from(created.childNodes));
            return true;
        },
        removeChild: removeWithPresence,
        isChildDetaching: isPresenceExiting,
        replaceUnsupportedChildren: () => {
            list.replaceChildren(...Array.from(createdParent.children));
            return true;
        }
    });
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

export { initializeChatPresetLibraryPresentation, applyChatPresetLibraryOperationState, disconnectChatPresetLibraryPresentation, readPresetId, readPresetSectionId, renderChatPresetLibrary, syncChatPresetEditorNamePresentation };
