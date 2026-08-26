/* SoAI - Shared routing base page streams state [frontend/assets/ts/core/routing/pages/basepagestreams/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageStreamsState } from '@core/routing/pages/basepagestreams/internalContracts.ts';

const createBasePageStreamsState = (): BasePageStreamsState => {
    return {
        streamTrackers: null,
        coreStreamRuntime: null,
        subscriptionManager: null,
        autoResourceCleanup: null,
        autoResourceOfflineVisible: false
    };
};

export { createBasePageStreamsState };
