/* SoAI - Prompts page state [frontend/assets/ts/pages/prompts/controllers/page/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import { normalizeResourceItem } from '@core/data/clientdatahub/guards.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { StoreItemRecord } from '@core/CollectionsStore.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { buildPromptDownloadText, normalizePromptRecord, type PromptRecord } from '@features/prompts/public.ts';
import type { ColorToolkitInterface } from '@pages/prompts/contracts/contracts.ts';
import { formatRelativeTime } from '@pages/prompts/mappers/mappers.ts';
import { PromptDataAdapter } from '@pages/prompts/services/service.ts';
import type { PromptsRuntimeOperations, PromptsRuntimeOwners } from '@pages/prompts/controllers/page/contracts.ts';
import type { PromptsPageSession } from '@pages/prompts/controllers/page/PromptsPageSession.ts';

interface PromptsPageStateHost {
    state: Pick<PromptsPageSession, 'dataAdapter' | 'dataAdapterReadyTask' | 'groupResolvers'>;
    owners: Pick<PromptsRuntimeOwners, 'collections'>;
    components: { colorToolkit: ColorToolkitInterface };
    operations: Pick<PromptsRuntimeOperations, 'upsertItem' | 'findPromptById'>;
}

const normalizeCollectionPromptId = (prompt: ResourceIncomingValue | StoreItemRecord | null | undefined): string | null => {
    if (!isPlainObject(prompt)) {
        return null;
    }
    const id = prompt['id'];
    if (typeof id === 'string' && id.trim()) {
        return id;
    }
    if (typeof id === 'number' && Number.isFinite(id)) {
        return String(id);
    }
    const name = prompt['name'];
    return typeof name === 'string' && name.trim() ? name : null;
};

const toPromptResourceItem = (prompt: PromptRecord): ResourceItem => ({
    id: prompt.id,
    name: prompt.name,
    content: prompt.content,
    color: prompt.color,
    createdAtMs: prompt.createdAtMs,
    modifiedAtMs: prompt.modifiedAtMs
});

const normalizeCollectionPrompt = (value: ResourceIncomingValue | null | undefined): ResourceItem => {
    const jsonValue = value === null || value === undefined ? null : toJsonCompatibleValue(value);
    if (!isPlainObject(jsonValue)) {
        throw new TypeError('Prompts collection stream returned a non-object item');
    }
    return normalizeResourceItem(toPromptResourceItem(normalizePromptRecord(jsonValue)), 'Prompts collection item');
};

const ensureDataAdapter = (host: PromptsPageStateHost): PromptDataAdapter => {
    if (!host.state.dataAdapter) {
        const adapter = new PromptDataAdapter({ colorToolkit: host.components.colorToolkit });
        host.state.dataAdapter = adapter;
        host.state.groupResolvers = adapter.getGroupResolvers();
    }
    return host.state.dataAdapter;
};

const ensureDataAdapterReady = async (host: PromptsPageStateHost): Promise<PromptDataAdapter> => {
    if (!host.state.dataAdapterReadyTask) {
        host.state.dataAdapterReadyTask = (async () => ensureDataAdapter(host))();
    }
    return host.state.dataAdapterReadyTask;
};

const buildPromptDownloadEntry = (prompt: PromptRecord): string => buildPromptDownloadText(prompt);

const buildSelectionDownloadFilename = (host: PromptsPageStateHost): string => ensureDataAdapter(host).buildSelectionDownloadFilename();

const formatDate = (timestamp: number): string => formatRelativeTime(timestamp);

const upsertPromptRecord = (host: PromptsPageStateHost, record: PromptRecord | null): PromptRecord | null => {
    if (!record || !host.owners.collections.runtime) {
        return null;
    }
    const normalized = normalizePromptRecord(record);
    host.operations.upsertItem(normalized);
    return host.operations.findPromptById(normalized.id) ?? normalized;
};

export { buildPromptDownloadEntry, buildSelectionDownloadFilename, ensureDataAdapter, ensureDataAdapterReady, formatDate, normalizeCollectionPrompt, normalizeCollectionPromptId, toPromptResourceItem, upsertPromptRecord };
export type { PromptsPageStateHost };
