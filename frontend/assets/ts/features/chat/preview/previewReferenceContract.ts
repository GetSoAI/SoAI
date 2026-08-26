/* SoAI - Canonical WebUI preview reference contract values [frontend/assets/ts/features/chat/preview/previewReferenceContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAllowedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ContentPreviewReasonCode, ContentPreviewReferenceType, ContentPreviewStatus, PreviewContractReasonCode } from '@features/chat/contentPreviewContracts.ts';

const PREVIEW_REFERENCE_TYPES: readonly ContentPreviewReferenceType[] = ['absolute_path', 'virtual_path', 'remote_url'];
const CONTENT_PREVIEW_STATUSES: readonly ContentPreviewStatus[] = ['failed', 'disabled'];
const CONTENT_PREVIEW_REASON_CODES: readonly ContentPreviewReasonCode[] = ['not_found', 'access_denied', 'invalid_reference', 'request_failed', 'upstream_not_found', 'upstream_gone', 'unsupported', 'previews_disabled'];
const PREVIEW_CONTRACT_REASON_CODES: readonly PreviewContractReasonCode[] = ['missing_preview_reference', 'noncanonical_reference_syntax', 'absolute_path_preview_scope_unavailable', 'invalid_remote_url', 'invalid_absolute_path_reference', 'invalid_virtual_path_reference'];

const isContentPreviewReferenceType = (value: JsonValue | null | undefined): value is ContentPreviewReferenceType => isAllowedStringValue(value, PREVIEW_REFERENCE_TYPES);

const isContentPreviewStatus = (value: JsonValue | null | undefined): value is ContentPreviewStatus => isAllowedStringValue(value, CONTENT_PREVIEW_STATUSES);

const isContentPreviewReasonCode = (value: JsonValue | null | undefined): value is ContentPreviewReasonCode => isAllowedStringValue(value, CONTENT_PREVIEW_REASON_CODES);

const isPreviewContractReasonCode = (value: JsonValue | null | undefined): value is PreviewContractReasonCode => isAllowedStringValue(value, PREVIEW_CONTRACT_REASON_CODES);

export { CONTENT_PREVIEW_REASON_CODES, CONTENT_PREVIEW_STATUSES, PREVIEW_CONTRACT_REASON_CODES, PREVIEW_REFERENCE_TYPES, isContentPreviewReasonCode, isContentPreviewReferenceType, isContentPreviewStatus, isPreviewContractReasonCode };
