/* SoAI - Chat knowledge attachment preview payload parsing [frontend/assets/ts/features/chat/message/knowledgeAttachmentPreviewPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentPreviewResponse } from '@core/api/contracts/webuiAttachmentContracts.ts';

const resolveKnowledgeAttachmentPreviewText = (payload: KnowledgeAttachmentPreviewResponse): string => payload.text ?? '';

const resolveKnowledgeAttachmentPreviewTitle = (payload: KnowledgeAttachmentPreviewResponse, fallback: string): string => payload.document.filename || fallback;

export { resolveKnowledgeAttachmentPreviewText, resolveKnowledgeAttachmentPreviewTitle };
