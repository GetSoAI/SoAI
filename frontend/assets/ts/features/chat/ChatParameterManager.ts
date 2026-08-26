/* SoAI - Chat feature parameter manager [frontend/assets/ts/features/chat/ChatParameterManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n, type TranslationKey } from '@core/i18n/index.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { isArray } from '@core/typeGuards.ts';
import { cloneChatParameters, formatParameterForInput, type ChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { readChatParameterControlValue, resolveChatParameterKey } from '@core/chat/parameters/parameterControlValues.ts';
import { applyParameterSendEnabledStates } from '@core/chat/parameters/parameterSendToggleEffects.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { formatTextZoomDisplay } from '@features/chat/conversationFormatting.ts';

interface ChatParameterSurfaceDependencies {
    showConfirmation: (options: import('@core/ui/modals/dialogs/types.ts').ConfirmationOptions) => Promise<boolean>;
    showNotification: (message: string, type: import('@core/ui/notifications/notifications.ts').NotificationType, duration?: number) => void;
    optionalUI: (selector: string, context?: Element) => Element | null;
    queryUI: (selector: string) => Element[];
    updateText: (element: Element, text: string) => void;
    updateProperty: (element: Element, prop: string, value: import('@core/dom/propertyValues.ts').DomPropertyValue) => void;
    setUIValue: (element: Element, value: JsonValue | null | undefined, options?: import('@core/routing/pages/pagetypes/public.ts').SetUIValueOptions) => void;
    isEditingConfiguration: () => boolean;
    recalculateConfigurationDirtyState: () => void;
    getWorkingParameters: () => ChatParameters;
}

interface ChatParameterManagerDependencies {
    surface: ChatParameterSurfaceDependencies;
    dom: { getData: (element: Element | null, key: string) => string | null };
    hasParameterKey: (parameter: string) => boolean;
    updateParameterValue: (parameter: string, value: JsonValue) => void;
    setParameterValidity: (parameter: string, valid: boolean) => void;
    isParameterLocked: (parameter: string) => boolean;
    resolveParameterLockHint: (parameter: string) => TranslationKey | null;
    resolveParameterControlValue: (parameter: string, value: JsonValue) => JsonValue;
    stageDefaultParameters: (parameters: ChatParameters) => Readonly<{ skippedToolParameters: number }>;
    getTextZoom: () => number;
    setTextZoom: (zoom: number) => void;
    getEditingTextZoom: () => number | null;
    setEditingTextZoom: (zoom: number) => void;
    getTextZoomController: () => { currentZoom: number; persistZoom: (zoom: number) => void } | null;
    applyTextZoom: () => void;
    savePreferences: () => void;
}
const TEXT_ZOOM_PARAMETER = 'textZoom';
const REASONING_EFFORT_PARAMETER = 'reasoningEffort';
const REASONING_EFFORT_SEND_ENABLED_PARAMETER = 'reasoningEffortSendEnabled';

class ChatParameterManager {
    #dependencies: ChatParameterManagerDependencies;
    constructor(dependencies: ChatParameterManagerDependencies) {
        this.#dependencies = dependencies;
    }
    isParameterLocked(parameter: string): boolean {
        return this.#dependencies.isParameterLocked(parameter);
    }
    async restoreDefaults(): Promise<void> {
        const confirmed = await this.#dependencies.surface.showConfirmation({
            title: i18n.t('chat.parameters.resetDefaultsAction'),
            message: i18n.t('chat.parameters.confirmRestoreDefaults'),
            confirmText: i18n.t('chat.parameters.resetDefaultsAction'),
            variant: 'warning'
        });
        if (!confirmed) {
            return;
        }
        const result = this.#applyDefaultParameters();
        if (result.skippedToolParameters > 0) {
            this.#dependencies.surface.showNotification(i18n.t('chat.parameters.defaultsRestoredToolsSkipped'), 'warning');
            return;
        }
        this.#dependencies.surface.showNotification(i18n.t('chat.parameters.defaultsRestored'), 'success');
    }
    updateParameterUI(): void {
        const elements = this.#dependencies.surface.queryUI('[data-param]');
        for (const element of elements) {
            this.#updateParameterElementFromState(element);
        }
        this.#applySendEnabledStates(elements[0]);
    }
    applyParameterValueFromElement(element: Element): void {
        const domParameter = this.#dependencies.dom.getData(element, 'param');
        if (!domParameter) return;
        const parameter = resolveChatParameterKey(domParameter);
        const isTextZoom = parameter === TEXT_ZOOM_PARAMETER;
        if (!isTextZoom && !this.#dependencies.hasParameterKey(parameter)) return;
        if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement) && !(element instanceof HTMLSelectElement)) {
            throw new TypeError('Chat parameter element must be an HTMLInputElement, HTMLTextAreaElement, or HTMLSelectElement');
        }
        if (this.#dependencies.isParameterLocked(parameter)) {
            this.#updateParameterElementFromState(element);
            return;
        }
        const isEditing = this.#dependencies.surface.isEditingConfiguration();
        const readResult = readChatParameterControlValue(element, domParameter);
        if (readResult === null) return;
        if (readResult === 'invalid') {
            this.#dependencies.setParameterValidity(parameter, false);
            return;
        }
        const value = readResult.value;
        this.#dependencies.setParameterValidity(parameter, true);
        if (isTextZoom) {
            const zoomValue = Number(value);
            if (isEditing) {
                this.#dependencies.setEditingTextZoom(zoomValue);
                this.#dependencies.surface.recalculateConfigurationDirtyState();
            } else {
                this.#dependencies.setTextZoom(zoomValue);
                const controller = this.#dependencies.getTextZoomController();
                if (controller) {
                    controller.currentZoom = zoomValue;
                    controller.persistZoom(zoomValue);
                }
                this.#dependencies.applyTextZoom();
            }
        } else {
            this.#dependencies.updateParameterValue(parameter, value);
            if (parameter === REASONING_EFFORT_PARAMETER && value === null) {
                this.#dependencies.updateParameterValue(REASONING_EFFORT_SEND_ENABLED_PARAMETER, false);
            }
        }
        this.#updateControlUi(element, parameter, value);
        this.#applySendEnabledStates(element);
    }
    #syncAfterEdit(): void {
        if (this.#dependencies.surface.isEditingConfiguration()) {
            this.#dependencies.surface.recalculateConfigurationDirtyState();
        } else {
            this.#dependencies.savePreferences();
        }
    }
    #applyDefaultParameters(): Readonly<{ skippedToolParameters: number }> {
        const defaults = cloneChatParameters({});
        const result = this.#dependencies.stageDefaultParameters(defaults);
        this.updateParameterUI();
        this.#syncAfterEdit();
        return result;
    }
    #applySendEnabledStates(element?: Element): void {
        const root = element?.closest('.chat-configuration-modal') ?? this.#dependencies.surface.optionalUI('.chat-configuration-modal') ?? element?.ownerDocument ?? null;
        if (root) {
            applyParameterSendEnabledStates(root, this.#dependencies.surface.getWorkingParameters());
        }
    }
    #updateParameterElementFromState(element: Element): void {
        const domParameter = this.#dependencies.dom.getData(element, 'param');
        if (!domParameter) {
            return;
        }
        const parameter = resolveChatParameterKey(domParameter);
        const isTextZoom = parameter === TEXT_ZOOM_PARAMETER;
        const value = isTextZoom ? (this.#dependencies.surface.isEditingConfiguration() ? this.#dependencies.getEditingTextZoom() : this.#dependencies.getTextZoom()) : this.#dependencies.surface.getWorkingParameters()?.[parameter];
        if (value === undefined) return;
        this.#updateControlUi(element, parameter, value);
    }
    #updateControlUi(element: Element, parameter: string, value: JsonValue | null | undefined): void {
        if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement) && !(element instanceof HTMLSelectElement)) {
            throw new Error('ChatParameterManager control element must be an HTMLInputElement, HTMLTextAreaElement, or HTMLSelectElement');
        }
        if (!isJsonValue(value)) {
            throw new Error(`Chat parameter "${parameter}" must be JSON-compatible`);
        }
        const controlValue = this.#dependencies.resolveParameterControlValue(parameter, value);
        if (element instanceof HTMLSelectElement) {
            const selectValue = controlValue === null || controlValue === undefined ? '' : String(controlValue);
            this.#dependencies.surface.updateProperty(element, 'value', selectValue);
            return;
        }
        const isTextarea = element instanceof HTMLTextAreaElement;
        if (!isTextarea && element.type === 'checkbox') {
            const checked = Boolean(controlValue);
            this.#dependencies.surface.updateProperty(element, 'checked', checked);
            updateToggleLabel(element, { checked });
            return;
        }
        const isRangeInput = !isTextarea && element.type === 'range';
        const isTextZoom = parameter === TEXT_ZOOM_PARAMETER;
        const displayInput = isArray(controlValue) ? controlValue.join(', ') : controlValue === null ? '' : isTextZoom ? String(controlValue) : formatParameterForInput(parameter, controlValue);
        const displayValue = isTextZoom ? formatTextZoomDisplay(Number(controlValue)) : displayInput;
        this.#dependencies.surface.setUIValue(element, isRangeInput ? displayInput : displayValue, { attribute: 'value' });
        const displaySelector = this.#dependencies.dom.getData(element, 'display');
        if (!displaySelector) return;
        const displayElement = this.#dependencies.surface.optionalUI(displaySelector);
        if (displayElement) this.#dependencies.surface.updateText(displayElement, displayValue);
    }
}
export { ChatParameterManager };
