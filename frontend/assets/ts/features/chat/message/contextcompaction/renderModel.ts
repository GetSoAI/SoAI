/* SoAI - Context compaction boundary render model [frontend/assets/ts/features/chat/message/contextcompaction/renderModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { hasManualContextCompactionBoundaryMarker, isContextCompactionBoundaryMessage, isInactiveContextCompactionBoundaryMessage } from '@features/chat/message/contextcompaction/detection.ts';

type ContextCompactionBoundaryRenderModel = {
    isBoundary: boolean;
    rootClassName: string;
    contentClassName: string;
    renderActions: boolean;
};

const COMPACTION_BOUNDARY_ROOT_CLASS = ' chat-message--compaction-boundary';
const COMPACTION_BOUNDARY_ACTIVE_ROOT_CLASS = `${COMPACTION_BOUNDARY_ROOT_CLASS} chat-message--compaction-boundary-active`;
const COMPACTION_BOUNDARY_INACTIVE_ROOT_CLASS = `${COMPACTION_BOUNDARY_ROOT_CLASS} chat-message--compaction-boundary-inactive`;
const COMPACTION_BOUNDARY_CONTENT_CLASS = ' message-content--compaction-boundary';

const resolveContextCompactionBoundaryRenderModel = (message: ChatMessage): ContextCompactionBoundaryRenderModel => {
    const isBoundary = isContextCompactionBoundaryMessage(message);
    if (!isBoundary) {
        return {
            isBoundary: false,
            rootClassName: '',
            contentClassName: '',
            renderActions: true
        };
    }
    const hasPersistedMarker = hasManualContextCompactionBoundaryMarker(message);
    const isInactive = isInactiveContextCompactionBoundaryMessage(message);
    return {
        isBoundary: true,
        rootClassName: isInactive ? COMPACTION_BOUNDARY_INACTIVE_ROOT_CLASS : COMPACTION_BOUNDARY_ACTIVE_ROOT_CLASS,
        contentClassName: COMPACTION_BOUNDARY_CONTENT_CLASS,
        renderActions: hasPersistedMarker && !isInactive
    };
};

export { resolveContextCompactionBoundaryRenderModel };
export type { ContextCompactionBoundaryRenderModel };
