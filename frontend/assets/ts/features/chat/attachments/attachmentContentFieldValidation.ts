/* SoAI - Chat attachment content part field validation [frontend/assets/ts/features/chat/attachments/attachmentContentFieldValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isNumber, isString } from '@core/typeGuards.ts';

type BackendMessageRecord = Record<string, JsonValue | undefined>;

const SOAI_ATTACHMENT_ID_MAX_LENGTH = 128;
const SOAI_FILE_NAME_MAX_LENGTH = 512;
const SOAI_FILE_MIME_TYPE_MAX_LENGTH = 256;
const SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH = 32;
const SOAI_KNOWLEDGE_TITLE_MAX_LENGTH = 512;
const SOAI_KNOWLEDGE_TYPE_MAX_LENGTH = 64;

const hasOnlyFields = (part: BackendMessageRecord, fields: Set<string>): boolean => {
    return Object.keys(part).every((fieldName) => fields.has(fieldName));
};

const normalizeRequiredTextField = (part: BackendMessageRecord, fieldName: string, maxLength: number): string | null => {
    const value = part[fieldName];
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed || value.includes('\0') || trimmed.length > maxLength) {
        return null;
    }
    return trimmed;
};

const normalizeNonNegativeIntegerField = (part: BackendMessageRecord, fieldName: string): number | null => {
    const value = part[fieldName];
    if (!isNumber(value) || !Number.isSafeInteger(value) || value < 0) {
        return null;
    }
    return value;
};

const normalizeOptionalNonNegativeIntegerField = (part: BackendMessageRecord, fieldName: string): number | null | undefined => {
    const value = part[fieldName];
    if (value === undefined || value === null) {
        return null;
    }
    if (!isNumber(value) || !Number.isSafeInteger(value) || value < 0) {
        return undefined;
    }
    return value;
};

export { hasOnlyFields, normalizeNonNegativeIntegerField, normalizeOptionalNonNegativeIntegerField, normalizeRequiredTextField, SOAI_ATTACHMENT_ID_MAX_LENGTH, SOAI_FILE_MIME_TYPE_MAX_LENGTH, SOAI_FILE_NAME_MAX_LENGTH, SOAI_FILE_PREVIEW_TYPE_MAX_LENGTH, SOAI_KNOWLEDGE_TITLE_MAX_LENGTH, SOAI_KNOWLEDGE_TYPE_MAX_LENGTH };
export type { BackendMessageRecord };
