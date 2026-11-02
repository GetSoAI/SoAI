/* SoAI - Standardized unsaved changes confirmation modal [frontend/assets/ts/core/modals/unsavedChangesConfirmation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PresentationOwner } from '@core/routing/router/types.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService, type DialogsServiceApi } from '@core/ui/modals/dialogs/service.ts';

type UnsavedChangesConfirmationOptions = {
    readonly owner: PresentationOwner;
    dialogs?: DialogsServiceApi | undefined;
    message?: string | undefined;
    confirmText?: string | undefined;
};

const showUnsavedChangesConfirmation = async (options: UnsavedChangesConfirmationOptions): Promise<boolean> => {
    const dialogs = options.dialogs ?? requireDialogsService();
    const confirmationOptions = {
        owner: options.owner,
        title: i18n.t('common.unsavedChangesTitle'),
        message: options.message ?? i18n.t('common.unsavedChanges'),
        variant: 'warning'
    };
    if (options.confirmText !== undefined) {
        return await dialogs.showConfirmation({ ...confirmationOptions, confirmText: options.confirmText });
    }
    return await dialogs.showConfirmation(confirmationOptions);
};

export { showUnsavedChangesConfirmation };
