/* SoAI - Frontend system limits API contracts [frontend/assets/ts/core/api/contracts/systemLimitsContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface SystemLimits {
    maxFileUploadBytes: number;
    maxFileUploadMb: number;
    cameraVisionUploadEnabled: boolean;
    cameraVisionImageOptimizationEnabled: boolean;
}

const decodeSystemLimits = (value: ApiResponsePayload): SystemLimits => {
    const record = requireRecord(value, 'System limits response');
    return {
        maxFileUploadBytes: readRequiredFiniteNumberValue(record['max_file_upload_bytes'], 'System limits response.max_file_upload_bytes'),
        maxFileUploadMb: readRequiredFiniteNumberValue(record['max_file_upload_mb'], 'System limits response.max_file_upload_mb'),
        cameraVisionUploadEnabled: readRequiredBooleanValue(record['camera_vision_upload_enabled'], 'System limits response.camera_vision_upload_enabled'),
        cameraVisionImageOptimizationEnabled: readRequiredBooleanValue(record['camera_vision_image_optimization_enabled'], 'System limits response.camera_vision_image_optimization_enabled')
    };
};

const serializeSystemLimitsCache = (limits: SystemLimits): JsonObject => ({
    'max_file_upload_bytes': limits.maxFileUploadBytes,
    'max_file_upload_mb': limits.maxFileUploadMb,
    'camera_vision_upload_enabled': limits.cameraVisionUploadEnabled,
    'camera_vision_image_optimization_enabled': limits.cameraVisionImageOptimizationEnabled
});

export { decodeSystemLimits, serializeSystemLimitsCache };
export type { SystemLimits };
