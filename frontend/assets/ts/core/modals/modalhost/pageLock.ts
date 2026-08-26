/* SoAI - Shared modals page lock [frontend/assets/ts/core/modals/modalhost/pageLock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { lockModalPage, restoreModalPage } from '@core/modals/modalhost/layout.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';

const notifyModalOpened = (state: ModalHostState): void => {
    if (state.activeStack.length === 1) {
        lockModalPage(state);
    }
};

const notifyModalClosed = (state: ModalHostState): void => {
    if (state.activeStack.length === 0) {
        restoreModalPage(state);
    }
};

export { notifyModalClosed, notifyModalOpened };
