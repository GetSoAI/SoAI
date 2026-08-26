/* SoAI - Shared frontend routing pages base page core mapping [frontend/assets/ts/core/routing/pages/basepagecore/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn, isObject, isString } from '@core/typeGuards.ts';

interface ItemIdentityCandidate {
    id?: string | number | null | undefined;
    name?: string | number | null | undefined;
}

const normalizeItemId = (item: ItemIdentityCandidate | null | undefined): string | null => {
    if (!isObject(item)) {
        return null;
    }
    const idValue = hasOwn(item, 'id') && 'id' in item ? item.id : null;
    if ((isString(idValue) || typeof idValue === 'number') && String(idValue)) {
        return String(idValue);
    }
    const nameValue = hasOwn(item, 'name') && 'name' in item ? item.name : null;
    if ((isString(nameValue) || typeof nameValue === 'number') && String(nameValue)) {
        return String(nameValue);
    }
    return null;
};

const describeUiTarget = (target: string | Element | null | undefined): string => {
    if (isString(target)) {
        return target;
    }
    if (target instanceof Element) {
        const idValue = hasOwn(target, 'id') && 'id' in target ? target.id : null;
        if (isString(idValue) && idValue.trim()) {
            return idValue;
        }
    }
    return '<unknown>';
};

export { describeUiTarget, normalizeItemId };
