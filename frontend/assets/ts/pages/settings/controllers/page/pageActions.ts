/* SoAI - Settings page control layer actions [frontend/assets/ts/pages/settings/controllers/page/pageActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPresentationOwnerCurrent, isPresentationOwnerMutationAllowed, requirePresentationOwnerActive } from '@core/presentationOwner.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { getBackgroundTasks } from '@core/backgroundtasks/service.ts';
import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getErrorReference } from '@core/errors/reference.ts';
import { resolveHandledOperationCause } from '@core/operationErrorNotifier.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { SaveUnitResult } from '@core/save/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { normalizeProgressPercent } from '@core/primitives/progress.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { isArray, isBoolean, isObject, isPlainObject } from '@core/typeGuards.ts';
import { readClampedFlooredIntegerOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { runDetachedWithBoundary } from '@pages/settings/controllers/page/detachedBoundaries.ts';
import { isSettingsNormalTabVisibleById } from '@pages/settings/controllers/page/settingsAccessController.ts';
import { updateSecurityTabNotifyBadge } from '@pages/settings/controllers/page/securityTabBadgeController.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { commitUiPreferences, prepareUiPreferences, type PreparedUiPreferences } from '@pages/settings/controllers/page/uiPreferences.ts';
import { showSettingsRestartNotification } from '@pages/settings/controllers/settingsRestartNotification.ts';

const scheduleWallpaperRefresh = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    if (state.wallpaperRefreshPending) {
        return;
    }
    state.wallpaperRefreshPending = true;
    page.owners.pageResources.setTimer(() => {
        state.wallpaperRefreshPending = false;
        runDetachedWithBoundary({ runWithBoundary: (name, task) => page.owners.pageLifecycle.run(name, task) }, 'settings:refreshBackground', async () => {
            await getBackgroundTasks().refresh();
        });
    }, 100);
};

const hasUnsavedChanges = (state: SettingsPageState): boolean => {
    return Boolean(state.configManager?.hasChanges || state.uiPrefsManager?.hasChanges || state.dirtyStateManager?.hasPendingChanges());
};

const buildMinimalConfigPatch = (previous: Record<string, JsonValue>, current: Record<string, JsonValue>): Record<string, JsonValue> => {
    const visit = (before: JsonValue | undefined, after: JsonValue | undefined): JsonValue | undefined => {
        if (before === after) {
            return undefined;
        }
        if (before === null || before === undefined || after === null || after === undefined) {
            return before === after ? undefined : after;
        }
        const beforeIsObject = isPlainObject(before);
        const afterIsObject = isPlainObject(after);
        if (!beforeIsObject || !afterIsObject) {
            return before === after ? undefined : after;
        }
        const beforeObject = before;
        const afterObject = after;
        const keys = new Set([...Object.keys(beforeObject), ...Object.keys(afterObject)]);
        const patch: Record<string, JsonValue> = {};
        for (const key of keys) {
            const sub = visit(beforeObject[key], afterObject[key]);
            if (sub !== undefined) {
                patch[key] = sub;
            }
        }
        return Object.keys(patch).length ? patch : undefined;
    };

    const patch = visit(previous, current);
    if (patch === undefined || !isObject(patch) || isArray(patch)) {
        return {};
    }
    return patch;
};

const withButtonDisabled = async <T>(page: SettingsRuntimeContext, button: Element | null, functionValue: () => T | Promise<T>, options: { keepDisabled?: boolean } = {}): Promise<T> => {
    if (!button) {
        return await functionValue();
    }
    if (button instanceof HTMLButtonElement) {
        beginLoadingButton(button);
    } else {
        page.owners.pageDom.updateProperty(button, 'disabled', true);
    }
    try {
        return await functionValue();
    } finally {
        if (!options.keepDisabled) {
            if (button instanceof HTMLButtonElement) {
                clearLoadingButtonIfNeeded(button);
            } else {
                page.owners.pageDom.updateProperty(button, 'disabled', false);
            }
        }
    }
};

const warnAndFocus = (page: SettingsRuntimeContext, element: Element | null, message: string): void => {
    page.owners.feedback.show(message, 'warning');
    if (element instanceof HTMLElement) {
        element.focus();
    }
};

const updatePreferenceToggleLabel = (page: SettingsRuntimeContext, element: Element, enabled?: boolean): void => {
    const checkbox = (() => {
        if (element instanceof HTMLInputElement && element.type === 'checkbox') {
            return element;
        }
        const candidate = page.owners.pageDom.optional('input[type="checkbox"]', element);
        if (!candidate) {
            return null;
        }
        if (!(candidate instanceof HTMLInputElement)) {
            throw new TypeError('Settings preference toggle checkbox must be an HTMLInputElement');
        }
        return candidate;
    })();
    if (!checkbox) {
        return;
    }
    updateToggleLabel(checkbox, { checked: isBoolean(enabled) ? enabled : undefined });
};

const doSettingsAction = async <Result>(page: SettingsRuntimeContext, boundaryName: string, confirmOptions: Omit<ConfirmationOptions, 'owner'> | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: ((result: Result) => Promise<void>) | null): Promise<Result | null> => {
    const owner = page.owners.pageContext.presentationOwner;
    return page.owners.pageLifecycle.run(boundaryName, async () => {
        requirePresentationOwnerActive(owner);
        if (confirmOptions && !(await requireDialogsService().showConfirmation({ ...confirmOptions, owner }))) {
            return null;
        }
        requirePresentationOwnerActive(owner);
        const result = await action();
        if (!isPresentationOwnerCurrent(owner)) return result;
        if (onSuccess) {
            await onSuccess(result);
        }
        if (successMessage && isPresentationOwnerCurrent(owner)) {
            page.owners.feedback.show(successMessage, 'success');
        }
        return result;
    });
};

const confirmAndExecute = async <Result>(page: SettingsRuntimeContext, boundaryName: string, confirmOptions: Omit<ConfirmationOptions, 'owner'> | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null): Promise<void> => {
    try {
        await doSettingsAction(
            page,
            boundaryName,
            confirmOptions,
            action,
            successMessage,
            onSuccess
                ? async (): Promise<void> => {
                      await onSuccess();
                  }
                : null
        );
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isAbortError(runtimeError) && isPresentationOwnerCurrent(page.owners.pageContext.presentationOwner)) onError?.(runtimeError);
        throw runtimeError;
    }
};

const clearAllModifiedStates = (state: SettingsPageState): void => {
    state.dirtyStateManager?.refreshRenderedFields();
};

const reloadSecurityAuditAfterConfigSave = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<void> => {
    if (!isSettingsNormalTabVisibleById(page, state, 'security')) {
        return;
    }
    if (!state.securityManager) {
        throw new Error('SecurityManager not initialized');
    }
    await state.securityManager.reload();
    updateSecurityTabNotifyBadge(page, state);
};

interface PreparedSettingsSave {
    configPatch: JsonObject;
    uiPreferences: PreparedUiPreferences | null;
    isCurrent: () => boolean;
}

const prepareSettingsSave = (page: SettingsRuntimeContext, state: SettingsPageState): PreparedSettingsSave => {
    const epoch = page.owners.auth.authEpoch;
    const owner = page.owners.pageContext.presentationOwner;
    const configManager = state.configManager;
    const uiPrefsManager = state.uiPrefsManager;
    const isCurrent = (): boolean => page.owners.auth.authEpoch === epoch && !page.controls.isDestroyed() && isPresentationOwnerMutationAllowed(owner) && state.configManager === configManager && state.uiPrefsManager === uiPrefsManager;
    configManager?.validateAll();
    return {
        configPatch: configManager?.hasChanges ? buildMinimalConfigPatch(configManager.originalData, configManager.currentData) : {},
        uiPreferences: prepareUiPreferences(state, isCurrent),
        isCurrent
    };
};

const reportSettingsPartialSave = (page: SettingsRuntimeContext, error: Error): void => {
    const reference = getErrorReference(error);
    const reason = resolveHandledOperationCause(error) ?? `${i18n.t('common.errors.operationFailed')} ${i18n.t('app.errors.reference', { reference })}`;
    if (error instanceof APIError) errorHandler.warn('SettingsPage', `Settings save partially applied (${reference})`, error);
    else errorHandler.error('SettingsPage', `Settings save partially applied (${reference})`, error);
    page.owners.feedback.show(i18n.t('settings.notifications.partialSave', { reason }), 'warning');
};

const saveSettings = async (page: SettingsRuntimeContext, state: SettingsPageState, prepared?: PreparedSettingsSave): Promise<SaveUnitResult> => {
    if (!prepared && state.dirtyStateManager?.hasInvalidFields()) {
        page.owners.feedback.show(i18n.t('settings.notifications.fixInvalidFields'), 'warning');
        return { type: 'stop' };
    }
    const submitted = prepared ?? prepareSettingsSave(page, state);
    return await page.owners.pageLifecycle.run('settings:saveSettings', async (): Promise<SaveUnitResult> => {
        const { configPatch, isCurrent } = submitted;
        if (!isCurrent()) return { type: 'stop' };
        const hadConfigChanges = Object.keys(configPatch).length > 0;
        if (hadConfigChanges && state.configManager) {
            await page.owners.api.configs.update('core', toJsonCompatibleValue(configPatch));
            if (!isCurrent()) return { type: 'stop' };
            state.configManager.commitBaselinePatch(configPatch);
            state.coreConfig = state.configManager.originalData;
        }

        let result: Awaited<ReturnType<typeof commitUiPreferences>>;
        try {
            result = await commitUiPreferences(page, state, submitted.uiPreferences);
        } catch (error) {
            if (!isCurrent()) return { type: 'stop' };
            if (!hadConfigChanges) throw ensureError(error);
            reportSettingsPartialSave(page, ensureError(error));
            state.dirtyStateManager?.refreshRenderedFields();
            return { type: 'stop' };
        }
        if (!isCurrent()) return { type: 'stop' };
        if (result?.type === 'partial') {
            reportSettingsPartialSave(page, result.error);
            state.dirtyStateManager?.refreshRenderedFields();
            return { type: 'stop' };
        }
        if (result?.type === 'stop') return result;
        clearAllModifiedStates(state);
        if (hadConfigChanges) {
            await reloadSecurityAuditAfterConfigSave(page, state);
        }
        if (!isCurrent()) return { type: 'stop' };
        if (hadConfigChanges) {
            await showSettingsRestartNotification();
        }
    });
};

const refreshWallpaperPreview = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    if (!state.themeManager) {
        throw new Error('ThemeManager not initialized');
    }
    const manager = state.themeManager;
    runDetachedWithBoundary({ runWithBoundary: (name, task) => page.owners.pageLifecycle.run(name, task) }, 'settings:refreshWallpaperPreview', async () => {
        await manager.reload();
    });
};

const applyWallpaperOverlay = (page: SettingsRuntimeContext, value: string): void => {
    const normalized = readClampedFlooredIntegerOrFallbackValue(value, 0, undefined, undefined);
    const clamped = (normalizeProgressPercent(normalized) ?? 0) / 100;
    page.owners.dom.setStyle(page.owners.dom.getBody(), '--wallpaper-overlay-opacity', String(clamped));
};

export { applyWallpaperOverlay, clearAllModifiedStates, confirmAndExecute, hasUnsavedChanges, prepareSettingsSave, refreshWallpaperPreview, saveSettings, scheduleWallpaperRefresh, updatePreferenceToggleLabel, warnAndFocus, withButtonDisabled };
export type { PreparedSettingsSave };
