/* SoAI - Chat composer draft keepalive request policy [frontend/assets/ts/features/chat/composerdraft/composerDraftKeepalive.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

const KEEPALIVE_BODY_LIMIT_BYTES = 60000;

const resolveComposerDraftKeepaliveOptions = (enabled: boolean | undefined, payload: JsonValue | null | undefined): { keepalive?: boolean } => {
    if (enabled !== true) {
        return {};
    }
    if (payload === undefined) {
        return { keepalive: true };
    }
    const bodySize = new Blob([JSON.stringify(payload)]).size;
    return bodySize <= KEEPALIVE_BODY_LIMIT_BYTES ? { keepalive: true } : {};
};

export { resolveComposerDraftKeepaliveOptions };
