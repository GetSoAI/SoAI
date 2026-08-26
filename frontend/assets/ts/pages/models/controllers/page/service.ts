/* SoAI - Models page service [frontend/assets/ts/pages/models/controllers/page/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { disposeManagedModalLifecycles } from '@core/modals/managedModalLifecycle.ts';
import { METRICS } from '@core/realtime/streammanager/resources/ids.ts';
import { unwrap } from '@core/realtime/streammanager/resources/normalizers.ts';
import { executeStreamItemDeletion } from '@core/routing/pages/collections/streamItemDeletion.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ModelsItemDeletionConfig, ModelsItemDeletionHost } from '@pages/models/controllers/page/types.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';

interface ModelsMetricsSubscriptionHost extends PageStreamingOwnerHost, PageResourcesOwnerHost {
    collections: PageCollections;
    currentMetrics: JsonObject | null;
    metricsPresentationSignature: string | null;
    metricsPatchController: { queue(): void };
}

const resolveModelsMetricsPresentationSignature = (snapshot: JsonObject): string => {
    const root = isJsonObject(snapshot['metrics']) ? snapshot['metrics'] : snapshot;
    const director = isJsonObject(root['director']) ? root['director'] : null;
    const billing = isJsonObject(root['billing']) ? root['billing'] : null;
    return stableJsonStringify({
        requestsByModel: director?.['requestsByModel'] ?? null,
        requestsByVirtualModel: director?.['requestsByVirtualModel'] ?? null,
        tokensByModel: billing?.['tokensByModel'] ?? null
    });
};

interface ModelsPageDestroyRuntime {
    downloadModalManager: { disposeForPageDestroy(): void };
    editModelModalManager: { disposeForPageDestroy(): void };
    renameModelModalManager: { disposeForPageDestroy(): void };
    providersManager: { disposeForPageDestroy(): void };
    virtualModelsManager: { disposeForPageDestroy(): void };
    catalogSubscriptions: { cleanup(): void };
    pluginLookup: { clear(): void };
    grouping: { clear(): void };
    deletingItems: Set<string>;
    cardController: { dispose(): void };
}

const executeModelsItemDeletion = async (host: ModelsItemDeletionHost, config: ModelsItemDeletionConfig): Promise<void> => {
    const { identifier, confirmTitle, confirmMessage, confirmButton, getStream, gridId, findCard, pendingClass, successMessage } = config;
    const resolveCard = (grid: HTMLElement | null, id: string): HTMLElement | null => {
        if (typeof findCard === 'function') {
            return findCard(grid, id);
        }
        return null;
    };
    await executeStreamItemDeletion(
        {
            deletingItems: host.deletingItems,
            streams: host.streams,
            optionalUI: (selector, context) => host.pageDom.optional(selector, context),
            addClassName: (element, className) => host.pageDom.addClass(element, className),
            removeClassName: (element, className) => host.pageDom.removeClass(element, className),
            showNotification: (message, type) => host.feedback.show(message, type),
            handleError: (error, title, options) => host.feedback.handle(error, title, options),
            renderItems: () => host.renderItems(),
            removeItemById: (id) => host.removeItemById(id)
        },
        {
            identifier,
            confirmTitle,
            confirmMessage,
            confirmButton,
            cancelButton: host.cancelLabel,
            getStream,
            gridSelector: gridId,
            findCard: resolveCard,
            pendingClass,
            successMessage
        }
    );
};

const readModelsMetricsSnapshot = (host: ModelsMetricsSubscriptionHost): JsonObject => {
    const streamResources = host.streaming.runtime().resources;
    const resource = streamResources.getResource(METRICS);
    const rawSnapshot = isJsonObject(resource) && 'value' in resource ? resource['value'] : resource;
    const snapshot = unwrap(isJsonValue(rawSnapshot) ? rawSnapshot : null);
    if (!isJsonObject(snapshot)) {
        throw new Error('Models page metrics snapshot requires an object payload');
    }
    return snapshot;
};

const syncModelsMetricsSnapshot = (host: ModelsMetricsSubscriptionHost): void => {
    const snapshot = readModelsMetricsSnapshot(host);
    host.currentMetrics = snapshot;
    host.metricsPresentationSignature = resolveModelsMetricsPresentationSignature(snapshot);
};

const applyModelsMetricsPayload = (host: ModelsMetricsSubscriptionHost, payload: JsonValue): void => {
    const snapshot = unwrap(payload);
    if (!isJsonObject(snapshot)) {
        throw new Error('Models page metrics subscription requires an object payload');
    }
    const signature = resolveModelsMetricsPresentationSignature(snapshot);
    const presentationChanged = signature !== host.metricsPresentationSignature;
    host.currentMetrics = snapshot;
    host.metricsPresentationSignature = signature;
    if (presentationChanged && host.collections.runtime) {
        host.metricsPatchController.queue();
    }
};

const setupModelsMetricsSubscription = (host: ModelsMetricsSubscriptionHost): void => {
    host.pageResources.track(
        host.streaming.subscribeResourceValue(METRICS, (payload: JsonValue): void => {
            applyModelsMetricsPayload(host, payload);
        })
    );
};

const destroyModelsPageFromRuntime = async (runtime: ModelsPageDestroyRuntime): Promise<void> => {
    const failures: Error[] = [];
    runCleanupStepCollectingFailure(() => {
        disposeManagedModalLifecycles([runtime.downloadModalManager, runtime.editModelModalManager, runtime.renameModelModalManager, runtime.providersManager, runtime.virtualModelsManager]);
    }, failures);
    runCleanupStepCollectingFailure(() => runtime.catalogSubscriptions.cleanup(), failures);
    runtime.pluginLookup.clear();
    runtime.grouping.clear();
    runtime.deletingItems.clear();
    runCleanupStepCollectingFailure(() => runtime.cardController.dispose(), failures);
    throwCollectedCleanupFailures(failures);
};

const createModelsItemDeletionHost = (host: Omit<ModelsItemDeletionHost, 'cancelLabel'>): ModelsItemDeletionHost => ({ ...host, cancelLabel: i18n.t('common.cancel') });

export { createModelsItemDeletionHost, destroyModelsPageFromRuntime, executeModelsItemDeletion, setupModelsMetricsSubscription, syncModelsMetricsSnapshot };
