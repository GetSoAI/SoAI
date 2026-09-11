/* SoAI - Updates page system payload parser [frontend/assets/ts/pages/updates/controllers/UpdatesSystemPayloadParser.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractApiErrorMessage } from '@core/errors/coerce.ts';
import { toString } from '@core/normalize.ts';
import type { SoftwareUpdateCheckResponse } from '@core/api/contracts/softwareContracts.ts';
import type { NormalizedUpdatePayload } from '@pages/updates/types.ts';

const normalizeUpdateText = (value: string | null): string => toString(value).trim();

const normalizeUpdatePayload = (payload: SoftwareUpdateCheckResponse | null): NormalizedUpdatePayload | null => {
    if (!payload) {
        return null;
    }
    return {
        updateAvailable: payload.updateAvailable,
        currentVersion: normalizeUpdateText(payload.currentVersion),
        latestVersion: normalizeUpdateText(payload.latestVersion),
        message: normalizeUpdateText(payload.message),
        releaseUrl: normalizeUpdateText(payload.releaseUrl),
        releaseNotes: payload.releaseNotes ?? '',
        publishedAt: normalizeUpdateText(payload.publishedAt),
        platformId: normalizeUpdateText(payload.platformId),
        deliveryType: payload.deliveryType,
        installSupported: payload.installSupported
    };
};

const normalizeUpdatesSystemErrorMessage = (error: Error | null, maxLength: number): string => {
    const message = extractUpdatesSystemErrorMessage(error).replace(/\s+/g, ' ').trim();
    if (!message) {
        return '';
    }
    if (maxLength <= 0) {
        return '';
    }
    if (message.length <= maxLength) {
        return message;
    }
    if (maxLength <= 3) {
        return '.'.repeat(maxLength);
    }
    return `${message.slice(0, maxLength - 3)}...`;
};

const extractUpdatesSystemErrorMessage = (error: Error | null): string => {
    const message = extractApiErrorMessage(error);
    return message ?? '';
};

export { normalizeUpdatePayload, normalizeUpdatesSystemErrorMessage };
