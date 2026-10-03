/* SoAI - Wizard AI setup cloud provider connection [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupCloudConnectionSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getApiClient } from '@core/api/service.ts';
import { runWithAbortSignalScope } from '@core/errors/abort.ts';
import { extractUserFacingErrorMessage, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';
import { resolvePluginUnavailableReason, submitProviderForm, validateProviderForm, waitForModelCatalogChange, type ProviderFormField, type ProviderFormValues } from '@features/models/public.ts';
import { withProvider } from '@pages/wizard/services/aisetup/state.ts';

const PROVIDER_DISCOVERY_WAIT_MS = 30_000;
const GENERIC_PROVIDER_PLUGIN_NAME = 'external';
const USER_CORRECTABLE_STATUSES: readonly number[] = [400, 422];

type ProviderDraft = Omit<ProviderFormValues, 'apiKey'>;

interface CloudConnectionState {
    connecting: boolean;
    connectingName: string;
    editing: boolean;
    error: { field: ProviderFormField | null; message: string } | null;
    draft: ProviderDraft;
}

interface AiSetupCloudConnectionSessionHost {
    updateSetup(update: (setup: AiSetupState) => AiSetupState): void;
    refreshModels(): Promise<void>;
    onChange(): void;
}

interface ProviderPluginAvailability {
    operational: PluginRecord[];
    unavailableReason: string | null;
}

const readProviderPluginAvailability = (): ProviderPluginAvailability => {
    const store = requireCatalogStore();
    const capable = store.getProviderCapable();
    const operational = capable.filter((plugin) => store.isProviderPluginOperational(plugin)).sort((left, right) => Number(right.name === GENERIC_PROVIDER_PLUGIN_NAME) - Number(left.name === GENERIC_PROVIDER_PLUGIN_NAME));
    return { operational, unavailableReason: operational.length > 0 ? null : resolvePluginUnavailableReason(capable[0] ?? null, 'provider') };
};

const readProviderFailureMessage = (error: Error): string => {
    const correctable = USER_CORRECTABLE_STATUSES.some((status) => isErrorHttpStatus(error, status));
    return (correctable ? extractUserFacingErrorMessage(error) : null) ?? i18n.t('models.notifications.providerCreateFailed');
};

class AiSetupCloudConnectionSession {
    readonly #host: AiSetupCloudConnectionSessionHost;
    readonly #abortController = new AbortController();
    readonly #timers = new ResourceTracker();
    readonly state: CloudConnectionState = { connecting: false, connectingName: '', editing: false, error: null, draft: { pluginName: '', name: '', apiUrl: '', modelsFilter: '' } };

    constructor(host: AiSetupCloudConnectionSessionHost) {
        this.#host = host;
    }

    dispose(): void {
        this.#abortController.abort();
        this.#timers.cleanup();
    }

    rememberDraft(draft: ProviderDraft): void {
        this.state.draft = { pluginName: draft.pluginName, name: draft.name, apiUrl: draft.apiUrl, modelsFilter: draft.modelsFilter };
    }

    edit(): void {
        this.state.editing = true;
        this.state.error = null;
        this.#host.onChange();
    }

    async connect(values: ProviderFormValues): Promise<boolean> {
        if (this.state.connecting) return false;
        this.rememberDraft(values);
        const store = requireCatalogStore();
        const validation = validateProviderForm(values, { getPluginByName: (name) => store.getPlugin(name), isProviderPluginOperational: (plugin) => store.isProviderPluginOperational(plugin) });
        if (validation.status === 'invalid') {
            this.state.error = { field: validation.field, message: validation.message };
            this.#host.onChange();
            return false;
        }
        this.state.connecting = true;
        this.state.connectingName = validation.payload.name;
        this.state.error = null;
        this.#host.onChange();
        const outcome = await submitProviderForm({
            pluginName: validation.pluginName,
            payload: validation.payload,
            signal: this.#abortController.signal,
            addProvider: (pluginName, payload) => getApiClient().plugins.providers.add(pluginName, payload),
            waitForModelCatalogChange: (signal) => this.#waitForDiscovery(signal),
            onAccepted: ({ provider }) => this.#host.updateSetup((setup) => withProvider(setup, { providerId: provider.id, providerName: provider.name ?? validation.payload.name, pluginName: validation.pluginName }))
        });
        if (this.#abortController.signal.aborted) return false;
        this.state.connecting = false;
        if (outcome.status === 'failed' && !outcome.accepted) {
            this.state.error = { field: null, message: readProviderFailureMessage(outcome.error) };
            this.#host.onChange();
            return false;
        }
        this.state.editing = false;
        await this.#host.refreshModels();
        this.#host.onChange();
        return true;
    }

    #waitForDiscovery(signal: AbortSignal): Promise<void> {
        const deadline = new AbortController();
        const timerId = this.#timers.setTimeout(() => deadline.abort(), PROVIDER_DISCOVERY_WAIT_MS);
        return runWithAbortSignalScope([signal, deadline.signal], (scoped) => waitForModelCatalogChange(scoped)).finally(() => this.#timers.clearTimer(timerId));
    }
}

export { AiSetupCloudConnectionSession, readProviderPluginAvailability };
export type { CloudConnectionState, ProviderDraft, ProviderPluginAvailability };
