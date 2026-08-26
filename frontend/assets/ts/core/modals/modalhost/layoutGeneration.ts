/* SoAI - Shared modals layout generation [frontend/assets/ts/core/modals/modalhost/layoutGeneration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';

const advanceModalLayoutGeneration = (state: ModalHostState): number => {
    state.layoutGeneration += 1;
    return state.layoutGeneration;
};

const isModalLayoutCurrent = (state: ModalHostState, modalId: string, generation: number): boolean => {
    return state.layoutGeneration === generation && state.activeStack.includes(modalId);
};

export { advanceModalLayoutGeneration, isModalLayoutCurrent };
