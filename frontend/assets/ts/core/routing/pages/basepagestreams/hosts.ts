/* SoAI - Shared routing hosts [frontend/assets/ts/core/routing/pages/basepagestreams/hosts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageStreamsTaskHost } from '@core/routing/pages/basepagestreams/internalContracts.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

const createBasePageStreamsTaskHost = (dependencies: { pageId: string; setLoadingState: (element: Element | string, loading: boolean, text?: string) => void; showNotification: (message: string, type: NotificationType) => void; pageContext: BasePageStreamsTaskHost['pageContext'] }): BasePageStreamsTaskHost => {
    return {
        pageId: dependencies.pageId,
        setLoadingState: dependencies.setLoadingState,
        showNotification: dependencies.showNotification,
        pageContext: dependencies.pageContext
    };
};

export { createBasePageStreamsTaskHost };
