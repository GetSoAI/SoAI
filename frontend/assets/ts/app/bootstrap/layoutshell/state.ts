/* SoAI - Frontend application layout shell state [frontend/assets/ts/app/bootstrap/layoutshell/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComponentDescriptor, LayoutShellState } from '@app/bootstrap/layoutshell/types.ts';
import { NOTIFICATIONS_CENTER_SERVICE_ID } from '@core/notifications/protocols.ts';
import { SEARCH_PANEL_SERVICE_ID } from '@core/search/protocols.ts';
import { TASK_MANAGER_SERVICE_ID } from '@core/tasks/protocols.ts';
import { LIVE_STATUS_OVERLAY_SERVICE_ID } from '@features/indicators/constants.ts';
import { RESTART_OVERLAY_SERVICE_ID } from '@features/overlays/public.ts';

const createLayoutShellState = (): LayoutShellState => {
    return {
        initialized: false,
        bootPromise: null,
        active: new Map()
    };
};

const createLayoutShellComponentSpec = (): ComponentDescriptor[] => {
    return [
        {
            key: 'mainStatusMonitor',
            identifier: null,
            registryNames: [],
            required: true
        },
        {
            key: 'header',
            identifier: 'core.layout.header',
            registryNames: ['core.layout.header'],
            registryOptions: { priority: 10 },
            required: true
        },
        {
            key: 'sidebar',
            identifier: 'core.layout.sidebar',
            registryNames: ['core.layout.sidebar'],
            registryOptions: { priority: 20 },
            required: true
        },
        {
            key: 'tasks',
            identifier: TASK_MANAGER_SERVICE_ID,
            registryNames: [TASK_MANAGER_SERVICE_ID],
            registryOptions: { priority: 30 },
            required: true
        },
        {
            key: 'notifications',
            identifier: NOTIFICATIONS_CENTER_SERVICE_ID,
            registryNames: [NOTIFICATIONS_CENTER_SERVICE_ID],
            registryOptions: { priority: 35 },
            required: true
        },
        {
            key: 'search',
            identifier: SEARCH_PANEL_SERVICE_ID,
            registryNames: [SEARCH_PANEL_SERVICE_ID],
            registryOptions: { priority: 40 },
            required: false
        },
        {
            key: 'liveStatusOverlay',
            identifier: LIVE_STATUS_OVERLAY_SERVICE_ID,
            registryNames: [LIVE_STATUS_OVERLAY_SERVICE_ID],
            registryOptions: { priority: 50 },
            required: false
        },
        {
            key: 'restartOverlay',
            identifier: RESTART_OVERLAY_SERVICE_ID,
            registryNames: [RESTART_OVERLAY_SERVICE_ID],
            registryOptions: { priority: 60 },
            required: false
        }
    ];
};

const findLayoutShellDescriptor = (spec: ComponentDescriptor[], key: string): ComponentDescriptor | null => {
    for (const descriptor of spec) {
        if (descriptor.key === key) {
            return descriptor;
        }
    }
    return null;
};

export { createLayoutShellComponentSpec, createLayoutShellState, findLayoutShellDescriptor };
