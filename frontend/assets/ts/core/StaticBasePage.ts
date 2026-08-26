/* SoAI - Shared frontend static base page [frontend/assets/ts/core/StaticBasePage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BasePage } from '@core/routing/pages/basepage/public.ts';
import { getTypeOf, isFunction } from '@core/typeGuards.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface RenderContext {
    parameters: JsonObject;
    state: JsonObject;
}

const ensureMarkup = (markup: TrustedHtml, owner: string): TrustedHtml => {
    if (!isTrustedHtml(markup)) {
        throw new Error(`${owner}: renderView() must resolve to TrustedHtml but received ${getTypeOf(markup)}`);
    }
    if (!markup.html.trim()) {
        throw new Error(`${owner}: renderView() produced empty markup`);
    }
    return markup;
};

abstract class StaticBasePage extends BasePage {
    #currentRenderContext: RenderContext | null = null;
    #afterRenderTask: (() => Promise<void>) | null = null;
    #renderSequence = 0;

    protected override async afterInitialization(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        if (context.signal?.aborted) {
            return;
        }
        await this.#executeAfterRender();
        if (context.signal?.aborted) {
            return;
        }
        await super.afterInitialization(parameters, context);
    }

    override async render(parameters: JsonObject = {}): Promise<TrustedHtml> {
        const sequence = ++this.#renderSequence;
        const preparation = await this.beforeRender(parameters);
        const renderContext: RenderContext = {
            parameters,
            state: preparation ?? {}
        };
        const markup = await this.renderView(renderContext);
        const html = ensureMarkup(markup, this.constructor.name);
        if (sequence !== this.#renderSequence) return html;
        this.#currentRenderContext = renderContext;
        this.#afterRenderTask = async (): Promise<void> => {
            await this.afterRender(renderContext);
        };
        return html;
    }

    async beforeRender(_parameters: JsonObject = {}): Promise<JsonObject> {
        return {};
    }

    abstract renderView(context: RenderContext): Promise<TrustedHtml>;

    async afterRender(_context: RenderContext): Promise<void> {}

    getRenderContext(): RenderContext | null {
        return this.#currentRenderContext;
    }

    async #executeAfterRender(): Promise<void> {
        const pending = this.#afterRenderTask;
        this.#afterRenderTask = null;
        if (isFunction(pending)) {
            await pending();
        }
    }
}

export { StaticBasePage };
export type { RenderContext };
