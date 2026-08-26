/* SoAI - Frontend application window identity [frontend/assets/ts/app/critical/windowIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { windowIdentity } from '@core/runtime/windowIdentity.ts';

const initializeWindowIdentity = (): void => {
    windowIdentity.ready();
};

export { initializeWindowIdentity };
