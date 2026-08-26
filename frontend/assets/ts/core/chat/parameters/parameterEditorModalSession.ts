/* SoAI - Shared chat parameter editor modal session [frontend/assets/ts/core/chat/parameters/parameterEditorModalSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyParameterSendEnabledStates } from '@core/chat/parameters/parameterSendToggleEffects.ts';
import { CHAT_PARAMETER_WIRE_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { restoreDisabledParameterSendValues } from '@core/chat/parameters/parameterSendToggleState.ts';
import { formatParameterForInput } from '@core/chat/parameters/chatParameterDefaults.ts';
import { readChatParameterControlValue, resolveChatParameterKey } from '@core/chat/parameters/parameterControlValues.ts';
import { cloneChatParameterEditorState, type ChatParameterEditorState } from '@core/chat/parameters/parameterEditorState.ts';
import { CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS, configureModelParameterNavigation } from '@core/chat/parameters/modelParameterNavigationMarkup.ts';
import { resolveChatParameterControlStrings } from '@core/chat/parameters/parameterControlStrings.ts';
import type { ReasoningEffortLevel } from '@core/chat/parameters/reasoningEffort.ts';
import { ReasoningEffortControl } from '@core/chat/parameters/reasoningEffortPresentation.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { dom } from '@core/dom/dom.ts';
import { setControlValidity } from '@core/dom/formValidity.ts';
import { createFormChangeSurfaceTracker } from '@core/forms/formChangeSurfaceTracker.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL } from '@core/save/public.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { isArray, isNumber } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

type ParameterControl = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

type OpenChatParameterEditorModalOptions = {
    presenter: ModalPresenterApi;
    modalId: string;
    initialState: ChatParameterEditorState;
    includeSystemPromptLock: boolean;
    canApply: () => boolean;
    resolveModelDetailId: () => string | null;
    supportedReasoningLevels: readonly ReasoningEffortLevel[] | null;
};

const isOpenModelSettingsAction = (value: string | undefined): value is typeof CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS => value === CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS;

const openModelParameters = (detailUniversalId: string): void => {
    requireRouter().navigateWithQuery(`model/${encodeSegment(detailUniversalId)}`, { tab: 'parameters' });
};

const requireSaveButton = (modal: HTMLElement, modalId: string): HTMLButtonElement => {
    const element = dom.resolve(modalUiSelector(modalId, 'save-button'), modal);
    if (!(element instanceof HTMLButtonElement)) throw new Error('Chat parameter editor save button is missing');
    return element;
};

const syncCompletionTokenMaximum = (modal: HTMLElement, modalId: string, state: ChatParameterEditorState): void => {
    const maximumInput = dom.resolve(modalUiSelector(modalId, 'max-completion-tokens-input'), modal);
    if (!(maximumInput instanceof HTMLInputElement)) throw new Error('Chat parameter editor maximum completion tokens input is missing');
    const contextWindowTokens = state.parameters.contextWindowTokens;
    if (typeof contextWindowTokens === 'number') maximumInput.max = String(contextWindowTokens);
    else maximumInput.removeAttribute('max');
};

const writeParameterControl = (control: ParameterControl, parameterKey: string, state: ChatParameterEditorState): void => {
    const value = state.parameters[parameterKey] ?? null;
    if (control instanceof HTMLSelectElement) {
        control.value = value === null || value === undefined ? '' : String(value);
        return;
    }
    if (control instanceof HTMLInputElement && control.type === 'checkbox') {
        control.checked = Boolean(value);
        updateToggleLabel(control, { checked: control.checked });
        return;
    }
    if (!isJsonValue(value)) throw new Error(`Chat parameter "${parameterKey}" must be JSON-compatible`);
    const displayValue = isArray(value) ? value.join(', ') : formatParameterForInput(parameterKey, value);
    control.value = displayValue;
    const displaySelector = control.dataset['display'] ?? '';
    const displayElement = displaySelector ? dom.resolve(displaySelector, control.ownerDocument) : null;
    if (displayElement) displayElement.textContent = displayValue;
};

const writeSettingControl = (control: ParameterControl, settingKey: string, state: ChatParameterEditorState): void => {
    if (settingKey === 'prompts.user_system_prompt' && control instanceof HTMLTextAreaElement) {
        control.value = state.prompts.userSystemPrompt ?? '';
        return;
    }
    if (settingKey === 'prompts.user_system_prompt_lock_enabled' && control instanceof HTMLInputElement) {
        control.checked = state.prompts.userSystemPromptLockEnabled;
        updateToggleLabel(control, { checked: control.checked });
        return;
    }
    if (settingKey === 'prompts.soai_system_prompt_enabled' && control instanceof HTMLInputElement) {
        control.checked = state.prompts.soaiSystemPromptEnabled;
        updateToggleLabel(control, { checked: control.checked });
    }
};

const writeParameterControlsForKey = (modal: HTMLElement, parameterKey: string, state: ChatParameterEditorState): void => {
    const wireParameter = CHAT_PARAMETER_WIRE_KEYS[parameterKey] ?? parameterKey;
    for (const element of dom.resolveAll(`[data-param="${wireParameter}"]`, modal)) {
        if (element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) {
            writeParameterControl(element, parameterKey, state);
        }
    }
};

const writeEditorState = (modal: HTMLElement, state: ChatParameterEditorState): void => {
    for (const element of dom.resolveAll('[data-param], [data-setting]', modal)) {
        if (!(element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement)) continue;
        const domParameter = element.dataset['param'] ?? '';
        if (domParameter) writeParameterControl(element, resolveChatParameterKey(domParameter), state);
        else writeSettingControl(element, element.dataset['setting'] ?? '', state);
    }
    applyParameterSendEnabledStates(modal, state.parameters);
};

const readSettingControl = (control: ParameterControl, settingKey: string, state: ChatParameterEditorState): boolean => {
    if (settingKey === 'prompts.user_system_prompt' && control instanceof HTMLTextAreaElement) {
        state.prompts.userSystemPrompt = toTrimmedString(control.value) || null;
    } else if (settingKey === 'prompts.user_system_prompt_lock_enabled' && control instanceof HTMLInputElement) {
        state.prompts.userSystemPromptLockEnabled = control.checked;
        updateToggleLabel(control, { checked: control.checked });
    } else if (settingKey === 'prompts.soai_system_prompt_enabled' && control instanceof HTMLInputElement) {
        state.prompts.soaiSystemPromptEnabled = control.checked;
        updateToggleLabel(control, { checked: control.checked });
    }
    return control.checkValidity();
};

const restoreDisabledSendParameterValues = (modal: HTMLElement, parameter: string, value: JsonValue, state: ChatParameterEditorState, baseline: ChatParameterEditorState): void => {
    for (const restoredParameter of restoreDisabledParameterSendValues(state.parameters, baseline.parameters, parameter, value)) {
        writeParameterControlsForKey(modal, restoredParameter, state);
    }
};

const readEditorControl = (modal: HTMLElement, control: ParameterControl, state: ChatParameterEditorState, baseline: ChatParameterEditorState): boolean => {
    const domParameter = control.dataset['param'] ?? '';
    if (!domParameter) return readSettingControl(control, control.dataset['setting'] ?? '', state);
    const result = readChatParameterControlValue(control, domParameter);
    if (result === 'invalid') return false;
    if (result === null) return control.checkValidity();
    state.parameters[result.parameter] = result.value;
    restoreDisabledSendParameterValues(modal, result.parameter, result.value, state, baseline);
    if (result.parameter === 'reasoningEffort' && result.value === null) {
        state.parameters.reasoningEffortSendEnabled = false;
        restoreDisabledSendParameterValues(modal, 'reasoningEffortSendEnabled', false, state, baseline);
        writeParameterControlsForKey(modal, 'reasoningEffortSendEnabled', state);
    }
    if (control instanceof HTMLInputElement && control.type === 'checkbox') updateToggleLabel(control, { checked: control.checked });
    if (isNumber(result.value)) writeParameterControl(control, result.parameter, state);
    return control.checkValidity();
};

const readEditorState = (modal: HTMLElement, state: ChatParameterEditorState, baseline: ChatParameterEditorState, reasoningEffortControl: ReasoningEffortControl): boolean => {
    let valid = true;
    for (const element of dom.resolveAll('[data-param], [data-setting]', modal)) {
        if (!(element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement)) continue;
        const controlValid = readEditorControl(modal, element, state, baseline);
        setControlValidity(element, controlValid, '.setting-change-surface');
        valid = controlValid && valid;
    }
    applyParameterSendEnabledStates(modal, state.parameters);
    return reasoningEffortControl.syncValidity(state.parameters.reasoningEffort) && valid;
};

const openChatParameterEditorModal = async (options: OpenChatParameterEditorModalOptions): Promise<ChatParameterEditorState | null> => {
    const draft = cloneChatParameterEditorState(options.initialState);
    const baseline = cloneChatParameterEditorState(options.initialState);
    return await runModalSession<ChatParameterEditorState | null>({
        presenter: options.presenter,
        modalId: options.modalId,
        onAlreadyOpen: 'replace',
        initialResult: null,
        initialize: ({ modal, signal, setResult, close }) => {
            const detailUniversalId = configureModelParameterNavigation(modal, options.resolveModelDetailId());
            const reasoningEffortControl = new ReasoningEffortControl(modal, options.modalId, draft.parameters.reasoningEffort, options.supportedReasoningLevels, resolveChatParameterControlStrings());
            writeEditorState(modal, draft);
            reasoningEffortControl.syncValidity(draft.parameters.reasoningEffort);
            syncCompletionTokenMaximum(modal, options.modalId, draft);
            const saveButton = requireSaveButton(modal, options.modalId);
            const changeSurfaces = createFormChangeSurfaceTracker(modal);
            changeSurfaces.captureBaseline();
            let completed = false;
            let savedState: ChatParameterEditorState | null = null;
            const save = createSaveController({
                headerContextId: `${options.modalId}:parameters`,
                headerPriority: SAVE_HEADER_PRIORITY_MODAL,
                requestContextLabel: 'Chat parameter editor save',
                units: [
                    {
                        id: 'chat-parameters',
                        hasChanges: () => changeSurfaces.hasChanges(),
                        isValid: () => options.canApply() && readEditorState(modal, draft, baseline, reasoningEffortControl),
                        save: (): void => {
                            savedState = cloneChatParameterEditorState(draft);
                        }
                    }
                ],
                onSaveComplete: (): void => {
                    if (!savedState) return;
                    setResult(savedState);
                    completed = true;
                    close('chat-parameters:save');
                }
            });
            save.attach({
                resolveSaveButtons: () => [saveButton],
                busyRoots: [modal],
                autoNotifyRoot: modal
            });
            const handleChange = (event: Event): void => {
                if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || event.target instanceof HTMLTextAreaElement) {
                    const valid = readEditorControl(modal, event.target, draft, baseline);
                    setControlValidity(event.target, valid, '.setting-change-surface');
                    applyParameterSendEnabledStates(modal, draft.parameters);
                    reasoningEffortControl.syncValidity(draft.parameters.reasoningEffort);
                    if (event.target.dataset['param'] === 'context_window_tokens') syncCompletionTokenMaximum(modal, options.modalId, draft);
                }
                changeSurfaces.sync();
                save.notifyChanged();
            };
            modal.addEventListener('input', handleChange, { signal, capture: true });
            modal.addEventListener('change', handleChange, { signal, capture: true });
            bindDataActionListener({
                root: modal,
                eventType: 'click',
                signal,
                isAction: isOpenModelSettingsAction,
                preventDefault: 'always',
                mouseButton: 'primary',
                ignoreDisabled: true,
                stopPropagation: true,
                onAction: (): void => {
                    if (detailUniversalId) openModelParameters(detailUniversalId);
                }
            });
            const detachDirtyGuard = attachBeforeCloseConfirmationGuard({
                modal,
                presenter: options.presenter,
                modalId: options.modalId,
                shouldConfirmClose: () => !completed && !save.isSaving() && changeSurfaces.hasChanges(),
                confirmClose: showUnsavedChangesConfirmation
            });
            return {
                dispose: (): void => {
                    detachDirtyGuard();
                    changeSurfaces.clear();
                    save.dispose();
                }
            };
        }
    });
};

export { openChatParameterEditorModal };
export type { OpenChatParameterEditorModalOptions };
