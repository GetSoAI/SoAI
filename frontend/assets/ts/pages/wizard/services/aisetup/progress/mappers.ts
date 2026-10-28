/* SoAI - Wizard AI setup progress item derivation [frontend/assets/ts/pages/wizard/services/aisetup/progress/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelDownloadOutcome } from '@features/models/public.ts';
import type { OperationProgressData } from '@core/operationprogress/types.ts';
import type { AiSetupBackend, AiSetupModel, AiSetupState, AiSetupTestOutcome } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { findItemModel, readConfigurationFingerprint, readModelLabel } from '@pages/wizard/services/aisetup/catalog/mappers.ts';
import { isEngineInstalled, readEngineName, type AiSetupFacts } from '@pages/wizard/services/aisetup/facts/service.ts';
import { findModelCatalogEntry } from '@pages/wizard/services/aisetup/catalog/constants.ts';

type TaskObservation = { status: 'cancelling'; taskId: string | null } | { status: 'cancelled' } | { status: 'checking'; taskId: string | null } | { status: 'running'; taskId: string | null; progress: OperationProgressData | null } | { status: 'succeeded' } | { status: 'failed'; insufficientDiskSpace: boolean };

type ReadinessPhase = 'configuring' | 'testing';

type AiSetupRowPhase = 'checking' | 'installing' | 'installed' | 'waiting' | 'blocked' | 'starting' | 'downloading' | 'discovering' | 'cancelling' | 'cancelled' | 'configuring' | 'testing' | 'ready' | 'stale' | 'failed';

type AiSetupRowFailure = 'install_failed' | 'download_failed' | 'no_disk_space' | 'discovery_failed' | Exclude<AiSetupTestOutcome, 'passed'>;

type AiSetupRowAction = 'repair_runtime' | 'retry' | 'retry_installation' | 'skip' | 'test_again' | 'send_test';

interface AiSetupRow {
    key: string;
    kind: 'backend' | 'model';
    itemId: string | null;
    source: AiSetupModel['source'] | null;
    pluginName: string;
    label: string;
    engineLabel: string;
    phase: AiSetupRowPhase;
    failure: AiSetupRowFailure | null;
    failureMetadata?: AiSetupModel['test']['failure'];
    progress: OperationProgressData | null;
    actions: AiSetupRowAction[];
    ready: boolean;
}

interface AiSetupRowInputs {
    setup: AiSetupState;
    facts: AiSetupFacts | null;
    models: readonly ModelData[];
    observations: ReadonlyMap<string, TaskObservation>;
    readiness: ReadonlyMap<string, ReadinessPhase>;
    stalledDiscovery: ReadonlySet<string>;
}

interface AiSetupProgressSummary {
    rows: AiSetupRow[];
    readyCount: number;
    modelCount: number;
}

type AiSetupRowIdentity = Pick<AiSetupRow, 'key' | 'kind' | 'itemId' | 'source' | 'pluginName' | 'label' | 'engineLabel'>;

type EngineState = 'ready' | 'installing' | 'checking' | 'failed' | 'missing';

const BACKEND_ROW_PREFIX = 'backend:';

const backendRowKey = (pluginName: string): string => `${BACKEND_ROW_PREFIX}${pluginName}`;

const readBackendRowPlugin = (rowKey: string): string | null => (rowKey.startsWith(BACKEND_ROW_PREFIX) ? rowKey.slice(BACKEND_ROW_PREFIX.length) : null);

const activeBackend = (setup: AiSetupState, pluginName: string): AiSetupBackend | null => setup.engine.backends.find((backend) => backend.pluginName === pluginName && !backend.excluded) ?? null;

const resolveEngineState = (inputs: Pick<AiSetupRowInputs, 'setup' | 'facts' | 'observations'>, pluginName: string): EngineState => {
    if (inputs.facts !== null && isEngineInstalled(inputs.facts, pluginName)) return 'ready';
    const observation = inputs.observations.get(backendRowKey(pluginName));
    if (observation?.status === 'succeeded') return 'ready';
    if (observation?.status === 'running') return 'installing';
    if (observation?.status === 'failed' || observation?.status === 'cancelled') return 'failed';
    if (observation?.status === 'checking') return 'checking';
    return activeBackend(inputs.setup, pluginName) === null ? 'missing' : 'checking';
};

const createRow = (fields: AiSetupRowIdentity, phase: AiSetupRowPhase, extra: Partial<Pick<AiSetupRow, 'failure' | 'failureMetadata' | 'progress' | 'actions'>> = {}): AiSetupRow => ({
    ...fields,
    phase,
    failure: extra.failure ?? null,
    failureMetadata: extra.failureMetadata ?? null,
    progress: extra.progress ?? null,
    actions: extra.actions ?? [],
    ready: phase === 'ready'
});

const deriveBackendRow = (inputs: AiSetupRowInputs, backend: AiSetupBackend): AiSetupRow | null => {
    const key = backendRowKey(backend.pluginName);
    const observation = inputs.observations.get(key);
    const label = readEngineName(inputs.facts, backend.pluginName);
    const fields: AiSetupRowIdentity = { key, kind: 'backend', itemId: null, source: null, pluginName: backend.pluginName, label, engineLabel: label };
    if (observation === undefined && backend.taskId === null && inputs.facts !== null && isEngineInstalled(inputs.facts, backend.pluginName)) return null;
    if (observation?.status === 'cancelling' || observation?.status === 'cancelled') return createRow(fields, observation.status, { actions: observation.status === 'cancelled' ? ['retry_installation', 'skip'] : [] });
    if (observation?.status === 'running') return createRow(fields, 'installing', { progress: observation.progress });
    if (observation?.status === 'failed') return createRow(fields, 'failed', { failure: 'install_failed', actions: ['retry_installation', 'skip'] });
    if (resolveEngineState(inputs, backend.pluginName) === 'ready') return createRow(fields, 'installed');
    return createRow(fields, 'checking');
};

const readItemLabel = (item: AiSetupModel, model: ModelData | null): string => findModelCatalogEntry(item.catalogId)?.name ?? readModelLabel(model, item.artifactName ?? item.artifactReference ?? item.modelId ?? item.itemId);

const deriveTestedRow = (inputs: AiSetupRowInputs, item: AiSetupModel, model: ModelData, fields: AiSetupRowIdentity): AiSetupRow => {
    const runtimePhase = inputs.readiness.get(item.itemId);
    if (runtimePhase !== undefined) return createRow(fields, runtimePhase);
    if (item.test.status === 'failed' && item.test.outcome !== null && item.test.outcome !== 'passed') return createRow(fields, 'failed', { failure: item.test.outcome, failureMetadata: item.test.failure, actions: item.test.failure?.code === 'openvino_tensor_shape_incompatible' ? ['repair_runtime', 'retry', 'skip'] : ['retry', 'skip'] });
    if (item.source === 'cloud') return createRow(fields, 'ready', { actions: item.test.status === 'not_run' ? ['send_test'] : [] });
    if (item.test.status === 'passed' || item.test.status === 'stale') {
        const fingerprint = readConfigurationFingerprint(model);
        const current = item.test.status === 'passed' && (fingerprint === null || fingerprint === item.test.configurationFingerprint);
        return current ? createRow(fields, 'ready') : createRow(fields, 'stale', { actions: ['test_again', 'skip'] });
    }
    return createRow(fields, item.test.configurationFingerprint === null ? 'configuring' : 'testing');
};

const deriveUndiscoveredRow = (inputs: AiSetupRowInputs, item: AiSetupModel, fields: AiSetupRowIdentity): AiSetupRow => {
    if (inputs.stalledDiscovery.has(item.itemId)) return createRow(fields, 'failed', { failure: 'discovery_failed', actions: ['skip'] });
    if (item.source === 'cloud') return createRow(fields, 'discovering', {});
    const observation = inputs.observations.get(item.itemId);
    if (observation?.status === 'cancelling' || observation?.status === 'cancelled') return createRow(fields, observation.status, { actions: observation.status === 'cancelled' ? ['retry', 'skip'] : [] });
    if (observation?.status === 'running') return createRow(fields, 'downloading', { progress: observation.progress });
    if (observation?.status === 'failed') return createRow(fields, 'failed', { failure: observation.insufficientDiskSpace ? 'no_disk_space' : 'download_failed', actions: ['retry', 'skip'] });
    if (observation?.status === 'succeeded' || item.modelId !== null) return createRow(fields, 'discovering', {});
    if (observation?.status === 'checking' || item.downloadTaskId !== null) return createRow(fields, 'checking');
    const engine = resolveEngineState(inputs, item.pluginName);
    if (engine === 'ready') return createRow(fields, 'starting');
    if (engine === 'installing' || engine === 'checking') return createRow(fields, 'waiting');
    return createRow(fields, 'blocked', { actions: ['retry_installation', 'skip'] });
};

const deriveModelRow = (inputs: AiSetupRowInputs, item: AiSetupModel): AiSetupRow => {
    const model = findItemModel(inputs.models, item);
    const fields: AiSetupRowIdentity = { key: item.itemId, kind: 'model', itemId: item.itemId, source: item.source, pluginName: item.pluginName, label: readItemLabel(item, model), engineLabel: readEngineName(inputs.facts, item.pluginName) };
    return model === null ? deriveUndiscoveredRow(inputs, item, fields) : deriveTestedRow(inputs, item, model, fields);
};

const deriveAiSetupProgress = (inputs: AiSetupRowInputs): AiSetupProgressSummary => {
    const backendRows = inputs.setup.engine.backends.filter((backend) => !backend.excluded).flatMap((backend) => deriveBackendRow(inputs, backend) ?? []);
    const models = inputs.setup.models.filter((item) => !item.excluded);
    const modelRows = [...models.filter((item) => item.source === 'cloud'), ...models.filter((item) => item.source === 'local')].map((item) => deriveModelRow(inputs, item));
    const readyCount = modelRows.filter((row) => row.ready).length;
    return {
        rows: [...backendRows, ...modelRows],
        readyCount,
        modelCount: modelRows.length
    };
};

const isRowReady = (summary: AiSetupProgressSummary, itemId: string): boolean => summary.rows.some((row) => row.itemId === itemId && row.ready);

export { backendRowKey, deriveAiSetupProgress, isRowReady, readBackendRowPlugin, resolveEngineState };
export type { AiSetupProgressSummary, AiSetupRow, AiSetupRowAction, AiSetupRowFailure, AiSetupRowInputs, AiSetupRowPhase, EngineState, ReadinessPhase, TaskObservation };

type SettledTaskResult = 'cancelled' | 'succeeded' | 'failed' | 'failed_disk' | 'detached';

const readDownloadResult = (outcome: Exclude<ModelDownloadOutcome, { status: 'rejected' }>): SettledTaskResult => {
    if (outcome.status === 'finished') return 'succeeded';
    if (outcome.status === 'detached') return 'detached';
    if (outcome.status === 'cancelled') return 'cancelled';
    return outcome.status === 'failed' && outcome.insufficientDiskSpace ? 'failed_disk' : 'failed';
};

export { readDownloadResult };
export type { SettledTaskResult };

const isLocalDownloadComplete = (setup: AiSetupState, observations: ReadonlyMap<string, TaskObservation>): boolean => setup.models.some((item) => item.source === 'local' && !item.excluded && (item.modelId !== null || observations.get(item.itemId)?.status === 'succeeded'));

export { isLocalDownloadComplete };
