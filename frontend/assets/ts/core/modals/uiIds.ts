/* SoAI - Modal UI ID helpers [frontend/assets/ts/core/modals/uiIds.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeModalId } from '@core/modals/guards.ts';

const TOKEN_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const modalUiId = (modalId: string, token: string): string => {
    const normalizedModalId = normalizeModalId(modalId);
    if (!TOKEN_PATTERN.test(token)) {
        throw new Error(`Invalid modal UI id token: "${token}"`);
    }
    return `${normalizedModalId}-${token}`;
};

const modalUiSelector = (modalId: string, token: string): string => `#${modalUiId(modalId, token)}`;

export { modalUiId, modalUiSelector };
