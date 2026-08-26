/* SoAI - Model detail page route implementation [frontend/assets/ts/pages/modeldetail/ModelDetailPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { MODELS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { ModelDetailPageDomain } from '@pages/modeldetail/controllers/page/ModelDetailPageDomain.ts';
import { renderModelDetailPageView } from '@pages/modeldetail/view.ts';

export const PAGE_ID = 'modelDetail';

class ModelDetailPage extends StaticBasePage {
    readonly #domain: ModelDetailPageDomain;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#domain = new ModelDetailPageDomain({
            api: this.dependencies.api,
            collapsibleCards: this.collapsibleCards,
            dom: this.dependencies.dom,
            feedback: this.feedback,
            layout: this.layout,
            modalPresenter: requireModalPresenter(),
            pageContext: this.pageContext,
            pageDom: this.pageDom,
            pageElements: this.pageElements,
            pageLifecycle: this.pageLifecycle,
            pageResources: this.pageResources,
            router: this.dependencies.router,
            services: this.services,
            statusManager: this.dependencies.stateManager.status,
            storage: this.dependencies.storage,
            streaming: this.streaming
        });
    }

    override getRequiredResources(): string[] {
        return [MODELS, PLUGINS];
    }

    override async renderView(context: RenderContext): Promise<TrustedHtml> {
        this.#domain.setModelIdFromParameters(context.parameters);
        return renderModelDetailPageView({ generateStandardHeader: (options) => this.layout.generateHeader(options) });
    }

    override async beforePageInitialize(parameters: JsonObject = {}, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.beforePageInitialize(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#domain.resetBeforeInitialization(parameters);
    }

    override async setupPage(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.setupPage(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#domain.setup();
    }

    override async loadData(): Promise<void> {
        await this.#domain.loadData();
    }

    bindPageEvents(): void {
        this.#domain.bindPageEvents();
    }

    override async onDestroy(): Promise<void> {
        this.#domain.destroy();
    }
}

export { ModelDetailPage };
