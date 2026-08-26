/* SoAI - Typed preview-contract diagnostics parsing and message extraction [frontend/assets/ts/features/chat/previewContractState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { PreviewContractDiagnosticsPayload } from '@features/chat/contentPreviewContracts.ts';
import { isPreviewContractReasonCode } from '@features/chat/preview/previewReferenceContract.ts';

const resolvePreviewContractPayload = (value: JsonValue | undefined): PreviewContractDiagnosticsPayload | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }
    const reasonCodeValue = value['reason_code'];
    const detailValue = value['detail'];
    const repairAttemptedValue = value['repair_attempted'];
    const repairSucceededValue = value['repair_succeeded'];
    return {
        reasonCode: isPreviewContractReasonCode(reasonCodeValue) ? reasonCodeValue : null,
        detail: isString(detailValue) && detailValue.trim() ? detailValue.trim() : null,
        repairAttempted: repairAttemptedValue === true,
        repairSucceeded: repairSucceededValue === true
    };
};

export { resolvePreviewContractPayload };
