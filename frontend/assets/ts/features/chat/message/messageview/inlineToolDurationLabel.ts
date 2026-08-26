/* SoAI - Chat feature inline tool duration label [frontend/assets/ts/features/chat/message/messageview/inlineToolDurationLabel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveInlineActivityDurationLabel } from '@features/chat/message/messageview/inlineActivityDuration.ts';

type InlineToolDurationStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'error';

const resolveInlineToolActivityDurationLabel = (inputArguments: { status: InlineToolDurationStatus; durationMs?: number | null | undefined; startedAtMs?: number | undefined; nowMs?: number | undefined }): string | null => {
    const normalizedStatus = inputArguments.status;
    const durationMs = typeof inputArguments.durationMs === 'number' && Number.isFinite(inputArguments.durationMs) ? Math.max(0, Math.floor(inputArguments.durationMs)) : undefined;

    return resolveInlineActivityDurationLabel({
        status: normalizedStatus,
        durationMs,
        startedAtMs: inputArguments.startedAtMs,
        nowMs: inputArguments.nowMs
    });
};

export { resolveInlineToolActivityDurationLabel };
