/* SoAI - Settings page manager operations, form binding, and dirty-state ownership [frontend/assets/ts/pages/settings/controllers/page/SettingsPageOperationsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { SaveController } from '@core/save/public.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext, SettingsPreferenceResetType } from '@pages/settings/controllers/page/contracts.ts';
import { applyWallpaperOverlay, confirmAndExecute, refreshWallpaperPreview, scheduleWallpaperRefresh, updatePreferenceToggleLabel, warnAndFocus, withButtonDisabled } from '@pages/settings/controllers/page/pageActions.ts';
import { preparePreferencesResetRefresh } from '@pages/settings/controllers/page/preferencesResetRefreshController.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { createAllTabs, renderAllContent } from '@pages/settings/controllers/page/settingsTabsController.ts';
import { filterSettings, setupFormIntegration } from '@pages/settings/controllers/page/view.ts';

class SettingsPageOperationsController implements SettingsManagerCallbacks {
    readonly #runtime: SettingsRuntimeContext;
    readonly #state: SettingsPageState;
    readonly #save: SaveController;

    constructor(runtime: SettingsRuntimeContext, state: SettingsPageState, save: SaveController) {
        this.#runtime = runtime;
        this.#state = state;
        this.#save = save;
    }

    readonly createAllTabs = async (): Promise<void> => {
        await createAllTabs(this.#runtime, this.#state);
    };

    readonly renderAllContent = (): void => {
        renderAllContent(this.#runtime, this.#state);
    };

    readonly filterSettings = (): void => {
        filterSettings(this.#runtime, this.#state);
    };

    readonly withButtonDisabled = async <T>(button: Element | null, operation: () => Promise<T>, options?: { keepDisabled?: boolean }): Promise<T> => {
        return withButtonDisabled(this.#runtime, button, operation, options);
    };

    readonly confirmAndExecute = async (...inputArguments: Parameters<SettingsManagerCallbacks['confirmAndExecute']>): Promise<void> => {
        await confirmAndExecute(this.#runtime, ...inputArguments);
    };

    readonly updatePreferenceToggleLabel = (element: Element, checked?: boolean): void => {
        updatePreferenceToggleLabel(this.#runtime, element, checked);
    };

    readonly warnAndFocus = (element: Element | null, message: string): void => {
        warnAndFocus(this.#runtime, element, message);
    };

    readonly applyWallpaperOverlay = (value: string): void => {
        applyWallpaperOverlay(this.#runtime, value);
    };

    readonly refreshWallpaperPreview = (): void => {
        refreshWallpaperPreview(this.#runtime, this.#state);
    };

    readonly scheduleWallpaperRefresh = (): void => {
        scheduleWallpaperRefresh(this.#runtime, this.#state);
    };

    readonly preparePreferencesResetRefresh = (type: SettingsPreferenceResetType): (() => Promise<void>) => {
        return preparePreferencesResetRefresh(this.#runtime, this.#state, { notifySaveChanged: this.notifySaveChanged }, type);
    };

    readonly rebindConfigForm = (): void => {
        setupFormIntegration(this.#runtime, this.#state, (path, valid, composing) => this.#updateSettingModifiedState(path, valid, composing));
        this.#state.dirtyStateManager?.refreshRenderedFields();
    };

    readonly notifySaveChanged = (): void => {
        this.#save.notifyChanged();
    };

    readonly requestSave = (): void => {
        terminateHandledPromise(this.#save.requestSave());
    };

    readonly syncManualDirtyField = (key: string, modified: boolean, valid: boolean): void => {
        this.#state.dirtyStateManager?.syncManualField(key, modified, valid);
    };

    readonly clearManualDirtyField = (key: string): void => {
        this.#state.dirtyStateManager?.clearManualField(key);
    };

    #updateSettingModifiedState(path: string, valid: boolean, composing = false): void {
        if (!path || !this.#state.dirtyStateManager) return;
        if (valid && this.#state.configManager) this.#state.coreConfig = this.#state.configManager.originalData;
        this.#state.dirtyStateManager.syncConfigField(path, valid, composing);
        this.#save.notifyChanged();
    }
}

export { SettingsPageOperationsController };
