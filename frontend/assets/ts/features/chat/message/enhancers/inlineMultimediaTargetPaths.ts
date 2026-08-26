/* SoAI - Chat feature inline multimedia target paths [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaTargetPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolvePathLeaf } from '@core/filePathResolution.ts';

const normalizeInlineMediaPathTarget = (target: string): string => target.trim().replace(/\\/g, '/');

const resolveInlineMediaPathLeaf = (target: string): string => {
    return resolvePathLeaf(normalizeInlineMediaPathTarget(target));
};

const resolveInlineMediaLeafTitle = (target: string): string => {
    const leaf = resolveInlineMediaPathLeaf(target);
    return leaf ? leaf : target;
};

export { normalizeInlineMediaPathTarget, resolveInlineMediaLeafTitle, resolveInlineMediaPathLeaf };
