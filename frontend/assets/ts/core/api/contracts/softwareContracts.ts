/* SoAI - Shared frontend API contract boundary software contracts [frontend/assets/ts/core/api/contracts/softwareContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';

interface SoftwareUpdateCheckResponse {
    updateAvailable: boolean;
    currentVersion: string | null;
    latestVersion: string | null;
    message: string | null;
    releaseUrl: string | null;
    publishedAt: string | null;
    releaseNotes: string | null;
    platformId: string | null;
    deliveryType: SoftwareUpdateDeliveryType;
    installSupported: boolean;
}

interface SoftwareUpdateAcceptedResponse {
    status: 'accepted';
    message: string;
    platformId: string;
    deliveryType: Exclude<SoftwareUpdateDeliveryType, null>;
}

type SoftwareUpdateDeliveryType = 'complete_archive' | 'installer' | null;

const readSoftwareUpdateDeliveryType = <T>(value: T, label: string): SoftwareUpdateDeliveryType => {
    if (value === null) {
        return null;
    }
    if (value === 'complete_archive') {
        return 'complete_archive';
    }
    if (value === 'installer') {
        return 'installer';
    }
    throw new TypeError(`${label} must be complete_archive, installer, or null.`);
};

const decodeSoftwareUpdateCheckResponse = (value: ApiResponsePayload): SoftwareUpdateCheckResponse => {
    const record = requireRecord(value, 'Software update check response');
    return {
        updateAvailable: readRequiredBooleanValue(record['update_available'], 'Software update check response.update_available'),
        currentVersion: readNullableTrimmedStringValue(record['current_version'], 'Software update check response.current_version'),
        latestVersion: readNullableTrimmedStringValue(record['latest_version'], 'Software update check response.latest_version'),
        message: readNullableTrimmedStringValue(record['message'], 'Software update check response.message'),
        releaseUrl: readNullableTrimmedStringValue(record['release_url'], 'Software update check response.release_url'),
        publishedAt: readNullableTrimmedStringValue(record['published_at'], 'Software update check response.published_at'),
        releaseNotes: readNullableTrimmedStringValue(record['release_notes'], 'Software update check response.release_notes'),
        platformId: readNullableTrimmedStringValue(record['platform_id'], 'Software update check response.platform_id'),
        deliveryType: readSoftwareUpdateDeliveryType(record['delivery_type'], 'Software update check response.delivery_type'),
        installSupported: readRequiredBooleanValue(record['install_supported'], 'Software update check response.install_supported')
    };
};

const decodeSoftwareUpdateAcceptedResponse = (value: ApiResponsePayload): SoftwareUpdateAcceptedResponse => {
    const record = requireRecord(value, 'Software update response');
    const status = readRequiredTrimmedString(record, 'status', 'Software update response.status');
    if (status !== 'accepted') {
        throw new TypeError('Software update response.status must be accepted.');
    }
    const deliveryType = readSoftwareUpdateDeliveryType(record['delivery_type'], 'Software update response.delivery_type');
    if (deliveryType === null) {
        throw new TypeError('Software update response.delivery_type cannot be null.');
    }
    return {
        status,
        message: readRequiredTrimmedString(record, 'message', 'Software update response.message'),
        platformId: readRequiredTrimmedString(record, 'platform_id', 'Software update response.platform_id'),
        deliveryType
    };
};

export { decodeSoftwareUpdateAcceptedResponse, decodeSoftwareUpdateCheckResponse };
export type { SoftwareUpdateAcceptedResponse, SoftwareUpdateCheckResponse, SoftwareUpdateDeliveryType };
