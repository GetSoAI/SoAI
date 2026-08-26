/* SoAI - Frontend page context ownership [frontend/assets/ts/core/pagecontext/PageContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getClipboardService } from '@core/clipboard.ts';
import { createClipboardApi } from '@core/pagecontext/clipboard/service.ts';
import type { ClipboardApi, NotificationApi, PageContextOptions, SanitizerApi, SanitizerInput, TelemetryService } from '@core/pagecontext/contracts.ts';
import { createNotificationApi } from '@core/pagecontext/notifications/service.ts';
import { createSanitizerApi } from '@core/pagecontext/sanitizer/service.ts';
import { ensureTelemetry } from '@core/pagecontext/telemetry/service.ts';
import { securityApi } from '@core/security/public.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { showNotification, type NotificationType } from '@core/ui/notifications/notifications.ts';

const ensurePageId = (value: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error('PageContext requires a page identifier');
    }
    return trimmed;
};

class PageContext {
    #pageId: string;
    #clipboard: ClipboardApi;
    #sanitizer: SanitizerApi;
    #notifications: NotificationApi;
    #telemetry: TelemetryService;

    constructor({
        pageId,
        clipboard = getClipboardService(),
        sanitizer = securityApi,
        notifier = (message: string, type: NotificationType, duration: number): void => {
            showNotification(message, type, duration);
        },
        telemetry: telemetryOverride = telemetry
    }: PageContextOptions) {
        this.#pageId = ensurePageId(pageId);
        this.#clipboard = createClipboardApi(clipboard);
        this.#sanitizer = createSanitizerApi(sanitizer);
        this.#notifications = createNotificationApi(notifier, this.#pageId);
        this.#telemetry = ensureTelemetry(telemetryOverride);
    }

    get id(): string {
        return this.#pageId;
    }

    get clipboard(): ClipboardApi {
        return this.#clipboard;
    }

    get sanitizer(): SanitizerApi {
        return this.#sanitizer;
    }

    get notifications(): NotificationApi {
        return this.#notifications;
    }

    get telemetry(): TelemetryService {
        return this.#telemetry;
    }
}

export { PageContext };

export type { PageContextOptions, ClipboardApi, SanitizerApi, SanitizerInput, NotificationApi, TelemetryService };
