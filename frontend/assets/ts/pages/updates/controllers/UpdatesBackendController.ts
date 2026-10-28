/* SoAI - Updates page backend catalog subscription [frontend/assets/ts/pages/updates/controllers/UpdatesBackendController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { canManagePluginBackends } from '@core/plugins/backendUpdateAccess.ts';
import { summarizePluginBackendUpdates } from '@core/plugins/backendUpdateSummary.ts';
import { getStreamConnection } from '@core/realtime/streammanager/public.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import { buildBackendUpdatesMarkup } from '@pages/updates/controllers/UpdatesSystemMarkupBuilder.ts';

interface UpdatesBackendDependencies {
    catalog: CatalogStore;
    pageDom: PageDom;
    pageResources: PageResources;
    pageElements: PageUi;
}

const SNAPSHOT_TIMEOUT_MS = 10000;

class UpdatesBackendController {
    readonly #dependencies: UpdatesBackendDependencies;
    readonly #abort = new AbortController();
    readonly #disposers: Array<() => void> = [];
    readonly #permissionsToken = new SequenceToken();
    #canManage = false;
    #renderPending = false;
    #markup: string | null = null;

    constructor(dependencies: UpdatesBackendDependencies) {
        this.#dependencies = dependencies;
    }

    async initialize(): Promise<void> {
        this.#disposers.push(this.#dependencies.catalog.subscribe(this.#scheduleRender, { emitInitial: false }));
        this.#disposers.push(requireTaskOperationsApi().subscribeOperations({ types: ['backend-update'] }, this.#scheduleRender));
        this.#disposers.push(getStreamConnection().subscribeConnected(this.#refreshPermissions));
        await this.#refreshPermissions();
    }

    #refreshPermissions = async (): Promise<void> => {
        const token = this.#permissionsToken.next();
        this.#canManage = false;
        this.#scheduleRender();
        try {
            const permissions = await loadWebuiPermissionsSnapshot({ signal: this.#abort.signal, timeoutMs: SNAPSHOT_TIMEOUT_MS });
            if (this.#abort.signal.aborted || !this.#permissionsToken.isActive(token)) return;
            this.#canManage = canManagePluginBackends(permissions);
            if (this.#canManage) await withTimeout(raceWithAbortSignal(this.#dependencies.catalog.ensureLoaded(), this.#abort.signal), { timeoutMs: SNAPSHOT_TIMEOUT_MS, timeoutMessage: 'Plugin catalog is unavailable.' });
        } catch (error) {
            if (!this.#permissionsToken.isActive(token)) return;
            this.#canManage = false;
            if (!isAbortError(error)) errorHandler.debug('UpdatesBackend', 'Backend update summary is unavailable', ensureError(error));
        }
        if (!this.#permissionsToken.isActive(token)) return;
        this.#scheduleRender();
    };

    #scheduleRender = (): void => {
        if (this.#abort.signal.aborted || this.#renderPending) return;
        this.#renderPending = true;
        this.#dependencies.pageResources.tracker.requestAnimationFrame(() => {
            this.#renderPending = false;
            if (this.#abort.signal.aborted) return;
            const { catalog, pageDom, pageElements } = this.#dependencies;
            const target = pageDom.requireHTMLElement('#backendUpdates');
            const operations = requireTaskOperationsApi().getOperations({ types: ['backend-update'] });
            const names = new Set(operations.flatMap((operation) => (operation.pluginName ? [operation.pluginName] : [])));
            const plugins = this.#canManage && catalog.isFresh() ? summarizePluginBackendUpdates(catalog.getPlugins(), names).available : [];
            const markup = buildBackendUpdatesMarkup(plugins);
            if (markup.html !== this.#markup) {
                pageDom.updateHtml(target, markup, { escape: false });
                this.#markup = markup.html;
            }
            pageElements.toggleHidden(target, plugins.length === 0);
        });
    };

    destroy(): void {
        this.#permissionsToken.invalidate();
        this.#abort.abort();
        for (const dispose of this.#disposers.splice(0)) dispose();
    }
}

export { UpdatesBackendController };
