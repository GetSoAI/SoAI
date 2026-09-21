/* SoAI - Exclusive save and reset admission [frontend/assets/ts/core/save/admission.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SaveAdmission } from '@core/save/controller.ts';

const createExclusiveSaveAdmission = (): SaveAdmission => {
    let acquired = false;
    return {
        canAcquire: () => !acquired,
        acquire: () => {
            if (acquired) return null;
            acquired = true;
            let released = false;
            return (): void => {
                if (released) return;
                released = true;
                acquired = false;
            };
        }
    };
};

export { createExclusiveSaveAdmission };
