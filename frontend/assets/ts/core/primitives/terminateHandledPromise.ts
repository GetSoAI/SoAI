/* SoAI - Shared primitives terminate handled promise [frontend/assets/ts/core/primitives/terminateHandledPromise.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
const terminateHandledPromise = <T>(value: PromiseLike<T>): void => {
    void Promise.resolve(value).catch((error: Error): void => {
        errorHandler.debug('CorePrimitives', 'Terminated handled promise rejected', ensureError(error));
    });
};

export { terminateHandledPromise };
