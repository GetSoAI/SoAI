/* SoAI - Automation page activation controller [frontend/assets/ts/pages/automation/controllers/AutomationPageActivationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parsePositiveCssPixelValue } from '@core/dom/attributes.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { applyAutomationInitialSelection, isAutomationInitialSelectionVisible } from '@pages/automation/controllers/initialSelectionController.ts';
import { loadAutomationPreferences } from '@pages/automation/state/preferences.ts';
import type { AutomationInitialSelection, AutomationPageState } from '@pages/automation/types.ts';
import { AUTOMATION_DEFAULT_HOUR_HEIGHT_PX } from '@pages/automation/widgets/calendar/constants.ts';
import type { AutomationPreferencesState } from '@pages/automation/controllers/AutomationPreferencesState.ts';

interface AutomationPageActivationControllerDependencies {
    storage: StorageService;
    root: HTMLElement;
    initialSelection: AutomationInitialSelection | null;
    getState: () => AutomationPageState;
    setState: (state: AutomationPageState) => void;
    setHourHeightPx: (value: number) => void;
    applySplit: (percent: number) => void;
    queueRender: () => void;
    refreshData: () => Promise<void>;
    waitForRenderIdle: () => Promise<void>;
    getStyleProp: (property: string, element?: Element) => string;
    showWarningNotification: (message: string) => void;
    preferencesStatus: AutomationPreferencesState;
}

class AutomationPageActivationController {
    readonly #dependencies: AutomationPageActivationControllerDependencies;
    #activated = false;
    #activationPromise: Promise<void> | null = null;
    #shellInitialized = false;

    constructor(dependencies: AutomationPageActivationControllerDependencies) {
        this.#dependencies = dependencies;
    }

    getPreferencesCorruptError(): Error | null {
        return this.#dependencies.preferencesStatus.error;
    }

    isPreferencesCorrupt(): boolean {
        return this.#dependencies.preferencesStatus.isCorrupt;
    }

    clearPreferencesCorruptError(): void {
        this.#dependencies.preferencesStatus.clear();
    }

    async initializeShell(): Promise<void> {
        if (this.#shellInitialized) {
            return;
        }
        this.#shellInitialized = true;
        try {
            const preferences = loadAutomationPreferences(this.#dependencies.storage);
            this.#dependencies.setState({ ...this.#dependencies.getState(), ...preferences });
        } catch (error) {
            this.#dependencies.preferencesStatus.record(ensureError(error));
        }
        this.#dependencies.applySplit(this.#dependencies.getState().splitLeftPercent);
        const hourHeight = this.#dependencies.getStyleProp('--automation-hour-height', this.#dependencies.root);
        this.#dependencies.setHourHeightPx(parsePositiveCssPixelValue(hourHeight, AUTOMATION_DEFAULT_HOUR_HEIGHT_PX));
        this.#dependencies.setState(applyAutomationInitialSelection(this.#dependencies.getState(), this.#dependencies.initialSelection));
        if (this.#dependencies.preferencesStatus.isCorrupt) {
            this.#dependencies.queueRender();
        }
    }

    async activate(signal: AbortSignal | null = null): Promise<void> {
        if (this.#activated || this.#dependencies.preferencesStatus.isCorrupt) {
            return;
        }
        if (this.#activationPromise) {
            return this.#activationPromise;
        }
        throwIfAborted(signal);
        const activation = this.#runActivation(signal);
        const trackedActivation = activation.finally(() => {
            if (this.#activationPromise === trackedActivation) {
                this.#activationPromise = null;
            }
        });
        this.#activationPromise = trackedActivation;
        return trackedActivation;
    }

    async #runActivation(signal: AbortSignal | null): Promise<void> {
        await this.#dependencies.refreshData();
        throwIfAborted(signal);
        await this.#dependencies.waitForRenderIdle();
        throwIfAborted(signal);
        if (!isAutomationInitialSelectionVisible(this.#dependencies.getState().zones, this.#dependencies.initialSelection)) {
            this.#dependencies.showWarningNotification(i18n.t('automation.notifications.runUnavailable'));
        }
        this.#activated = true;
    }
}

export { AutomationPageActivationController };
