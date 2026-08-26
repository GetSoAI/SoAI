/* SoAI - Tool result media hydration policy [frontend/assets/ts/features/chat/toolactivity/toolResultMediaHydration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { hasToolResultInlineMediaBase64, hasToolResultOmittedInlineMediaBase64, resolveToolResultMediaHydrationRank } from '@features/chat/toolactivity/toolMediaSignatures.ts';

const toolResultOptions = (projection: ToolActivityItem | null): { toolLeafName?: string } => (projection === null ? {} : { toolLeafName: projection.toolName });

const toolResultHasInlineMedia = (value: JsonValue | undefined, options: { toolLeafName?: string } = {}): boolean => hasToolResultInlineMediaBase64(value, options);

const toolResultHasOmittedInlineMedia = (value: JsonValue | undefined, options: { toolLeafName?: string } = {}): boolean => hasToolResultOmittedInlineMediaBase64(value, options);

const toolProjectionNeedsMediaHydration = (projection: ToolActivityItem | null): boolean => {
    return projection !== null && toolResultHasOmittedInlineMedia(projection.result, toolResultOptions(projection));
};

const toolProjectionHasHydratedInlineMedia = (projection: ToolActivityItem | null): boolean => {
    return projection !== null && toolResultHasInlineMedia(projection.result, toolResultOptions(projection));
};

const compareToolResultMediaHydration = (existing: JsonValue | undefined, incoming: JsonValue | undefined, options: { toolLeafName?: string } = {}): number => {
    const existingRank = resolveToolResultMediaHydrationRank(existing, options);
    const incomingRank = resolveToolResultMediaHydrationRank(incoming, options);
    if (incomingRank < existingRank) {
        return -1;
    }
    if (incomingRank > existingRank) {
        return 1;
    }
    return 0;
};

export { compareToolResultMediaHydration, toolProjectionHasHydratedInlineMedia, toolProjectionNeedsMediaHydration, toolResultHasInlineMedia, toolResultHasOmittedInlineMedia };
