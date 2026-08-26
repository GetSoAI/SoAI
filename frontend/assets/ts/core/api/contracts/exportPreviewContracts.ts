/* SoAI - Frontend export preview snapshot contracts [frontend/assets/ts/core/api/contracts/exportPreviewContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ExportPreviewSnapshotPayload {
    filename: string;
    downloadUrl: string;
    previewText: string;
    previewTruncated: boolean;
}

const decodeExportPreviewSnapshot = (value: JsonValue, label: string): ExportPreviewSnapshotPayload => {
    const record = requireRecord(value, label);
    return {
        filename: readRequiredTrimmedString(record, 'filename', `${label}.filename`),
        downloadUrl: readRequiredTrimmedString(record, 'download_url', `${label}.download_url`),
        previewText: typeof record['preview_text'] === 'string' ? record['preview_text'] : readRequiredTrimmedString(record, 'preview_text', `${label}.preview_text`),
        previewTruncated: readRequiredBooleanValue(record['preview_truncated'], `${label}.preview_truncated`)
    };
};

export { decodeExportPreviewSnapshot };
export type { ExportPreviewSnapshotPayload };
