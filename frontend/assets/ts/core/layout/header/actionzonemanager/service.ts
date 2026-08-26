/* SoAI - Shared frontend layout header action zone manager service [frontend/assets/ts/core/layout/header/actionzonemanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getHeaderActions } from '@core/headeractions/public.ts';
import { isFunction } from '@core/typeGuards.ts';
import { destroyActionEntries, reorderVisibleActions, syncActionEntries, updateActionZoneEmptyState, validateActionZoneManagerDependencies } from '@core/layout/header/actionzonemanager/effects.ts';
import { bindActionZoneSpaceUpdates, queueActionZoneSpaceUpdate } from '@core/layout/header/actionzonemanager/space.ts';
import { normalizeActionArray } from '@core/layout/header/actionzonemanager/mappers.ts';
import type { Action, ActionZoneManagerHost, ActionZoneManagerOptions, ActionZoneManagerState } from '@core/layout/header/actionzonemanager/types.ts';

class ActionZoneManager {
    header: ActionZoneManagerHost;
    hiddenClass: string;
    state: ActionZoneManagerState;

    constructor({ header, hiddenClass }: ActionZoneManagerOptions) {
        validateActionZoneManagerDependencies(header, hiddenClass);
        this.header = header;
        this.hiddenClass = hiddenClass;
        this.state = {
            container: null,
            subscription: null,
            layoutCleanup: null,
            layoutFrameId: null,
            actions: new Map()
        };
    }

    async initialize(): Promise<void> {
        this.state.container = this.header.getDom('actionZone');
        if (!this.state.container) {
            throw new Error('Action zone container is unavailable');
        }

        this.state.subscription = getHeaderActions().subscribe((snapshot) => {
            this.sync(normalizeActionArray(snapshot.actions));
        });
        bindActionZoneSpaceUpdates(this.state, this.header);
        updateActionZoneEmptyState(this.state, this.header, this.hiddenClass, []);
    }

    destroy(): void {
        if (isFunction(this.state.subscription)) {
            this.state.subscription();
        }
        this.state.subscription = null;
        destroyActionEntries(this.state);
        this.state.container = null;
    }

    sync(actions: Action[]): void {
        if (!this.state.container) {
            return;
        }

        const visibleActions = syncActionEntries(this.state, this.header, actions);
        reorderVisibleActions(this.state, visibleActions);
        updateActionZoneEmptyState(this.state, this.header, this.hiddenClass, visibleActions);
        queueActionZoneSpaceUpdate(this.state, this.header);
    }

    localize(): void {
        if (!this.state.container) {
            return;
        }

        const snapshot = getHeaderActions().snapshot;
        this.sync(normalizeActionArray(snapshot.actions));
    }
}

export { ActionZoneManager };
export type { ActionZoneManagerHost };
