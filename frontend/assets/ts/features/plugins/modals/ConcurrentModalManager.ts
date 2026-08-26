/* SoAI - Plugins feature concurrent modal manager [frontend/assets/ts/features/plugins/modals/ConcurrentModalManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import { validateClassNames, type BaseClassNames, type RequiredClassNames } from '@core/ui/classNames.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { CONCURRENT_ERROR_ID, CONCURRENT_ERROR_SELECTOR, CONCURRENT_FIELD_SELECTOR, CONCURRENT_HEADER_CONTEXT_ID, CONCURRENT_INPUT_SELECTOR, CONCURRENT_MODAL_ID, CONCURRENT_SAVE_SELECTOR, CONCURRENT_SLIDER_SELECTOR } from '@features/plugins/modals/concurrentmanager/constants.ts';
import { ensureConcurrentConfigLoaded, showConcurrentPluginsRestartNotification } from '@features/plugins/modals/concurrentmanager/effects.ts';
import { buildConcurrentCoreConfigCache, normalizeConcurrentValue, parseConcurrentInputValue, resolveConcurrentModalInitialState, resolveSliderInputState } from '@features/plugins/modals/concurrentmanager/state.ts';
import type { ConcurrentManagerHost, ConcurrentSliderBounds } from '@features/plugins/modals/concurrentmanager/types.ts';

const CONCURRENT_FIELD_KEY = 'maxConcurrentPlugins';

class ConcurrentModalManager {
    readonly modalId = CONCURRENT_MODAL_ID;
    readonly #host: ConcurrentManagerHost;
    private classNames: Pick<RequiredClassNames, 'hidden' | 'disabled'>;
    private sliderBounds: ConcurrentSliderBounds;
    #save: SaveController | null = null;
    #fieldState: FieldStateTracker | null = null;

    constructor({ host, classNames, sliderBounds }: { host: ConcurrentManagerHost; classNames: BaseClassNames; sliderBounds: ConcurrentSliderBounds }) {
        if (!host) {
            throw new Error('ConcurrentController requires a host');
        }
        this.#host = host;
        this.classNames = validateClassNames(classNames, ['hidden', 'disabled'], 'ConcurrentController');
        if (!sliderBounds || !Number.isFinite(sliderBounds.min) || !Number.isFinite(sliderBounds.defaultMax) || !Number.isFinite(sliderBounds.maxLimit)) {
            throw new Error('ConcurrentController requires numeric slider bounds');
        }
        this.sliderBounds = sliderBounds;
    }

    #disposeSaveWiring(): void {
        this.#save?.dispose();
        this.#save = null;
    }

    #disposeFieldState(): void {
        this.#fieldState?.clearAll();
        this.#fieldState = null;
    }

    #clearModalState(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        this.#disposeFieldState();

        const errorElement = this.#host.view.optionalHTMLElement(CONCURRENT_ERROR_SELECTOR, modalRoot);
        if (errorElement) {
            this.#host.view.addClassName(errorElement, this.classNames.hidden);
        }

        this.#disposeSaveWiring();
    }

    onModalClosed(): void {
        this.#clearModalState();
    }

    disposeForPageDestroy(): void {
        this.#clearModalState();
    }

    #isOpen(): boolean {
        return this.#host.view.modals.isOpen(this.modalId);
    }

    #computeFormState(): { hasChanges: boolean; isValid: boolean; parsedValue: number | null } {
        if (!this.#isOpen()) {
            return { hasChanges: false, isValid: true, parsedValue: null };
        }
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const input = requireInputElement(this.#host.view, CONCURRENT_INPUT_SELECTOR, 'value input', modalRoot);
        const raw = readTrimmedInputValue(input);
        const original = normalizeConcurrentValue(this.#host.state.getConcurrentPluginsOriginalValue(), this.sliderBounds.min);
        if (!input.validity.valid) {
            return { hasChanges: true, isValid: false, parsedValue: null };
        }
        if (raw === '') {
            return { hasChanges: original !== null, isValid: false, parsedValue: null };
        }
        const parsed = parseConcurrentInputValue(raw, this.sliderBounds.min);
        if (parsed === null) {
            return { hasChanges: true, isValid: false, parsedValue: null };
        }
        if (parsed > this.sliderBounds.maxLimit) {
            return { hasChanges: true, isValid: false, parsedValue: parsed };
        }
        const hasChanges = original === null ? true : parsed !== original;
        return { hasChanges, isValid: true, parsedValue: parsed };
    }

    setConcurrentPluginsError(message: string | null = null): void {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const errorElement = this.#host.view.requireHTMLElement(CONCURRENT_ERROR_SELECTOR, modalRoot);
        if (message) {
            this.#host.view.updateText(errorElement, message);
            this.#host.view.removeClassName(errorElement, this.classNames.hidden);
        } else {
            this.#host.view.addClassName(errorElement, this.classNames.hidden);
        }
    }

    populateConcurrentPluginsModal(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const input = requireInputElement(this.#host.view, CONCURRENT_INPUT_SELECTOR, 'value input', modalRoot);
        const slider = requireInputElement(this.#host.view, CONCURRENT_SLIDER_SELECTOR, 'slider', modalRoot);
        const modalState = resolveConcurrentModalInitialState(this.#host.state.getMaxConcurrentPlugins(), this.sliderBounds);
        this.#host.state.setConcurrentPluginsOriginalValue(modalState.normalizedValue);
        this.#host.view.updateAttribute(slider, 'min', String(this.sliderBounds.min));
        this.#host.view.updateAttribute(slider, 'max', String(modalState.sliderMax));
        this.#host.view.updateProperty(slider, 'value', modalState.sliderValue);

        this.#host.view.updateProperty(input, 'value', modalState.inputValue);
        this.#host.view.updateAttribute(input, 'aria-describedby', CONCURRENT_ERROR_ID);
        this.setConcurrentPluginsError(null);
    }

    async openConcurrentPluginsModal(): Promise<void> {
        await ensureConcurrentConfigLoaded(this.#host);
        this.#disposeSaveWiring();
        this.#disposeFieldState();
        this.populateConcurrentPluginsModal();
        this.#initializeFieldState();
        this.#initializeSaveWiring();
        this.#host.view.modals.open(this.modalId);
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        this.updateConcurrentPluginsModifiedState();
        requireInputElement(this.#host.view, CONCURRENT_INPUT_SELECTOR, 'value input', modalRoot).focus({ preventScroll: true });
    }

    handleSaveConcurrentPlugins(): void {
        if (!this.#save) {
            throw new Error('ConcurrentModalManager handleSaveConcurrentPlugins requires an active SaveController');
        }
        terminateHandledPromise(this.#save.requestSave());
    }

    async saveConcurrentPluginsSetting(): Promise<void> {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const input = requireInputElement(this.#host.view, CONCURRENT_INPUT_SELECTOR, 'value input', modalRoot);
        const parsedValue = parseConcurrentInputValue(input.value, this.sliderBounds.min);
        if (parsedValue === null) {
            this.setConcurrentPluginsError(i18n.t('plugins.notifications.concurrentPluginsInvalid'));
            this.updateConcurrentPluginsModifiedState();
            input.focus({ preventScroll: true });
            return;
        }
        if (parsedValue > this.sliderBounds.maxLimit) {
            this.setConcurrentPluginsError(i18n.t('plugins.notifications.concurrentPluginsTooHigh'));
            this.updateConcurrentPluginsModifiedState();
            input.focus({ preventScroll: true });
            return;
        }
        this.setConcurrentPluginsError(null);
        try {
            await this.#host.operations.api.configs.update('core', { MODELS: { ROUTING: { MAX_CONCURRENT_PLUGINS: parsedValue } } });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ConcurrentController', i18n.t('plugins.notifications.concurrentPluginsSaveFailed'), runtimeError);
            this.#host.view.showNotification(i18n.t('plugins.notifications.concurrentPluginsSaveFailed'), 'error');
        }
        this.#host.state.setMaxConcurrentPlugins(parsedValue);
        this.#host.state.setCoreConfigCache(buildConcurrentCoreConfigCache(this.#host.state.getCoreConfigCache(), parsedValue));
        this.#host.state.updateStats();
        this.#host.view.showNotification(i18n.t('plugins.notifications.concurrentPluginsSaved'), 'success');
        await this.showConcurrentPluginsRestartNotification();
        this.#host.view.modals.close(this.modalId);
        this.#save?.notifyChanged();
    }

    handleConcurrentPluginsSliderInput(event: Event): void {
        const slider = event?.target;
        if (!(slider instanceof HTMLInputElement)) return;
        const value = parseConcurrentInputValue(slider.value, this.sliderBounds.min);
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const input = requireInputElement(this.#host.view, CONCURRENT_INPUT_SELECTOR, 'value input', modalRoot);
        if (value !== null) {
            this.#host.view.updateProperty(input, 'value', value);
            this.setConcurrentPluginsError(null);
        }
        this.updateConcurrentPluginsModifiedState();
    }

    handleConcurrentPluginsInputChange(event: Event): void {
        const target = event?.target;
        if (!(target instanceof HTMLInputElement)) return;
        const input = target;
        const value = parseConcurrentInputValue(input.value, this.sliderBounds.min);
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const slider = requireInputElement(this.#host.view, CONCURRENT_SLIDER_SELECTOR, 'slider', modalRoot);
        if (value !== null) {
            const maxParsed = Number(slider.max);
            const currentMax = Number.isFinite(maxParsed) ? maxParsed : this.sliderBounds.defaultMax;
            const sliderState = resolveSliderInputState(value, currentMax, this.sliderBounds);
            if (sliderState.nextSliderMax !== currentMax) {
                this.#host.view.updateAttribute(slider, 'max', String(sliderState.nextSliderMax));
            }
            this.#host.view.updateProperty(slider, 'value', sliderState.boundedValue);
            if (value !== sliderState.boundedValue) {
                this.#host.view.updateProperty(input, 'value', sliderState.boundedValue);
            }
            this.setConcurrentPluginsError(null);
        }
        this.updateConcurrentPluginsModifiedState();
    }

    updateConcurrentPluginsModifiedState(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        this.#host.view.requireHTMLElement(CONCURRENT_FIELD_SELECTOR, modalRoot);
        const { hasChanges, isValid } = this.#computeFormState();
        this.#fieldState?.setModified(CONCURRENT_FIELD_KEY, hasChanges);
        this.#fieldState?.setInvalid(CONCURRENT_FIELD_KEY, isValid ? null : 'invalid');
        this.#save?.notifyChanged();
    }

    async showConcurrentPluginsRestartNotification(): Promise<void> {
        await showConcurrentPluginsRestartNotification(this.#host);
    }

    #initializeSaveWiring(): void {
        const modalRoot = this.#host.view.modals.requireElement(CONCURRENT_MODAL_ID);
        const saveButton = requireButtonElement(this.#host.view, CONCURRENT_SAVE_SELECTOR, 'save button', modalRoot);
        setAriaBusy(modalRoot, false);
        const save = createSaveController({
            headerContextId: CONCURRENT_HEADER_CONTEXT_ID,
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Concurrent plugins save',
            units: [
                {
                    id: 'concurrent-plugins',
                    hasChanges: () => this.#computeFormState().hasChanges,
                    isValid: () => this.#computeFormState().isValid,
                    save: async () => this.saveConcurrentPluginsSetting()
                }
            ]
        });
        this.#save = save;
        save.attach({
            resolveSaveButtons: () => (this.#host.view.modals.isOpen(CONCURRENT_MODAL_ID) ? [saveButton] : []),
            busyRoots: [modalRoot],
            autoNotifyRoot: modalRoot,
            buttonDisabledClassName: this.classNames.disabled
        });
    }

    #initializeFieldState(): void {
        this.#fieldState = new FieldStateTracker({
            getElement: () => {
                const modalRoot = this.#host.view.modals.requireElement(this.modalId);
                return this.#host.view.requireHTMLElement(CONCURRENT_FIELD_SELECTOR, modalRoot);
            }
        });
        this.updateConcurrentPluginsModifiedState();
    }
}

export { ConcurrentModalManager };
