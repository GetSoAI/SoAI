/* SoAI - Administrator human-user creation controller [frontend/assets/ts/pages/settings/controllers/usersmanager/userCreationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { publishTerminalAccessPolicyInvalidation } from '@core/routing/router/terminalAccessPolicy.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isCanonicalUsernameInput, requireCanonicalUsername } from '@core/users/username.ts';
import type { UsersManagerActionContext } from '@pages/settings/controllers/usersmanager/types.ts';

const performAddUserAction = async ({ host, reloadUsers }: UsersManagerActionContext): Promise<void> => {
    await host.execution.runWithBoundary('settings:showAddUserModal', async () => {
        const rawUsername = await requireDialogsService().showPrompt({
            title: i18n.t('settings.users.addUserModal.title'),
            message: i18n.t('settings.users.addUserModal.usernamePrompt'),
            defaultValue: '',
            inputType: 'text',
            autocomplete: 'username'
        });
        if (rawUsername === null) return;
        if (!isCanonicalUsernameInput(rawUsername)) {
            host.notifications.feedback.show(i18n.t('settings.users.addUserModal.invalidUsername'), 'warning');
            return;
        }
        const username = requireCanonicalUsername(rawUsername);
        const password = await requireDialogsService().showPrompt({
            title: i18n.t('settings.users.addUserModal.title'),
            message: i18n.t('settings.users.addUserModal.passwordPrompt'),
            defaultValue: '',
            inputType: 'password',
            autocomplete: 'new-password'
        });
        if (!password) return;
        const isAdmin = await requireDialogsService().showConfirmation({
            title: i18n.t('settings.users.addUserModal.roleTitle'),
            message: i18n.t('settings.users.addUserModal.roleMessage', { username }),
            confirmText: i18n.t('settings.users.addUserModal.yesAdmin'),
            cancelText: i18n.t('settings.users.addUserModal.noRegularUser'),
            variant: 'info'
        });
        await host.execution.confirmAndExecute(
            'settings:createUser',
            null,
            async () => {
                await host.execution.runPageTask('settings.createUser', () => host.api.createUser(username, password, isAdmin), {
                    displayName: i18n.t('settings.users.addUserModal.title')
                });
                publishTerminalAccessPolicyInvalidation();
                await reloadUsers();
                return null;
            },
            i18n.t('settings.notifications.userCreateSuccess'),
            null,
            null
        );
    });
};

export { performAddUserAction };
