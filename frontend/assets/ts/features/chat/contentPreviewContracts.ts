/* SoAI - Content preview feedback contracts [frontend/assets/ts/features/chat/contentPreviewContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ContentPreviewReferenceType = 'absolute_path' | 'virtual_path' | 'remote_url';
type ContentPreviewStatus = 'failed' | 'disabled';
type ContentPreviewReasonCode = 'not_found' | 'access_denied' | 'invalid_reference' | 'request_failed' | 'upstream_not_found' | 'upstream_gone' | 'unsupported' | 'previews_disabled';
type PreviewContractViolationCode = 'preview_contract_violation';
type PreviewContractReasonCode = 'missing_preview_reference' | 'noncanonical_reference_syntax' | 'absolute_path_preview_scope_unavailable' | 'invalid_remote_url' | 'invalid_absolute_path_reference' | 'invalid_virtual_path_reference';

interface ContentPreviewFeedbackItem {
    referenceType: ContentPreviewReferenceType;
    target: string;
    status: ContentPreviewStatus;
    reasonCode: ContentPreviewReasonCode;
}

interface ContentPreviewFeedbackPayload {
    assistantAtMs: number;
    assistantTurnAtMs: number;
    items: ContentPreviewFeedbackItem[];
}

interface ContentPreviewFeedbackState extends ContentPreviewFeedbackPayload {
    pendingForModel: boolean;
}

interface PreviewContractViolationFeedbackPayload {
    assistantAtMs: number;
    assistantTurnAtMs: number;
    code: PreviewContractViolationCode;
    reasonCode: PreviewContractReasonCode | null;
    detail: string | null;
    repairAttempted: boolean;
    repairSucceeded: boolean;
}

interface PreviewContractDiagnosticsPayload {
    reasonCode: PreviewContractReasonCode | null;
    detail: string | null;
    repairAttempted: boolean;
    repairSucceeded: boolean;
}

export type { ContentPreviewFeedbackItem, ContentPreviewFeedbackPayload, ContentPreviewFeedbackState, ContentPreviewReasonCode, ContentPreviewReferenceType, ContentPreviewStatus, PreviewContractDiagnosticsPayload, PreviewContractReasonCode, PreviewContractViolationCode, PreviewContractViolationFeedbackPayload };
