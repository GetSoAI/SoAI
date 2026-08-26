/* SoAI - Chat feature apply patch header preview [frontend/assets/ts/features/chat/message/messageview/applyPatchHeaderPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { clampToolHeaderPreview } from '@features/chat/toolactivity/payloadTextParsing.ts';
import { resolvePayloadRecord } from '@features/chat/toolactivity/payloadReaders.ts';
import type { InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';

const APPLY_PATCH_INPUT_KEY = 'input';

type PatchPreviewOperation = {
    label: string;
    path: string;
};

const resolvePatchPreviewOperation = (line: string): PatchPreviewOperation | null => {
    const trimmed = line.trim();
    if (trimmed.startsWith('*** Add File: ')) {
        return { label: 'Add file', path: trimmed.slice('*** Add File: '.length).trim() };
    }
    if (trimmed.startsWith('*** Delete File: ')) {
        return { label: 'Delete file', path: trimmed.slice('*** Delete File: '.length).trim() };
    }
    if (trimmed.startsWith('*** Update File: ')) {
        return { label: 'Update file', path: trimmed.slice('*** Update File: '.length).trim() };
    }
    return null;
};

const resolveApplyPatchHeaderPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName !== 'apply_patch' || segment.inputArguments === undefined || segment.inputArguments === null) {
        return null;
    }
    const argumentsRecord = resolvePayloadRecord(segment.inputArguments);
    const input = argumentsRecord !== null ? argumentsRecord[APPLY_PATCH_INPUT_KEY] : null;
    if (!isString(input)) {
        return '';
    }
    const operations = input
        .split('\n')
        .map((line) => resolvePatchPreviewOperation(line))
        .filter((operation): operation is PatchPreviewOperation => operation !== null && operation.path.length > 0);
    const first = operations[0] ?? null;
    if (first === null) {
        return '';
    }
    const suffix = operations.length > 1 ? ` +${String(operations.length - 1)}` : '';
    return clampToolHeaderPreview(`${first.label}: ${first.path}${suffix}`);
};

export { resolveApplyPatchHeaderPreview };
