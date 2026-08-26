/* SoAI - Active page inspection helpers [frontend/assets/ts/core/routing/router/activePage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { hasFunctionProperty, isObject, isString } from '@core/typeGuards.ts';
import type { PageInstance } from '@core/pagehost/types.ts';
import type { PageHostInstance } from '@core/pageoutlet/types.ts';

interface ActivePageEntry {
    name: string;
    instance: PageInstance;
}

interface PageHostContract {
    getCurrent: PageHostInstance['getCurrent'];
}

const isPageHostContract = (value: PageHostInstance | PageHostContract | null): value is PageHostContract => isObject(value) && hasFunctionProperty(value, 'getCurrent');

const isActivePageEntry = (value: { name?: string | undefined; instance?: PageInstance | null | undefined } | null): value is ActivePageEntry => {
    if (!isObject(value)) {
        return false;
    }
    return 'name' in value && isString(value.name) && 'instance' in value && value.instance !== null && value.instance !== undefined;
};

const getActivePageEntry = (): ActivePageEntry | null => {
    const router = requireRouter();
    const pageHostCandidate = router.pageHost;
    if (!isPageHostContract(pageHostCandidate)) {
        return null;
    }
    const current = pageHostCandidate.getCurrent();
    if (!isActivePageEntry(current)) {
        return null;
    }
    return current;
};

const requireActivePageEntry = (): ActivePageEntry => {
    const entry = getActivePageEntry();
    if (!entry) {
        throw new Error('Active page instance is unavailable');
    }
    return entry;
};

export { getActivePageEntry, requireActivePageEntry };
export type { ActivePageEntry };
