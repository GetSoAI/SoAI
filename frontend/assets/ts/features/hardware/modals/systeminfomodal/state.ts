/* SoAI - Hardware feature system info modal state [frontend/assets/ts/features/hardware/modals/systeminfomodal/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemInfoModalState } from '@features/hardware/modals/systeminfomodal/types.ts';

const createSystemInfoModalState = (): SystemInfoModalState => ({
    rawSystemInfo: '',
    anonymizedSystemInfo: '',
    isAnonymized: false,
    isOpen: false
});

export { createSystemInfoModalState };
