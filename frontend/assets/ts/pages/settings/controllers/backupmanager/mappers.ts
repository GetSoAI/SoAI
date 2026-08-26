/* SoAI - Settings page control layer backup manager mapping [frontend/assets/ts/pages/settings/controllers/backupmanager/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { normalizeProgressPercent } from '@core/primitives/progress.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import type { BackupCompletionPayload, BackupProgressPayload } from '@pages/settings/controllers/backupmanager/contracts.ts';

const parseBackupProgressPayload = (value: JsonValue): BackupProgressPayload | null => {
    if (!isObject(value)) {
        return null;
    }
    const taskId = toTrimmedString(value['taskId']);
    if (!taskId) {
        return null;
    }
    const progressValue = value['progress'];
    const percent = normalizeProgressPercent(progressValue) ?? 0;
    return { taskId, percent, message: toTrimmedString(value['message']) };
};

const parseBackupCompletionPayload = (value: JsonValue): BackupCompletionPayload | null => {
    if (!isObject(value)) {
        return null;
    }
    const taskId = toTrimmedString(value['taskId']);
    if (!taskId) {
        return null;
    }
    return { taskId, success: value['success'] === true, message: toTrimmedString(value['message']) };
};

export { parseBackupCompletionPayload, parseBackupProgressPayload };
