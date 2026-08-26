/* SoAI - Preview-contract stream error presentation helpers [frontend/assets/ts/features/chat/chatstreamservice/streamPreviewContractPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PreviewContractReasonCode } from '@features/chat/contentPreviewContracts.ts';
import { resolvePreviewContractPayload } from '@features/chat/previewContractState.ts';

const translatePreviewContractReason = (reasonCode: PreviewContractReasonCode): string => {
    switch (reasonCode) {
        case 'missing_preview_reference':
            return i18n.t('chat.stream.errors.preview_contract_reason_missing_preview_reference');
        case 'noncanonical_reference_syntax':
            return i18n.t('chat.stream.errors.preview_contract_reason_noncanonical_reference_syntax');
        case 'absolute_path_preview_scope_unavailable':
            return i18n.t('chat.stream.errors.preview_contract_reason_absolute_path_preview_scope_unavailable');
        case 'invalid_remote_url':
            return i18n.t('chat.stream.errors.preview_contract_reason_invalid_remote_url');
        case 'invalid_absolute_path_reference':
            return i18n.t('chat.stream.errors.preview_contract_reason_invalid_absolute_path_reference');
        case 'invalid_virtual_path_reference':
            return i18n.t('chat.stream.errors.preview_contract_reason_invalid_virtual_path_reference');
    }
};

const resolvePreviewContractReasonMessage = (previewContract: JsonValue): string | null => {
    const resolved = resolvePreviewContractPayload(previewContract);
    if (resolved === null || resolved.reasonCode === null) {
        return null;
    }
    return translatePreviewContractReason(resolved.reasonCode);
};

export { resolvePreviewContractReasonMessage };
