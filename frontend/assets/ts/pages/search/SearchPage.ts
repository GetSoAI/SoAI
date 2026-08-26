/* SoAI - Search routed page [frontend/assets/ts/pages/search/SearchPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { bindTypedResolvedDataActionListener } from '@core/dom/dataActionBinding.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { SEARCH_ACTION_CLEAR_RECENT, SEARCH_ACTION_OPEN_ITEM, SEARCH_ACTION_SELECT_RECENT, isSearchActionId } from '@pages/search/actions.ts';
import { isSearchComponent, type SearchPageDependencies } from '@pages/search/contracts/contracts.ts';
import { resolveSearchQueryFromParameters } from '@pages/search/controllers/page/events.ts';
import { SearchPageRuntime } from '@pages/search/controllers/page/service.ts';
import { renderSearchPageView } from '@pages/search/view.ts';

export const PAGE_ID = 'search';
export const PAGE_MODULE_ID = 'pages.SearchPage';

class SearchPage extends StaticBasePage {
    readonly #runtime: SearchPageRuntime;

    constructor({ searchComponent }: SearchPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        if (!isSearchComponent(searchComponent)) throw new Error('SearchPage requires a valid search component dependency');
        this.#runtime = new SearchPageRuntime(searchComponent, {
            api: this.dependencies.api,
            stateManager: this.dependencies.stateManager,
            pageContext: this.pageContext,
            pageDom: this.pageDom,
            feedback: this.feedback,
            services: this.services,
            pageElements: this.pageElements,
            layout: this.layout,
            storage: this.dependencies.storage,
            router: this.dependencies.router
        });
        this.layout.configure({ onTabChange: (tab) => this.#runtime.onTabChange(tab) });
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return renderSearchPageView({ generateStandardHeader: (options) => this.layout.generateHeader(options) });
    }

    override async initializeShell(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#runtime.initializeShell(
            resolveSearchQueryFromParameters(parameters, (value) => value?.trim() ?? ''),
            context.signal ?? null
        );
    }

    bindPageEvents(): void {
        bindTypedResolvedDataActionListener({
            root: this.resolveHostContainer(),
            signal: this.pageLifecycle.beginListeners(),
            eventType: 'click',
            isAction: isSearchActionId,
            mouseButton: 'primary',
            preventDefault: 'always',
            onAction: ({ action, actionElement }): void => {
                if (action === SEARCH_ACTION_CLEAR_RECENT) {
                    this.#runtime.service.clearRecentSearches();
                    return;
                }
                if (action === SEARCH_ACTION_SELECT_RECENT) {
                    this.#runtime.service.handleRecentSearchSelection(actionElement);
                    return;
                }
                if (action === SEARCH_ACTION_OPEN_ITEM) this.#runtime.service.handleSearchItemClick(actionElement);
            }
        });
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#runtime.destroy();
    }
}

export { SearchPage };
