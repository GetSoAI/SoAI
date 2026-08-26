/* SoAI - Backend website link event binding [frontend/assets/ts/features/plugins/modals/backend/backendWebsiteLinkEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface BackendWebsiteLinkEventHost {
    view: {
        on(target: EventTarget | Element, event: string, handler: EventListener, options?: AddEventListenerOptions): () => void;
    };
    status: {
        handleBackendWebsiteLinkClick(event: Event): Promise<void>;
    };
}

const reportBackendWebsiteLinkError = (error: Error): void => {
    errorHandler.error('PluginsBackendModal', 'Backend website link click failed', error);
};

const trackBackendWebsiteLinkClick = (task: Promise<void>): void => {
    task.catch((error) => {
        reportBackendWebsiteLinkError(ensureError(error));
    });
};

const bindBackendWebsiteLinkClick = (host: BackendWebsiteLinkEventHost, linkElement: HTMLElement): void => {
    host.view.on(linkElement, 'click', (event: Event): void => {
        event.preventDefault();
        trackBackendWebsiteLinkClick(host.status.handleBackendWebsiteLinkClick(event));
    });
};

export { bindBackendWebsiteLinkClick };
