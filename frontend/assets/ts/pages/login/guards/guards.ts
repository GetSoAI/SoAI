/* SoAI - Login page guards validation [frontend/assets/ts/pages/login/guards/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isObject, isString } from '@core/typeGuards.ts';
import type { LoginResult } from '@pages/login/types.ts';

const isLoginResult = <T>(value: T | JsonValue | null | undefined): value is T & LoginResult => {
    if (!isObject(value)) {
        return false;
    }
    const status = 'status' in value ? value['status'] : undefined;
    const error = 'error' in value ? value['error'] : undefined;
    const retryAfterSeconds = 'retryAfterSeconds' in value ? value['retryAfterSeconds'] : undefined;
    if (status === 'authenticated') {
        const user = 'user' in value ? value['user'] : null;
        return isObject(user) && isString(user['username']) && typeof user['isAdmin'] === 'boolean' && error === undefined && retryAfterSeconds === undefined;
    }
    if (status === 'sessionActivationFailed') {
        return isString(error) && retryAfterSeconds === undefined;
    }
    return status === 'rejected' && isString(error) && (retryAfterSeconds === undefined || isNonNegativeInteger(retryAfterSeconds));
};

export { isLoginResult };
