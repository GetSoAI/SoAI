/* SoAI - Models feature provider form submission [frontend/assets/ts/features/models/providerform/providerSubmission.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ExternalProviderCreateResponse } from '@core/api/contracts/pluginProviderContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortSignalScope } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { splitTrimmedList, toTrimmedString } from '@core/normalize.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

interface ProviderFormValues {
    pluginName: string;
    name: string;
    apiUrl: string;
    apiKey: string;
    modelsFilter: string;
}

interface ProviderCreatePayload {
    name: string;
    apiUrl: string;
    apiKey: string;
    modelsFilter?: string[];
}

type ProviderFormField = 'pluginName' | 'name' | 'apiUrl' | 'apiKey';

type ProviderFormValidation = { status: 'valid'; pluginName: string; payload: ProviderCreatePayload } | { status: 'invalid'; field: ProviderFormField; message: string };

interface ProviderFormPluginAccess {
    getPluginByName(name: string): PluginRecord | null;
    isProviderPluginOperational(plugin: PluginRecord): boolean;
}

interface ProviderSubmissionOptions {
    pluginName: string;
    payload: ProviderCreatePayload;
    signal: AbortSignal;
    addProvider(pluginName: string, payload: ProviderCreatePayload): Promise<ExternalProviderCreateResponse>;
    waitForModelCatalogChange(signal: AbortSignal): Promise<void>;
    onAccepted?(response: ExternalProviderCreateResponse): void;
}

type ProviderSubmissionOutcome = { status: 'created'; response: ExternalProviderCreateResponse } | { status: 'failed'; error: Error; accepted: boolean };

const validateProviderForm = (values: ProviderFormValues, plugins: ProviderFormPluginAccess): ProviderFormValidation => {
    const pluginName = toTrimmedString(values.pluginName);
    const name = toTrimmedString(values.name);
    const apiUrl = toTrimmedString(values.apiUrl);
    const apiKey = toTrimmedString(values.apiKey);
    const modelsFilter = toTrimmedString(values.modelsFilter);
    if (!pluginName) return { status: 'invalid', field: 'pluginName', message: i18n.t('models.notifications.selectPlugin') };
    if (!name) return { status: 'invalid', field: 'name', message: i18n.t('models.notifications.enterProviderName') };
    if (!apiUrl) return { status: 'invalid', field: 'apiUrl', message: i18n.t('models.notifications.enterApiUrl') };
    if (!apiKey) return { status: 'invalid', field: 'apiKey', message: i18n.t('models.notifications.enterApiKey') };
    const plugin = plugins.getPluginByName(pluginName);
    if (!plugin || !plugins.isProviderPluginOperational(plugin)) return { status: 'invalid', field: 'pluginName', message: i18n.t('models.notifications.pluginUnavailable') };
    const payload: ProviderCreatePayload = { name, apiUrl, apiKey };
    if (modelsFilter) payload.modelsFilter = splitTrimmedList(modelsFilter, ',');
    return { status: 'valid', pluginName, payload };
};

const submitProviderForm = async (options: ProviderSubmissionOptions): Promise<ProviderSubmissionOutcome> => {
    let accepted = false;
    const catalogAbort = new AbortController();
    const catalogScope = createAbortSignalScope([options.signal, catalogAbort.signal]);
    try {
        const catalogChange = options.waitForModelCatalogChange(catalogScope.signal).then(
            () => null,
            (error) => ensureError(error)
        );
        const response = await options.addProvider(options.pluginName, options.payload);
        accepted = true;
        options.onAccepted?.(response);
        const catalogError = await catalogChange;
        if (catalogError !== null) throw catalogError;
        return { status: 'created', response };
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ProviderSubmission', accepted ? 'Provider was created but post-accept processing failed' : 'Failed to create external provider', runtimeError);
        return { status: 'failed', error: runtimeError, accepted };
    } finally {
        catalogAbort.abort();
        catalogScope.cleanup();
    }
};

export { submitProviderForm, validateProviderForm };
export type { ProviderCreatePayload, ProviderFormField, ProviderFormPluginAccess, ProviderFormValidation, ProviderFormValues, ProviderSubmissionOutcome };
