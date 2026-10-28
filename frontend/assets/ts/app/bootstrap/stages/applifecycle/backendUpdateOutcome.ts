/* SoAI - Permission-gated backend advisories for software update outcomes [frontend/assets/ts/app/bootstrap/stages/applifecycle/backendUpdateOutcome.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canManagePluginBackends } from '@core/plugins/backendUpdateAccess.ts';
import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { summarizePluginBackendUpdates } from '@core/plugins/backendUpdateSummary.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { NoticeOptions, NoticeSection } from '@core/ui/modals/dialogs/types.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';

const SNAPSHOT_TIMEOUT_MS = 10000;

type BackendUpdateOutcome = Pick<NoticeOptions, 'sections' | 'action' | 'actionErrorText'> & { waitForReview?: () => Promise<boolean> };

const canManagePlugins = async (signal: AbortSignal): Promise<boolean> => {
    const permissions = await loadWebuiPermissionsSnapshot({ signal, timeoutMs: SNAPSHOT_TIMEOUT_MS });
    return canManagePluginBackends(permissions);
};

const readBackendUpdateOutcome = async (router: Pick<Router, 'navigate' | 'getCurrentRoute'>, signal: AbortSignal): Promise<BackendUpdateOutcome> => {
    try {
        if (!(await canManagePlugins(signal))) return {};
        const catalog = requireCatalogStore();
        const plugins = await withTimeout(raceWithAbortSignal(catalog.ensureLoaded(), signal), { timeoutMs: SNAPSHOT_TIMEOUT_MS, timeoutMessage: 'Plugin catalog snapshot is unavailable.' });
        if (!catalog.isFresh()) return {};
        const operations = requireTaskOperationsApi().getOperations({ types: ['backend-update'] });
        const names = new Set(operations.flatMap((operation) => (operation.pluginName ? [operation.pluginName] : [])));
        const summary = summarizePluginBackendUpdates(plugins, names);
        const failedUpdates = plugins.filter((plugin) => plugin.backendUpdate?.autoUpdateFailed && !summary.updating.includes(plugin));
        const available = summary.available.filter((plugin) => !failedUpdates.includes(plugin));
        const sections: NoticeSection[] = [];
        const groups = [
            { entries: available, heading: i18n.t('updates.backend.availableHeading'), versions: true },
            { entries: summary.updating, heading: i18n.t('updates.backend.updatingHeading'), versions: false },
            { entries: summary.pending.filter((plugin) => !failedUpdates.includes(plugin)), heading: i18n.t('updates.backend.pendingHeading'), versions: false },
            { entries: failedUpdates, heading: i18n.t('updates.backend.failedUpdatesHeading'), versions: false },
            { entries: summary.failed.filter((plugin) => !failedUpdates.includes(plugin)), heading: i18n.t('updates.backend.failedHeading'), versions: false }
        ];
        for (const { entries, heading, versions } of groups) {
            if (!entries.length) continue;
            sections.push({
                heading,
                items: entries.map((plugin) => {
                    const current = plugin.backendUpdate?.currentVersion;
                    const latest = plugin.backendUpdate?.latestVersion;
                    return {
                        label: plugin.displayName || plugin.name || i18n.t('common.unknown'),
                        detail: versions && current && latest ? `${current} → ${latest}` : ''
                    };
                })
            });
        }
        if (!sections.length) return {};
        let reviewCompletion = Promise.resolve(false);
        return {
            sections,
            waitForReview: () => reviewCompletion,
            actionErrorText: i18n.t('common.errors.operationFailed'),
            action: {
                text: available.length ? (available.length === 1 ? i18n.t('updates.backend.reviewUpdate') : i18n.t('updates.backend.reviewUpdates')) : i18n.t('updates.backend.viewPlugins'),
                variantClassName: 'ui-variant-primary',
                disabled: false,
                title: null,
                deferredBusy: true,
                perform: async (): Promise<boolean> => {
                    const completion = createDeferred<boolean>();
                    reviewCompletion = completion.promise;
                    let reviewed = false;
                    try {
                        if (signal.aborted) return false;
                        if (!(await canManagePlugins(signal))) throw new Error('Plugin management is no longer authorized.');
                        if (signal.aborted) return false;
                        await router.navigate('plugins');
                        if (router.getCurrentRoute() !== 'plugins') throw new Error('Plugin navigation did not complete.');
                        reviewed = true;
                        return true;
                    } catch (error) {
                        if (isAbortError(error)) return false;
                        throw ensureError(error);
                    } finally {
                        completion.resolve(reviewed);
                    }
                }
            }
        };
    } catch (error) {
        if (!isAbortError(error)) errorHandler.debug('AppLifecycle', 'Backend update outcome snapshot is unavailable', ensureError(error));
        return {};
    }
};

export { readBackendUpdateOutcome };
