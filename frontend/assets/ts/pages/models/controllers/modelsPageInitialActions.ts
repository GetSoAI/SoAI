/* SoAI - Models page initial actions [frontend/assets/ts/pages/models/controllers/modelsPageInitialActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL, MODELS_ACTION_MANAGE_PROVIDERS, MODELS_ACTION_MANAGE_VIRTUAL_MODELS } from '@core/models/pageActions.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

type InitialActionContext = { action: string; plugin?: string; vm?: string };
type InitialActionParameters = JsonObject;
type InitialActionExecutor = (host: ModelsInitialActionHost, parameters?: InitialActionParameters) => void | Promise<void>;

interface ModelsInitialActionHost {
    getInitialActionContext: () => InitialActionContext | null;
    setInitialActionContext: (context: InitialActionContext | null) => void;
    router: { getCurrentRoute: () => string | null; getRouteParameters: () => Record<string, string> };
    replaceHashRoute: (route: string) => void;
    log: (level: 'debug' | 'info' | 'warn' | 'error', message: string, error?: Error) => void;
    openDownloadModelModal: () => void;
    openProvidersModal: () => void | Promise<void>;
    openVirtualModelsModal: () => void;
    showEditVirtualModelForm: (vmName?: string | null) => void | Promise<void>;
}

const INITIAL_PLUGIN_ACTIONS: ReadonlySet<string> = new Set([MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL, MODELS_ACTION_MANAGE_PROVIDERS]);
const INITIAL_ACTION_EXECUTORS: Readonly<Record<string, InitialActionExecutor>> = Object.freeze({
    [MODELS_ACTION_ADD_PROVIDER]: (host) => {
        host.openDownloadModelModal();
    },
    [MODELS_ACTION_DOWNLOAD_MODEL]: (host) => {
        host.openDownloadModelModal();
    },
    [MODELS_ACTION_MANAGE_PROVIDERS]: async (host) => {
        await host.openProvidersModal();
    },
    [MODELS_ACTION_MANAGE_VIRTUAL_MODELS]: async (host, parameters) => {
        host.openVirtualModelsModal();
        const vmId = toTrimmedString(parameters ? parameters['vm'] : null);
        if (vmId) {
            await host.showEditVirtualModelForm(vmId);
        }
    }
});

const setModelsInitialActionContext = (host: ModelsInitialActionHost, context: InitialActionContext | null): void => {
    if (!context) {
        host.setInitialActionContext(null);
        return;
    }
    const initialActionContext = context;
    const action = toTrimmedString(initialActionContext['action']);
    if (!action) {
        host.setInitialActionContext(null);
        return;
    }
    const plugin = toTrimmedString(initialActionContext['plugin']);
    const vm = toTrimmedString(initialActionContext['vm']);
    host.setInitialActionContext({ action, ...(plugin ? { plugin } : {}), ...(vm ? { vm } : {}) });
};

const clearInitialActionQuery = (host: ModelsInitialActionHost, keys: string[] = ['action', 'plugin', 'vm']): void => {
    const currentRoute = host.router.getCurrentRoute();
    if (!currentRoute) {
        throw new Error('Models initial action cleanup requires a current route');
    }

    const parameters = host.router.getRouteParameters();
    const exclude = new Set(keys);
    const filtered = new URLSearchParams();
    let modified = false;

    for (const [key, value] of Object.entries(parameters)) {
        if (exclude.has(key)) {
            modified = true;
            continue;
        }
        filtered.append(key, value);
    }

    if (modified) {
        const nextQuery = filtered.toString();
        const nextRoute = currentRoute.split('?')[0] + (nextQuery ? `?${nextQuery}` : '');
        host.replaceHashRoute(nextRoute);
    }
};

const handleModelsInitialAction = async (host: ModelsInitialActionHost, parameters: JsonObject | null): Promise<void> => {
    const parametersObject = parameters;
    const action = toTrimmedString(parametersObject ? parametersObject['action'] : null);
    if (!action) {
        setModelsInitialActionContext(host, null);
        return;
    }

    if (INITIAL_PLUGIN_ACTIONS.has(action)) {
        setModelsInitialActionContext(host, {
            action,
            plugin: toTrimmedString(parametersObject ? parametersObject['plugin'] : null)
        });
    } else {
        setModelsInitialActionContext(host, null);
    }

    const handler = INITIAL_ACTION_EXECUTORS[action];
    if (!handler) {
        setModelsInitialActionContext(host, null);
        return;
    }

    const actionParameters: InitialActionParameters | undefined = parametersObject ? parametersObject : undefined;
    try {
        await handler(host, actionParameters);
        clearInitialActionQuery(host);
    } catch (error) {
        const runtimeError = ensureError(error);
        host.log('warn', 'Models initial action failed', runtimeError);
    }
};

export { clearInitialActionQuery, handleModelsInitialAction, setModelsInitialActionContext };
export type { InitialActionContext, ModelsInitialActionHost };
