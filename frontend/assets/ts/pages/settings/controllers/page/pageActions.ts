/* SoAI - Settings page control layer actions [frontend/assets/ts/pages/settings/controllers/page/pageActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { getBackgroundTasks } from '@core/backgroundtasks/service.ts';
import { ensureError } from '@core/errors/coerce.ts';
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
import { commitUiPreferences } from '@pages/settings/controllers/page/uiPreferences.ts';
import { showSettingsRestartNotification } from '@pages/settings/controllers/settingsRestartNotification.ts';
import type { OperationType } from '@features/overlays/public.ts';

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

const refreshBackgroundAfterPreferencesSave = (page: SettingsRuntimeContext): void => {
    runDetachedWithBoundary({ runWithBoundary: (name, task) => page.owners.pageLifecycle.run(name, task) }, 'settings:refreshBackgroundAfterSave', async () => {
        await getBackgroundTasks().refresh();
    });
};

const hasUnsavedChanges = (state: SettingsPageState): boolean => {
    return Boolean(state.configManager?.hasChanges || state.uiPrefsManager?.hasChanges);
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

const doSettingsAction = async <Result>(page: SettingsRuntimeContext, boundaryName: string, confirmOptions: ConfirmationOptions | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: ((result: Result) => Promise<void>) | null): Promise<Result | null> => {
    return page.owners.pageLifecycle.run(boundaryName, async () => {
        if (confirmOptions && !(await requireDialogsService().showConfirmation(confirmOptions))) {
            return null;
        }
        const result = await action();
        if (onSuccess) {
            await onSuccess(result);
        }
        if (successMessage) {
            page.owners.feedback.show(successMessage, 'success');
        }
        return result;
    });
};

const confirmAndExecute = async <Result>(page: SettingsRuntimeContext, boundaryName: string, confirmOptions: ConfirmationOptions | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null): Promise<void> => {
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
        onError?.(runtimeError);
        throw runtimeError;
    }
};

const clearAllModifiedStates = (state: SettingsPageState): void => {
    state.dirtyStateManager?.refreshRenderedFields();
};

const showRestartNotification = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<void> => {
    await showSettingsRestartNotification({
        restartApplication: async (): Promise<void> => {
            await page.owners.api.system.power.restartApplication();
        },
        showRestartOverlay: (value: OperationType): void => {
            state.restartOverlay.show(value);
        }
    });
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

const saveSettings = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<void> => {
    await page.owners.pageLifecycle.run('settings:saveSettings', async () => {
        if (!hasUnsavedChanges(state)) {
            return;
        }
        if (state.dirtyStateManager?.hasInvalidFields()) {
            page.owners.feedback.show(i18n.t('settings.notifications.fixInvalidFields'), 'warning');
            return;
        }
        const hadConfigChanges = Boolean(state.configManager?.hasChanges);
        if (state.configManager?.hasChanges) {
            state.configManager.validateAll();
            const patch = buildMinimalConfigPatch(state.configManager.originalData, state.configManager.currentData);
            await page.owners.api.configs.update('core', toJsonCompatibleValue(patch));
            state.configManager.commitChanges();
            state.coreConfig = state.configManager.currentData;
        }

        const solidBackgroundChanged = await commitUiPreferences(page, state);
        clearAllModifiedStates(state);
        if (solidBackgroundChanged) {
            refreshBackgroundAfterPreferencesSave(page);
        }
        if (hadConfigChanges) {
            await reloadSecurityAuditAfterConfigSave(page, state);
        }
        if (hadConfigChanges) {
            await showRestartNotification(page, state);
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

export { applyWallpaperOverlay, clearAllModifiedStates, confirmAndExecute, hasUnsavedChanges, refreshWallpaperPreview, saveSettings, scheduleWallpaperRefresh, showRestartNotification, updatePreferenceToggleLabel, warnAndFocus, withButtonDisabled };
