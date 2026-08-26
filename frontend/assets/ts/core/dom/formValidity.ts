/* SoAI - Shared DOM form validity [frontend/assets/ts/core/dom/formValidity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setFieldSurfaceInvalid } from '@core/forms/fieldSurface.ts';

const setControlValidity = (element: HTMLElement, valid: boolean, ownerSelector: string): void => {
    element.setAttribute('aria-invalid', valid ? 'false' : 'true');
    const owner = element.closest(ownerSelector);
    if (!owner) {
        throw new Error(`Control validity owner not found for selector ${ownerSelector}`);
    }
    setFieldSurfaceInvalid(owner, !valid);
};

export { setControlValidity };
