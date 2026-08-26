/* SoAI - Inline tool activity status value rendering [frontend/assets/ts/features/chat/message/messageview/inlineToolStatusValueRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface InlineToolStatusValueRenderHost {
    escapeHtml: (unsafe: string) => string;
}

const resolveStatusValueClass = (value: string): string | null => {
    const normalized = value.trim().toLowerCase();
    if (normalized === 'pending') {
        return 'inline-tool-status-value--pending';
    }
    if (normalized === 'in_progress') {
        return 'inline-tool-status-value--in-progress';
    }
    if (normalized === 'running') {
        return 'inline-tool-status-value--running';
    }
    if (normalized === 'completed') {
        return 'inline-tool-status-value--completed';
    }
    if (normalized === 'cancelled') {
        return 'inline-tool-status-value--cancelled';
    }
    if (normalized === 'error') {
        return 'inline-tool-status-value--error';
    }
    return null;
};

const renderInlineToolStatusValue = (host: InlineToolStatusValueRenderHost, key: string, value: JsonValue | undefined): string | null => {
    if (key !== 'status' || !isString(value)) {
        return null;
    }
    const className = resolveStatusValueClass(value);
    if (className === null) {
        return null;
    }
    return `<span class="inline-tool-field-value inline-tool-status-value ${className}">${host.escapeHtml(value)}</span>`;
};

export { renderInlineToolStatusValue };
