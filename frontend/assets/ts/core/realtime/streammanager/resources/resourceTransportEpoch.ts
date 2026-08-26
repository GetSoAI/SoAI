/* SoAI - Resource transport epoch ownership [frontend/assets/ts/core/realtime/streammanager/resources/resourceTransportEpoch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceEntry } from '@core/realtime/streammanager/types.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';
import { isWebSocketUpdatedResource } from '@core/websocketEvents.ts';

const applyResourceTransportEvent = (resources: Iterable<ResourceEntry>, context: WebSocketDispatchContext, ownsEvent: () => boolean): boolean => {
    for (const resource of resources) {
        if (!ownsEvent()) return false;
        if (!resource.config.websocketOnly && !isWebSocketUpdatedResource(resource.name)) continue;
        if (resource.reconciler.snapshot.transportEpoch < context.connectionEpoch) resource.reconciler.replaceTransportEpoch(context.connectionEpoch);
        if (!ownsEvent()) return false;
    }
    return ownsEvent();
};

export { applyResourceTransportEvent };
