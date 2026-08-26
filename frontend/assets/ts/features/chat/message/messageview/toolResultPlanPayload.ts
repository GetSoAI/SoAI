/* SoAI - Chat feature tool result plan payload [frontend/assets/ts/features/chat/message/messageview/toolResultPlanPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface ToolResultPlanPayload {
    markdown: string;
    revision: number | null;
    title: string | null;
}

const MAX_PLAN_TITLE_LENGTH = 120;

const readPlanMarkdown = (record: JsonObject): string | null => {
    const value = record['markdown'];
    if (!isString(value) || !value.trim()) {
        return null;
    }
    return value;
};

const readPlanTitle = (record: JsonObject): string | null => {
    const value = record['title'];
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    return trimmed ? trimmed.slice(0, MAX_PLAN_TITLE_LENGTH) : null;
};

const readPlanRevision = (record: JsonObject): number | null => {
    const value = record['revision'];
    if (!isFiniteNumber(value) || !Number.isInteger(value) || value < 0) {
        return null;
    }
    return value;
};

const resolveToolResultPlanPayload = (payload: JsonValue | undefined): ToolResultPlanPayload | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const markdown = readPlanMarkdown(payload);
    if (markdown === null) {
        return null;
    }
    return {
        markdown,
        revision: readPlanRevision(payload),
        title: readPlanTitle(payload)
    };
};

export { MAX_PLAN_TITLE_LENGTH, resolveToolResultPlanPayload };
export type { ToolResultPlanPayload };
