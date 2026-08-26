/* SoAI - Settings page users manager [frontend/assets/ts/pages/settings/controllers/UsersManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import { markSettingsCapabilityFailed, markSettingsCapabilityReady, SettingsSectionLifecycle } from '@features/settings/public.ts';
import { runDetachedWithBoundary } from '@pages/settings/controllers/page/detachedBoundaries.ts';
import { USERS_ACTION_ADD_USER } from '@pages/settings/controllers/usersmanager/constants.ts';
import { executeUsersManagerAction, executeUsersRoleSelectAction, isUsersActionId, isUsersRoleSelectActionId } from '@pages/settings/controllers/usersmanager/events.ts';
import { getUserById, getUserStats, isCurrentUser, mergeUserMutationResult, shouldPreventAdminDemotion, shouldPreventUserDeletion } from '@pages/settings/controllers/usersmanager/state.ts';
import type { UsersManagerDependencies, UsersManagerHost, UserStats } from '@pages/settings/controllers/usersmanager/types.ts';
import { renderUsersSection } from '@pages/settings/controllers/usersmanager/view.ts';
import { WebuiSessionsController } from '@pages/settings/controllers/usersmanager/WebuiSessionsController.ts';
import type { SettingsUsersContribution, SettingsUsersController } from '@core/edition/settingsContribution.ts';

class UsersManager {
    readonly #host: UsersManagerHost;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();
    readonly #productContribution: SettingsUsersContribution | null;
    #productController: SettingsUsersController | null = null;
    readonly #sessionsController: WebuiSessionsController;

    constructor({ host, productContribution }: UsersManagerDependencies) {
        if (!host) {
            throw new Error('UsersManager requires a host');
        }
        this.#host = host;
        this.#productContribution = productContribution;
        this.#sessionsController = new WebuiSessionsController(host);
    }

    render(): TrustedHtml {
        return toTrustedUiHtml(
            renderUsersSection({
                users: this.#host.state.getUsers(),
                availability: this.#host.state.getUsersAvailability(),
                sanitizeHtml: this.#host.view.sanitizeHtml,
                isCurrentUser: (userId) => this.isCurrentUserById(userId),
                canAdministerUsers: this.#host.state.canAdministerUsers(),
                canChangePassword: (userId) => this.canChangePasswordById(userId),
                shouldDisableChangeRole: (userId) => this.shouldPreventAdminDemotion(userId),
                shouldDisableDelete: (userId) => this.shouldPreventUserDeletion(userId),
                productSection:
                    this.#productContribution?.render({
                        users: this.#host.state.getUsers(),
                        availability: this.#host.state.getUsersAvailability(),
                        sanitizeHtml: this.#host.view.sanitizeHtml
                    }) ?? ''
            })
        );
    }

    setupEventListeners(): void {
        this.dispose();
        this.#lifecycle.mount();

        const container = this.#host.view.pageDom.requireHTMLElement('users-content');
        const actionsSignal = this.#lifecycle.createAbortSignal('users-actions-dispose');
        const shouldSkipClick = (event: Event): boolean => event.defaultPrevented;
        if (this.#productContribution !== null) {
            bindDataActionListener({
                root: container,
                eventType: 'click',
                signal: actionsSignal,
                isAction: this.#productContribution.isAction,
                preventDefault: 'always',
                mouseButton: 'primary',
                ignoreDisabled: true,
                beforeEvent: shouldSkipClick,
                onAction: async ({ action }): Promise<void> => {
                    await this.#host.execution.runWithBoundary('settings:usersClick', async () => {
                        if (this.#productController === null) {
                            throw new Error('Trusted host user controller is not initialized');
                        }
                        await this.#productController.execute(action);
                    });
                }
            });
        }
        bindDataActionListener({
            root: container,
            eventType: 'click',
            signal: actionsSignal,
            isAction: isUsersActionId,
            preventDefault: 'always',
            mouseButton: 'primary',
            ignoreDisabled: true,
            beforeEvent: shouldSkipClick,
            onAction: async ({ action, actionElement }): Promise<void> => {
                await this.#host.execution.runWithBoundary('settings:usersClick', async () => {
                    await executeUsersManagerAction(action, actionElement, {
                        host: this.#host,
                        reloadUsers: () => this.reload(),
                        getUserById: (userId) => this.getUserById(userId),
                        isCurrentUser: (user) => this.isCurrentUser(user),
                        applyUserResult: (user) => this.applyUserResult(user),
                        signal: actionsSignal,
                        shouldPreventAdminDemotion: (userId) => this.shouldPreventAdminDemotion(userId),
                        shouldPreventUserDeletion: (userId) => this.shouldPreventUserDeletion(userId)
                    });
                });
            }
        });
        bindDataActionListener({
            root: container,
            eventType: 'change',
            signal: actionsSignal,
            isAction: isUsersRoleSelectActionId,
            preventDefault: 'never',
            ignoreDisabled: true,
            onAction: async ({ action, actionElement }): Promise<void> => {
                await this.#host.execution.runWithBoundary('settings:usersRoleSelect', async () => {
                    await executeUsersRoleSelectAction(action, actionElement, {
                        host: this.#host,
                        reloadUsers: () => this.reload(),
                        getUserById: (userId) => this.getUserById(userId),
                        isCurrentUser: (user) => this.isCurrentUser(user),
                        applyUserResult: (user) => this.applyUserResult(user),
                        signal: actionsSignal,
                        shouldPreventAdminDemotion: (userId) => this.shouldPreventAdminDemotion(userId),
                        shouldPreventUserDeletion: (userId) => this.shouldPreventUserDeletion(userId)
                    });
                });
            }
        });

        if (this.#host.state.canAdministerUsers()) {
            const addUserButton = narrowButton(this.#host.view.pageDom.requireHTMLElement('add-user-btn', container), 'Add user button');
            if (requireTrimmedDataAttribute(addUserButton, 'action', 'Add user button') !== USERS_ACTION_ADD_USER) {
                throw new Error('Add user button is missing required data-action');
            }
        }

        this.#host.view.pageDom.requireHTMLElement('users-refresh-btn', container);
        this.#host.view.pageDom.requireHTMLElement('users-list', container);

        this.#rebindProductController(container, false);
        this.#sessionsController.mount(container);
    }

    async reload(): Promise<void> {
        const reloadRun = this.#lifecycle.beginReload('users-reload');
        if (reloadRun === null) {
            return;
        }

        let users: WebuiUser[];
        try {
            users = await this.#host.execution.runWithBoundary('settings:reloadUsers', async () => {
                return await this.#host.api.listUsers();
            });
        } catch (error) {
            if (this.#lifecycle.isReloadCurrent(reloadRun)) {
                this.#host.state.setUsersAvailability(markSettingsCapabilityFailed(this.#host.state.getUsersAvailability()));
                this.#renderUsersContent();
            }
            throw ensureError(error);
        }

        if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
            return;
        }

        this.#host.state.setUsers(users);
        this.#host.state.setUsersAvailability(markSettingsCapabilityReady());
        this.#renderUsersContent();
    }

    async refreshProductUsers(): Promise<void> {
        const productController = this.#productController;
        if (!productController) {
            return;
        }
        const refreshed = await productController.refresh();
        if (refreshed && this.#productController === productController) {
            this.#host.filterSettings();
        }
    }

    dispose(): void {
        const productController = this.#productController;
        this.#productController = null;
        try {
            this.#lifecycle.dispose('users-dispose');
        } finally {
            productController?.destroy();
            this.#sessionsController.destroy();
        }
    }

    getUserById(userId: string): WebuiUser | null {
        return getUserById(this.#host.state.getUsers(), userId);
    }

    isCurrentUser(user: WebuiUser): boolean {
        return isCurrentUser(this.#host.state.getCurrentUserId(), user);
    }

    isCurrentUserById(userId: string): boolean {
        const currentUserId = this.#host.state.getCurrentUserId();
        return currentUserId !== null && String(currentUserId) === String(userId);
    }

    canChangePasswordById(userId: string): boolean {
        return this.#host.state.canAdministerUsers() || this.isCurrentUserById(userId);
    }

    applyUserResult(user: WebuiUser): void {
        this.#host.state.setUsers(mergeUserMutationResult(this.#host.state.getUsers(), user));
        this.#renderUsersContent();
    }

    getUserStats(): UserStats {
        return getUserStats(this.#host.state.getUsers());
    }

    shouldPreventAdminDemotion(userId: string): boolean {
        return shouldPreventAdminDemotion(this.#host.state.getUsers(), userId);
    }

    shouldPreventUserDeletion(userId: string): boolean {
        return shouldPreventUserDeletion(this.#host.state.getUsers(), userId);
    }

    #renderUsersContent(): void {
        if (!this.#lifecycle.isMounted) {
            return;
        }
        const container = this.#host.view.pageDom.requireHTMLElement('users-content');
        this.#host.view.pageDom.updateHtml(container, this.render());
        this.#rebindProductController(container, true);
        this.#sessionsController.mount(container);
        this.#host.filterSettings();
    }

    #rebindProductController(container: HTMLElement, refresh: boolean): void {
        this.#productController?.destroy();
        this.#productController = null;
        if (this.#productContribution !== null) {
            const productController = this.#productContribution.createController(this.#host, container);
            this.#productController = productController;
            if (refresh) {
                runDetachedWithBoundary(this.#host.execution, 'settings:productUsersRefresh', async () => {
                    if (this.#productController === productController) {
                        const refreshed = await productController.refresh();
                        if (refreshed && this.#productController === productController) {
                            this.#host.filterSettings();
                        }
                    }
                });
            }
        }
    }
}

export { UsersManager };
