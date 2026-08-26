/* SoAI - Models feature rename modal effects [frontend/assets/ts/features/models/modals/renamemodal/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { RenameFormResetHost } from '@features/models/modals/renamemodal/types.ts';

const clearRenameFormFields = (host: RenameFormResetHost, modalRoot: HTMLElement): void => {
    const aliasInput = host.optionalHTMLElement(modalUiSelector(modalRoot.id, 'alias-input'), modalRoot);
    if (aliasInput instanceof HTMLInputElement) {
        host.setUIValue(aliasInput, '', { attribute: 'value' }, modalRoot);
        return;
    }
    if (aliasInput !== null) {
        throw new Error('RenameModelModalManager requires alias-input to be an input when present');
    }
};

export { clearRenameFormFields };
