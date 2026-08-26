/* SoAI - Chat feature inline multimedia URLs [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaUrls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation } from '@core/environment/public.ts';
import { buildFileExplorerDeepLink, buildFileExplorerSearchLink, resolveFileExplorerDeepLinkPath } from '@core/fileexplorerbrowser/deepLinks.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { resolveHttpUrl } from '@core/security/public.ts';

const resolveInlineMediaHttpHref = (rawHref: string): string => {
    const resolved = resolveHttpUrl(rawHref, getLocation().href);
    if (resolved === null && !toTrimmedString(rawHref)) {
        throw new Error('Inline media href is required');
    }
    if (resolved === null) {
        throw new Error('Inline media href is invalid');
    }
    return resolved;
};

export { buildFileExplorerDeepLink, buildFileExplorerSearchLink, resolveFileExplorerDeepLinkPath, resolveInlineMediaHttpHref };
