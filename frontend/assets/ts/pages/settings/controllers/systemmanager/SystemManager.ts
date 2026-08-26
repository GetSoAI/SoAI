/* SoAI - Settings system manager ownership [frontend/assets/ts/pages/settings/controllers/systemmanager/SystemManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { SettingsSectionLifecycle } from '@features/settings/public.ts';
import { SETTINGS_SYSTEM_CLEAR_PROMPT_HISTORY_ACTION, SETTINGS_SYSTEM_DELETE_ALL_CONVERSATIONS_ACTION, SETTINGS_SYSTEM_FACTORY_RESET_ACTION, SETTINGS_SYSTEM_RESET_ACL_POLICY_ACTION, SETTINGS_SYSTEM_RESET_APPEARANCE_ACTION, SETTINGS_SYSTEM_RESET_CHAT_PRESETS_ACTION, SETTINGS_SYSTEM_RESET_CONFIGURATION_ACTION, SETTINGS_SYSTEM_RESET_HARDWARE_HISTORY_ACTION, SETTINGS_SYSTEM_RESET_METRICS_ACTION, SETTINGS_SYSTEM_RESET_PAGE_LAYOUTS_ACTION, SETTINGS_SYSTEM_RESET_PASSWORD_MANAGER_ACTION, SETTINGS_SYSTEM_RESET_PREFERENCES_ACTION, SETTINGS_SYSTEM_RESET_RECENT_SEARCHES_ACTION, SETTINGS_SYSTEM_RESET_TOOL_APPROVAL_PERMISSIONS_ACTION } from '@pages/settings/controllers/systemmanager/constants.ts';
import type { FactoryResetExecutionContext, ManagedTimerState, ResetActionExecutionContext, SystemManagerActionId, SystemManagerDependencies, SystemManagerHost } from '@pages/settings/controllers/systemmanager/contracts.ts';
import { executeClearPromptHistory, executeConfigurationReset, executeFactoryReset, executeResetAclPolicy, executeResetAppearance, executeResetHardwareHistory, executeResetMetrics, executeResetPasswordManager, executeResetPreferences, executeResetToolApprovalPermissions } from '@pages/settings/controllers/systemmanager/controller.ts';
import { executeDeleteAllConversations } from '@pages/settings/controllers/systemmanager/deleteallconversationsreset/service.ts';
import { isSystemManagerActionId } from '@pages/settings/controllers/systemmanager/guards.ts';
import { executeResetChatPresets, executeResetMovablePageLayouts, executeResetRecentSearches } from '@pages/settings/controllers/systemmanager/localresetactions/service.ts';
import { renderSystemManagerSection } from '@pages/settings/controllers/systemmanager/view.ts';

const createTimerState = (): ManagedTimerState => ({
    value: null
});

class SystemManager {
    readonly #host: SystemManagerHost;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();
    #factoryResetTimerState: ManagedTimerState = createTimerState();

    constructor({ host }: SystemManagerDependencies) {
        if (!host) {
            throw new Error('SystemManager requires a host');
        }
        this.#host = host;
    }

    render(): TrustedHtml {
        return toTrustedUiHtml(renderSystemManagerSection((action) => this.#host.workflow.canRunSystemAction(action)));
    }

    setupEventListeners(): void {
        this.#lifecycle.dispose('system-listeners-dispose');

        const root = this.#host.view.pageDom.optionalHTMLElement('reset-content');
        if (!root) {
            return;
        }

        this.#lifecycle.mount();

        const actionHandlers: Record<SystemManagerActionId, (button: HTMLButtonElement) => Promise<void>> = {
            [SETTINGS_SYSTEM_RESET_ACL_POLICY_ACTION]: (button): Promise<void> => this.resetAclPolicy(button),
            [SETTINGS_SYSTEM_RESET_APPEARANCE_ACTION]: (button): Promise<void> => this.resetAppearance(button),
            [SETTINGS_SYSTEM_RESET_PREFERENCES_ACTION]: (button): Promise<void> => this.resetPreferences(button),
            [SETTINGS_SYSTEM_RESET_METRICS_ACTION]: (button): Promise<void> => this.resetMetrics(button),
            [SETTINGS_SYSTEM_RESET_HARDWARE_HISTORY_ACTION]: (button): Promise<void> => this.resetHardwareHistory(button),
            [SETTINGS_SYSTEM_RESET_PAGE_LAYOUTS_ACTION]: (button): Promise<void> => this.resetMovablePageLayouts(button),
            [SETTINGS_SYSTEM_RESET_CHAT_PRESETS_ACTION]: (button): Promise<void> => this.resetChatPresets(button),
            [SETTINGS_SYSTEM_CLEAR_PROMPT_HISTORY_ACTION]: (button): Promise<void> => this.clearPromptHistory(button),
            [SETTINGS_SYSTEM_RESET_RECENT_SEARCHES_ACTION]: (button): Promise<void> => this.resetRecentSearches(button),
            [SETTINGS_SYSTEM_DELETE_ALL_CONVERSATIONS_ACTION]: (button): Promise<void> => this.deleteAllConversations(button),
            [SETTINGS_SYSTEM_RESET_TOOL_APPROVAL_PERMISSIONS_ACTION]: (button): Promise<void> => this.resetToolApprovalPermissions(button),
            [SETTINGS_SYSTEM_RESET_PASSWORD_MANAGER_ACTION]: (button): Promise<void> => this.resetPasswordManager(button),
            [SETTINGS_SYSTEM_RESET_CONFIGURATION_ACTION]: (button): Promise<void> => this.resetConfiguration(button),
            [SETTINGS_SYSTEM_FACTORY_RESET_ACTION]: (button): Promise<void> => this.showFactoryResetConfirmation(button)
        };

        bindDataActionListener({
            root,
            eventType: 'click',
            signal: this.#lifecycle.createAbortSignal('system-manager-actions-dispose'),
            isAction: isSystemManagerActionId,
            preventDefault: 'never',
            mouseButton: 'primary',
            ignoreDisabled: true,
            onAction: ({ action, actionElement }): Promise<void> => {
                if (!this.#host.workflow.canRunSystemAction(action)) {
                    throw new Error(`System action "${action}" is not allowed for the current user`);
                }
                const button = narrowButton(actionElement, `Action ${action}`);
                return actionHandlers[action](button);
            }
        });
    }

    async reload(): Promise<void> {
        this.#renderAndBindContent();
    }

    dispose(): void {
        try {
            this.#lifecycle.dispose('system-manager-dispose');
        } finally {
            if (this.#factoryResetTimerState.value !== null) {
                this.#host.view.pageResources.clearTimer(this.#factoryResetTimerState.value);
                this.#factoryResetTimerState.value = null;
            }
        }
    }

    async resetPreferences(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetPreferences(context);
    }

    async resetAclPolicy(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetAclPolicy(context);
    }

    async resetAppearance(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetAppearance(context);
    }

    async resetMetrics(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetMetrics(context);
    }

    async resetHardwareHistory(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetHardwareHistory(context);
    }

    async resetMovablePageLayouts(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetMovablePageLayouts(context);
    }

    async resetChatPresets(button: HTMLButtonElement): Promise<void> {
        return executeResetChatPresets({ host: this.#host, button });
    }

    async clearPromptHistory(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeClearPromptHistory(context);
    }

    async resetRecentSearches(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetRecentSearches(context);
    }

    async deleteAllConversations(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeDeleteAllConversations(context);
    }

    async resetToolApprovalPermissions(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetToolApprovalPermissions(context);
    }

    async resetPasswordManager(button: HTMLButtonElement): Promise<void> {
        const context: ResetActionExecutionContext = {
            host: this.#host,
            button
        };
        return executeResetPasswordManager(context);
    }

    async resetConfiguration(button: HTMLButtonElement): Promise<void> {
        return executeConfigurationReset({ host: this.#host, button });
    }

    async showFactoryResetConfirmation(button: HTMLButtonElement): Promise<void> {
        const context: FactoryResetExecutionContext = {
            host: this.#host,
            button,
            timerState: this.#factoryResetTimerState
        };
        return executeFactoryReset(context);
    }

    #renderAndBindContent(): void {
        renderSettingsSection({
            container: this.#host.view.pageDom.optionalHTMLElement('reset-content'),
            render: () => this.render(),
            renderMarkup: (container, markup): void => this.#host.view.pageDom.updateHtml(container, markup),
            bind: (): void => this.setupEventListeners(),
            filter: (): void => this.#host.workflow.filterSettings(),
            filterMode: 'always'
        });
    }
}

export { SystemManager };
