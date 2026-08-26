/* SoAI - Offline entitlement browser file contract [frontend/assets/ts/core/licensing/offlineEntitlementFile.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const MAXIMUM_OFFLINE_ENTITLEMENT_BYTES = 65_536;
const OFFLINE_ENTITLEMENT_MEDIA_TYPES: ReadonlySet<string> = new Set(['application/json', 'application/octet-stream', 'application/vnd.soai.offline-entitlement+json']);

const requireOfflineEntitlementFile = (file: File): void => {
    if (!file.name.endsWith('.soailicense')) {
        throw new TypeError('Offline entitlement filename is invalid.');
    }
    if (file.size < 1 || file.size > MAXIMUM_OFFLINE_ENTITLEMENT_BYTES) {
        throw new TypeError('Offline entitlement size is invalid.');
    }
    const mediaType = file.type.trim().toLowerCase();
    if (mediaType && !OFFLINE_ENTITLEMENT_MEDIA_TYPES.has(mediaType)) {
        throw new TypeError('Offline entitlement media type is invalid.');
    }
};

export { requireOfflineEntitlementFile };
