/* SoAI - Chat knowledge attachment readiness predicates [frontend/assets/ts/features/chat/knowledgeAttachmentReadiness.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';

const completedKnowledgeItemCount = (knowledge: KnowledgeAttachmentSummary): number => knowledge.statusCounts['completed'] ?? 0;

const isClaimableKnowledgeDraft = (knowledge: KnowledgeAttachmentSummary): boolean => knowledge.processingState === 'ready' && completedKnowledgeItemCount(knowledge) > 0;

export { completedKnowledgeItemCount, isClaimableKnowledgeDraft };
