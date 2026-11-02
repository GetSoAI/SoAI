/* SoAI - Shared routing hosts [frontend/assets/ts/core/routing/pages/basepagestreams/hosts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageStreamsTaskHost } from '@core/routing/pages/basepagestreams/internalContracts.ts';

const createBasePageStreamsTaskHost = (dependencies: BasePageStreamsTaskHost): BasePageStreamsTaskHost => {
    return {
        pageId: dependencies.pageId,
        requireActive: dependencies.requireActive,
        setLoadingState: dependencies.setLoadingState,
        showNotification: dependencies.showNotification,
        pageContext: dependencies.pageContext
    };
};

export { createBasePageStreamsTaskHost };
