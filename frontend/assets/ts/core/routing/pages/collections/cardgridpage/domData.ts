/* SoAI - Shared routing DOM data [frontend/assets/ts/core/routing/pages/collections/cardgridpage/domData.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isFunction, isString } from '@core/typeGuards.ts';
import type { CardPageHost, CardWithDataset, EmptyState } from '@core/routing/pages/collections/cardgridpage/contracts.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';

const resolveDataValue = (host: CardPageHost, card: CardWithDataset | null, key: string): string | null => {
    if (!card) return null;
    if (host?.dom?.getData) {
        const resolved = host.dom.getData(card, key);
        return isString(resolved) && resolved ? resolved : resolved ? String(resolved) : null;
    }
    return null;
};

const setDataValue = (host: CardPageHost, card: CardWithDataset | null, key: string, value: string): void => {
    if (!card || !value) return;
    if (host?.dom?.setData) {
        host.dom.setData(card, key, value);
    }
};

const applyEmptyStates = (host: CardPageHost, states: EmptyState[] | null, filtered: (ResourceIncomingValue | null)[], all: (ResourceIncomingValue | null)[]): void => {
    if (!isArray(states) || !states.length) return;
    for (const state of states) {
        const target = state?.element || (state?.selector ? host.optionalUI(state.selector) : null);
        if (!target) continue;
        const visible = isFunction(state.visibleWhen) ? state.visibleWhen({ filtered, all }) : Boolean(state.visibleWhen);
        host.toggleHidden(target, !visible);
    }
};

export { applyEmptyStates, resolveDataValue, setDataValue };
