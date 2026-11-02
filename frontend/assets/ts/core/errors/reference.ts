/* SoAI - Stable public correlation references for browser failures [frontend/assets/ts/core/errors/reference.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { isString } from '@core/typeGuards.ts';

const CLIENT_REFERENCE_LENGTH = 12;
const failureReferences = new WeakMap<Error, string>();

const getErrorReference = (error: Error): string => {
    let reference = failureReferences.get(error);
    if (reference === undefined) {
        const traceId = error instanceof APIError ? error.traceId : undefined;
        reference = isString(traceId) && traceId.trim() ? traceId.trim() : generateSecureId({ format: 'hex' }).slice(0, CLIENT_REFERENCE_LENGTH);
        failureReferences.set(error, reference);
    }
    return reference;
};

export { getErrorReference };
