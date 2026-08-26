/* SoAI - Shared inline multimedia reference title resolution [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaReferenceTitle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { PreviewReferenceType } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';
import { resolveInlineMediaPathLeaf } from '@features/chat/message/enhancers/inlineMultimediaTargetPaths.ts';

const resolveInlineMultimediaReferenceTitle = (descriptor: { type: PreviewReferenceType | null; target: string; label: string | null }): string | null => {
    const label = toTrimmedString(descriptor.label ?? '');
    if (label) {
        return label;
    }
    if (descriptor.type === 'absolute_path') {
        return resolveInlineMediaPathLeaf(descriptor.target) || i18n.t('chat.inlinePreviews.absolutePathTitle');
    }
    if (descriptor.type === 'virtual_path') {
        return resolveInlineMediaPathLeaf(descriptor.target) || i18n.t('chat.inlinePreviews.virtualPathTitle');
    }
    if (descriptor.type === 'remote_url') {
        return i18n.t('chat.inlinePreviews.remoteUrlTitle');
    }
    return null;
};

export { resolveInlineMultimediaReferenceTitle };
