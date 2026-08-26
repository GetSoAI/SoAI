/* SoAI - Shared auth session failure [frontend/assets/ts/core/auth/sessionFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { isString } from '@core/typeGuards.ts';

const SESSION_INVALID_CODES = new Set(['authentication_error', 'not_authenticated', 'session_expired', 'invalid_token', 'unauthorized']);
const SETUP_REQUIRED_AUTH_EVENT = 'soai:auth:setup-required';

const isSessionInvalidApiError = <T>(error: T): boolean => {
    if (!(error instanceof APIError)) {
        return false;
    }
    const codeValue = error.code;
    const code = isString(codeValue) ? codeValue.toLowerCase() : '';
    if (error.status === 401) {
        return !code || SESSION_INVALID_CODES.has(code);
    }
    if (error.status === 403) {
        return code === 'session_expired' || code === 'invalid_token';
    }
    return false;
};

const isSetupRequiredApiError = <T>(error: T): boolean => {
    if (!(error instanceof APIError) || error.status !== 403) {
        return false;
    }
    const code = isString(error.code) ? error.code.toLowerCase() : '';
    const reason = isString(error.reason) ? error.reason.toLowerCase() : '';
    return code === 'setup_required' || reason === 'setup_required';
};

export { SETUP_REQUIRED_AUTH_EVENT, isSessionInvalidApiError, isSetupRequiredApiError };
