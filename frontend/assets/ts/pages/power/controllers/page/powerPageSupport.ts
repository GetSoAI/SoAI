/* SoAI - Power page support [frontend/assets/ts/pages/power/controllers/page/powerPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isElementNode } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { RestartState } from '@core/restartStateGateway.ts';
import type { ActionDefinition, ConfirmActionOptions, NormalizedRestartState, PowerRestartType, RestartNotification } from '@pages/power/types.ts';
import type { PowerPageViewAction } from '@pages/power/view.ts';

const SYSTEM_REBOOT_SOURCE_PREFIX = 'soai_os.';

const resolvePowerEventTarget = (event: Event): Element | null => {
    const target = event.target;
    return isElementNode(target) ? target : null;
};

const normalizePowerRestartState = (value: RestartState): NormalizedRestartState => {
    const required = value.required;
    const reasons = value.reasons.filter((reason) => reason.trim().length > 0);
    const notifications: RestartNotification[] = value.notifications
        .map((entry) => {
            const reason = entry.reason.trim();
            const path = entry.path && entry.path.trim().length > 0 ? entry.path.trim() : null;
            return { reason, path };
        })
        .filter((entry) => entry.reason.length > 0);
    return { required, reasons, notifications };
};

const classifyPowerRestartType = (state: NormalizedRestartState): PowerRestartType => (state.notifications.some((notification) => notification.path !== null && notification.path.startsWith(SYSTEM_REBOOT_SOURCE_PREFIX)) ? 'system' : 'application');

const mapPowerViewActions = (definitions: ActionDefinition[]): PowerPageViewAction[] => {
    return definitions.map((definition) => {
        const mappedOptions = definition.options?.map((option) => {
            const optionView: {
                parameter: string;
                type?: 'checkbox' | 'number';
                label?: string;
                defaultValue?: number | boolean;
                min?: number;
                max?: number;
                step?: number;
            } = {
                parameter: String(option.parameter)
            };
            if (option.type !== undefined) {
                optionView.type = option.type;
            }
            if (option.label !== undefined) {
                optionView.label = option.label;
            }
            if (option.defaultValue !== undefined) {
                optionView.defaultValue = option.defaultValue;
            }
            if (option.min !== undefined) {
                optionView.min = option.min;
            }
            if (option.max !== undefined) {
                optionView.max = option.max;
            }
            if (option.step !== undefined) {
                optionView.step = option.step;
            }
            return optionView;
        });
        const viewAction: PowerPageViewAction = {
            key: definition.key,
            title: definition.title,
            description: definition.description,
            icon: definition.icon,
            buttonVariant: definition.buttonVariant,
            tone: definition.tone
        };
        if (mappedOptions && mappedOptions.length > 0) {
            viewAction.options = mappedOptions;
        }
        return viewAction;
    });
};

const confirmAndRunPowerAction = async (
    options: ConfirmActionOptions,
    dependencies: {
        showNotification: (message: string, type: 'success') => void;
        showErrorNotification: (message: string) => void;
    }
): Promise<boolean> => {
    const confirmationOptions: {
        title: string;
        message: string;
        confirmText: string;
        cancelText: string;
        variant: string;
        icon?: string;
        description?: string;
    } = {
        title: options.title ?? i18n.t('common.confirm'),
        message: options.message ?? '',
        confirmText: options.confirmText ?? i18n.t('common.confirm'),
        cancelText: options.cancelText ?? i18n.t('common.cancel'),
        variant: options.variant ?? 'warning'
    };
    if (options.icon !== undefined) {
        confirmationOptions.icon = options.icon;
    }
    if (options.warning !== undefined) {
        confirmationOptions.description = options.warning;
    }
    const confirmed = await requireDialogsService().showConfirmation(confirmationOptions);
    if (!confirmed) {
        return false;
    }
    try {
        let result = undefined;
        if (options.run) {
            result = await options.run();
        }
        if (options.successMessage) {
            dependencies.showNotification(options.successMessage, 'success');
        }
        if (options.onSuccess) {
            if (result === undefined) {
                throw new Error('Power confirmation onSuccess requires a run result');
            }
            options.onSuccess(result);
        }
        return true;
    } catch (error) {
        const runtimeError = ensureError(error);
        if (options.onError) {
            options.onError(runtimeError);
        }
        if (options.errorToastMessage) {
            dependencies.showErrorNotification(options.errorToastMessage);
        } else {
            showOperationFailureNotification({
                error: runtimeError,
                rawMessage: false,
                showNotification: (message) => dependencies.showErrorNotification(message)
            });
        }
        throw runtimeError;
    }
};

interface PowerRestartNoticeTarget {
    notice: HTMLElement | null;
    message: HTMLElement | null;
    options: HTMLElement | null;
}

interface PowerRestartReminderTargets {
    application: PowerRestartNoticeTarget;
    system: PowerRestartNoticeTarget;
}

interface PowerRestartReminderDependencies {
    updateText: (target: HTMLElement, text: string) => void;
    addHiddenClass: (target: HTMLElement) => void;
    removeHiddenClass: (target: HTMLElement) => void;
}

const restartReminderText = (reasons: string[]): string => {
    const reason = reasons[0];
    if (reason) {
        return i18n.t('power.restartReminder.messageWithReason', { reason });
    }
    return i18n.t('power.restartReminder.message');
};

const showRestartOptions = (target: HTMLElement | null, dependencies: PowerRestartReminderDependencies): void => {
    if (!target) {
        return;
    }
    dependencies.removeHiddenClass(target);
    target.setAttribute('aria-hidden', 'false');
};

const hideRestartOptions = (target: HTMLElement | null, dependencies: PowerRestartReminderDependencies): void => {
    if (!target) {
        return;
    }
    dependencies.addHiddenClass(target);
    target.setAttribute('aria-hidden', 'true');
};

const showRestartNotice = (target: PowerRestartNoticeTarget, reasons: string[], dependencies: PowerRestartReminderDependencies): void => {
    if (!target.notice) {
        return;
    }
    dependencies.removeHiddenClass(target.notice);
    target.notice.setAttribute('aria-hidden', 'false');
    if (target.message) {
        dependencies.updateText(target.message, restartReminderText(reasons));
    }
    hideRestartOptions(target.options, dependencies);
};

const hideRestartNotice = (target: PowerRestartNoticeTarget, dependencies: PowerRestartReminderDependencies): void => {
    if (!target.notice) {
        return;
    }
    dependencies.addHiddenClass(target.notice);
    target.notice.setAttribute('aria-hidden', 'true');
    if (target.message) {
        dependencies.updateText(target.message, i18n.t('power.restartReminder.message'));
    }
    showRestartOptions(target.options, dependencies);
};

const refreshPowerRestartReminderUi = (targets: PowerRestartReminderTargets, restartState: NormalizedRestartState, dependencies: PowerRestartReminderDependencies): void => {
    const restartType: PowerRestartType = restartState.required ? classifyPowerRestartType(restartState) : 'application';
    const systemActive = restartState.required && restartType === 'system';
    const applicationActive = restartState.required && restartType === 'application';

    if (applicationActive) {
        showRestartNotice(targets.application, restartState.reasons, dependencies);
    } else {
        hideRestartNotice(targets.application, dependencies);
    }

    if (systemActive) {
        showRestartNotice(targets.system, restartState.reasons, dependencies);
    } else {
        hideRestartNotice(targets.system, dependencies);
    }
};

export { classifyPowerRestartType, confirmAndRunPowerAction, mapPowerViewActions, normalizePowerRestartState, refreshPowerRestartReminderUi, resolvePowerEventTarget };

export type { PowerRestartNoticeTarget, PowerRestartReminderTargets };
