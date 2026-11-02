/* SoAI - Models page initial actions [frontend/assets/ts/pages/models/controllers/modelsPageInitialActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageRouting } from '@core/routing/router/types.ts';
import { consumeRouteQuery, MODELS_INITIAL_ACTION_QUERY_KEYS } from '@core/routeregistry/reconstruction.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL, MODELS_ACTION_MANAGE_PROVIDERS, MODELS_ACTION_MANAGE_VIRTUAL_MODELS } from '@core/models/pageActions.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

type InitialActionContext = { action: string; plugin?: string; vm?: string; search?: string };
type InitialActionParameters = JsonObject;
type InitialActionExecutor = (host: ModelsInitialActionHost, parameters?: InitialActionParameters) => void | Promise<void>;

interface ModelsInitialActionHost {
    getInitialActionContext: () => InitialActionContext | null;
    setInitialActionContext: (context: InitialActionContext | null) => void;
    router: Pick<PageRouting, 'getCurrentRoute' | 'getQueryParameters' | 'replaceCurrentRoute'>;
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
    const search = toTrimmedString(initialActionContext['search']);
    host.setInitialActionContext({ action, ...(plugin ? { plugin } : {}), ...(vm ? { vm } : {}), ...(search ? { search } : {}) });
};

const clearInitialActionQuery = (host: ModelsInitialActionHost, keys: readonly string[] = MODELS_INITIAL_ACTION_QUERY_KEYS): void => {
    consumeRouteQuery(host.router, keys);
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
            plugin: toTrimmedString(parametersObject ? parametersObject['plugin'] : null),
            search: toTrimmedString(parametersObject ? parametersObject['search'] : null)
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
        if (isAbortError(runtimeError)) return;
        host.log('warn', 'Models initial action failed', runtimeError);
    }
};

export { clearInitialActionQuery, handleModelsInitialAction, setModelsInitialActionContext };
export type { InitialActionContext, ModelsInitialActionHost };
