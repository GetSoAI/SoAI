/* SoAI - Shared UI primitives adapters [frontend/assets/ts/core/uiprimitives/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getIconFromStringSync } from '@core/ui/icons/iconservice/public.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { parseNotificationType } from '@core/ui/notifications/notificationTypeParsing.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import { securityApi, type TrustedHtml } from '@core/security/public.ts';
import type { EscapableValue, IconOptions, NotifyOptions } from '@core/uiprimitives/types.ts';

const safeStr = (value: EscapableValue): string => {
    if (value == null) {
        return '';
    }
    return typeof value === 'object' ? value.html : String(value);
};

const escapeHtml = (value: EscapableValue): string => {
    return securityApi.escapeHtml(safeStr(value));
};

const escapeAttribute = (value: EscapableValue): string => {
    return securityApi.escapeAttribute(safeStr(value));
};

const notify = (message: string, type: string = 'info', options: NotifyOptions = {}): void => {
    showNotification(message, parseNotificationType(type), isFiniteNumber(options.duration) ? options.duration : null);
};

const iconResolver = (name: string, options: IconOptions = {}): TrustedHtml => {
    const resolvedSize = options.size;
    const size = isFiniteNumber(resolvedSize) ? resolvedSize : isString(resolvedSize) ? Number(resolvedSize) : undefined;

    return getIconFromStringSync(name, {
        className: isString(options.className) ? options.className : undefined,
        size: isFiniteNumber(size) ? size : undefined
    });
};

export { escapeAttribute, escapeHtml, iconResolver, notify, safeStr };
