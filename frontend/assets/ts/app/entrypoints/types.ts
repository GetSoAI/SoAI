/* SoAI - Frontend application contracts [frontend/assets/ts/app/entrypoints/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageHost } from '@core/pagehost/service.ts';
import type { PageInstance } from '@core/pagehost/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface AppLifecycleInstance {
    bootstrap: () => Promise<void>;
    renderInitializationError: (error: Error) => void;
}

interface DetachedContextData {
    pageId: string;
    windowId: string;
    parameters: JsonObject;
    host: PageHost | null;
    instance: PageInstance | null;
    stage: string;
}

interface DetachedParameters {
    pageId: string | null;
    parameters: JsonObject;
    windowId: string;
}

interface BackendReadyOptions {
    allowDiscovery?: boolean;
}

interface EntryModule {
    startPrimaryApp: () => void | Promise<void>;
    startDetachedWindow: () => void | Promise<void>;
}

export type { AppLifecycleInstance, BackendReadyOptions, DetachedContextData, DetachedParameters, EntryModule };
