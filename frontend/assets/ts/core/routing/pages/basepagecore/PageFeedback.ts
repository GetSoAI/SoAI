/* SoAI - Routed page notification and operational-error ownership [frontend/assets/ts/core/routing/pages/basepagecore/PageFeedback.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { coerceErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface PageErrorOptions {
    notify?: boolean;
    rethrow?: boolean;
    severity?: 'debug' | 'info' | 'warn' | 'error';
}

class PageFeedback {
    readonly #pageId: string;
    readonly #context: PageContext;

    constructor(pageId: string, context: PageContext) {
        this.#pageId = pageId;
        this.#context = context;
    }

    show(message: string, type: NotificationType = 'info', duration = 3000): void {
        this.#context.notifications.show(message, type, duration);
    }

    error(message: string, duration = 6000): void {
        this.#context.notifications.error(message, duration);
    }

    success(message: string, duration = 3000): void {
        this.#context.notifications.success(message, duration);
    }

    warning(message: string, duration = 4000): void {
        this.#context.notifications.warning(message, duration);
    }

    info(message: string, duration = 3000): void {
        this.#context.notifications.info(message, duration);
    }

    handle(error: Error, context = '', options: PageErrorOptions = {}): void {
        const { notify = false, severity = 'error', rethrow = false } = options;
        const handledByNotifier = notifyHandledOperationError(error);
        const message = coerceErrorMessage(error);
        const formatted = context ? `${context}: ${message}` : message;
        errorHandler[severity](this.#pageId, formatted, error);
        if (notify && !handledByNotifier) {
            const type: NotificationType = severity === 'warn' ? 'warning' : severity === 'error' ? 'error' : 'info';
            this.show(i18n.t('common.errors.operationFailed'), type);
        }
        if (rethrow) {
            throw error;
        }
    }
}

export { PageFeedback };
export type { PageErrorOptions };
export interface PageFeedbackOwnerHost {
    feedback: PageFeedback;
}
