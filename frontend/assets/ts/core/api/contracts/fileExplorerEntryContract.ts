/* SoAI - Shared File Explorer entry response contract [frontend/assets/ts/core/api/contracts/fileExplorerEntryContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerEntryResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { isFileEntryTypeId } from '@core/fileexplorerbrowser/entryTypeMappings.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredPresentStringValue, readRequiredSignedEpochMsValue, readRequiredStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const decodeFileExplorerEntry = (value: JsonValue, label: string): FileExplorerEntryResponse => {
    const record = requireRecord(value, label);
    const typeId = readRequiredTrimmedString(record, 'type_id', `${label}.type_id`);
    if (!isFileEntryTypeId(typeId)) throw new TypeError(`${label}.type_id is unsupported.`);
    return {
        name: readRequiredPresentStringValue(record['name'], `${label}.name`),
        isDirectory: readRequiredBooleanValue(record['is_directory'], `${label}.is_directory`),
        size: readRequiredNonNegativeIntegerValue(record['size'], `${label}.size`),
        modifiedAtMs: readRequiredSignedEpochMsValue(record['modified_at_ms'], `${label}.modified_at_ms`),
        mimeType: readRequiredStringValue(record['mime_type'], `${label}.mime_type`),
        typeId,
        typeRank: readRequiredNonNegativeIntegerValue(record['type_rank'], `${label}.type_rank`),
        permissions: readRequiredStringValue(record['permissions'], `${label}.permissions`)
    };
};

export { decodeFileExplorerEntry };
