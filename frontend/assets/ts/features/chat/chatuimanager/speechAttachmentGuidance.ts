/* SoAI - Chat media attachment speech setup guidance [frontend/assets/ts/features/chat/chatuimanager/speechAttachmentGuidance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createSpeechMediaSelectionView } from '@core/speechsetup/selectionView.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const syncSpeechAttachmentGuidance = (context: ChatUIManagerContext, preview: HTMLElement, attachments: readonly ChatAttachment[]): void => {
    if (context.state.speechSetupSelection === null) {
        const controller = new AbortController();
        context.state.speechSetupAbortController = controller;
        context.state.speechSetupSelection = createSpeechMediaSelectionView(preview, controller.signal, 'composer');
    }
    context.state.speechSetupSelection(
        attachments.map((attachment) => attachment.mimeType ?? attachment.type),
        attachments.some((attachment) => attachment.missingCapabilities?.includes('speech_to_text')) || (context.dependencies.drafts.getDraftKnowledgeAttachments()?.some((summary) => summary.missingCapabilities?.includes('speech_to_text')) ?? false)
    );
};

export { syncSpeechAttachmentGuidance };
