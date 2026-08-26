/* SoAI - Frontend stream manager runtime access [frontend/assets/ts/core/realtime/streammanager/streamManagerAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamManager } from '@core/realtime/streammanager/StreamManager.ts';
import { requireStreamManager } from '@core/realtime/streammanager/runtime.ts';
import type { StreamResourceLoader } from '@core/realtime/streammanager/resourceLoader.ts';
import type { StreamSubscriptions } from '@core/realtime/streammanager/streamSubscriptions.ts';
import type { StreamTaskRuntime } from '@core/realtime/streammanager/actions/service.ts';
import type { StreamTransport } from '@core/realtime/streammanager/streamTransport.ts';

interface StreamRuntimeOwners {
    resources: StreamResourceLoader;
    subscriptions: StreamSubscriptions;
    tasks: StreamTaskRuntime;
    connection: StreamTransport;
}

const getStreamManager = (): StreamManager => {
    return requireStreamManager();
};

const getStreamRuntime = (): StreamRuntimeOwners => requireStreamManager();
const getStreamResources = (): StreamResourceLoader => requireStreamManager().resources;
const getStreamSubscriptions = (): StreamSubscriptions => requireStreamManager().subscriptions;
const getStreamTasks = (): StreamTaskRuntime => requireStreamManager().tasks;
const getStreamConnection = (): StreamTransport => requireStreamManager().connection;

export { getStreamConnection, getStreamManager, getStreamResources, getStreamRuntime, getStreamSubscriptions, getStreamTasks };
export type { StreamRuntimeOwners };
