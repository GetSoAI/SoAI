/* SoAI - Inline multimedia preview token routing [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaPreviewTokenResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { PreviewReferenceToken } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';

const WINDOWS_DRIVE_ABSOLUTE_PATH_PATTERN = /^[A-Za-z]:[\\/]/;

const isAbsolutePathPreviewTarget = (target: string): boolean => {
    const normalizedTarget = toTrimmedString(target);
    return normalizedTarget.startsWith('/') || normalizedTarget.startsWith('\\\\') || WINDOWS_DRIVE_ABSOLUTE_PATH_PATTERN.test(normalizedTarget);
};

const resolveInlineMultimediaPreviewTokenRoute = (token: PreviewReferenceToken): PreviewReferenceToken => {
    if (token.type === 'remote_url' && isAbsolutePathPreviewTarget(token.target)) {
        return {
            ...token,
            type: 'absolute_path'
        };
    }
    return token;
};

export { resolveInlineMultimediaPreviewTokenRoute };
