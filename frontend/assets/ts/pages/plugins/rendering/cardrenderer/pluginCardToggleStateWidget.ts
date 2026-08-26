/* SoAI - Plugin card toggle state rendering [frontend/assets/ts/pages/plugins/rendering/cardrenderer/pluginCardToggleStateWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PLUGIN_TOGGLE_ENABLED_STATUSES } from '@core/state/pluginStatus.ts';
import { isString } from '@core/typeGuards.ts';

function resolveToggleChecked(isEnabled: boolean | undefined, pluginState: string | undefined, forceUnchecked: boolean, pendingToggleTarget: boolean | null | undefined): boolean {
    const normalizedState = isString(pluginState) ? pluginState.toUpperCase() : '';
    if (forceUnchecked || normalizedState === 'STOPPING') {
        return false;
    }
    if (pendingToggleTarget === true || pendingToggleTarget === false) {
        return pendingToggleTarget;
    }
    if (PLUGIN_TOGGLE_ENABLED_STATUSES.has(normalizedState)) {
        return true;
    }
    return isEnabled === true;
}

export { resolveToggleChecked };
