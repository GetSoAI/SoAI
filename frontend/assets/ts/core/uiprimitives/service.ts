/* SoAI - Shared UI primitives service [frontend/assets/ts/core/uiprimitives/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { safeStr } from '@core/uiprimitives/adapters.ts';
import { combineClasses } from '@core/uiprimitives/dom.ts';
import { CollectionLayoutBuilder } from '@core/uiprimitives/view/service.ts';
import type { ButtonConfig, CardConfig, EscapableValue, GridConfig, IconConfig, IconOptions, LayoutNodeValue, NodeConfig, PageInstance } from '@core/uiprimitives/types.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';

interface FactoryInput {
    escapeHtml: (value: string) => string;
    escapeAttribute: (value: string) => string;
    iconResolver: (name: string, options?: IconOptions) => TrustedHtml;
}

class CollectionCardFactory {
    builder: CollectionLayoutBuilder;

    constructor(page: PageInstance, escapeHtmlFunctionValue: (value: string) => string, iconResolverFunctionValue: (name: string, options?: IconOptions) => TrustedHtml) {
        if (!page) throw new Error('CollectionCardFactory requires a page instance');
        this.builder = new CollectionLayoutBuilder(page, escapeHtmlFunctionValue, iconResolverFunctionValue);
    }

    card(config: CardConfig = {}): string {
        const children: string[] = [];
        if (Array.isArray(config.actions) && config.actions.length > 0) {
            children.push(
                this.builder.section({
                    tag: 'div',
                    className: config.actionsWrapperClass || 'ui-collection-card__action-bar',
                    children: config.actions.map((action) => (isString(action) ? action : this.builder.button(action))).join('')
                })
            );
        }
        const content = this.#resolve(config.children ?? config.sections ?? config.content ?? '');
        if (content) children.push(content);
        if (config.statusLine)
            children.push(
                this.builder.section({
                    tag: config.statusLine.tag || 'div',
                    className: combineClasses('ui-collection-card__status-line', config.statusLine.className),
                    dataset: config.statusLine.dataset,
                    attributes: config.statusLine.attributes,
                    aria: config.statusLine.aria
                })
            );
        return this.builder.section({
            tag: config.tag || 'div',
            id: config.id,
            aria: config.aria,
            dataset: config.dataset,
            attributes: config.attributes,
            className: combineClasses(config.includeCollectionRoot === false ? '' : 'ui-collection-card', config.className),
            children: children.join('')
        });
    }

    section(config: NodeConfig = {}): string {
        return this.builder.section(config);
    }

    fragment(config: NodeConfig | string = {}): string {
        return isString(config) ? config : this.builder.fragment(config);
    }

    button(config: ButtonConfig = {}): string {
        return this.builder.button(config);
    }

    grid(config: GridConfig = {}): string {
        return this.builder.grid(config);
    }

    icon(name: string | IconConfig, options: IconOptions = {}): string {
        return isString(name) ? this.builder.resolveIcon({ name, options }) : this.builder.resolveIcon(name);
    }

    escapeHtml(value: EscapableValue): string {
        return this.builder.escapeHtml(safeStr(value));
    }

    escapeAttribute(value: EscapableValue): string {
        return this.builder.escapeAttributeValue(safeStr(value));
    }

    getBuilder(): CollectionLayoutBuilder {
        return this.builder;
    }

    #resolve(node: LayoutNodeValue): string {
        if (!node) return '';
        if (Array.isArray(node)) return node.map((item) => this.#resolve(item)).join('');
        if (isString(node)) return node;
        if (isTrustedHtml(node)) return node.html;
        if (typeof node === 'function') return this.#resolve(node(this.builder));
        return this.builder.resolveNode(node);
    }
}

const createCollectionLayoutFactory = ({
    escapeHtml: escapeHtmlFunctionValue,
    escapeAttribute: _escapeAttributeFunctionValue,
    iconResolver: iconResolverFunctionValue
}: FactoryInput): {
    createBuilder: (page: PageInstance) => CollectionLayoutBuilder;
    cards: { createFactory: (page: PageInstance) => CollectionCardFactory };
} => {
    void _escapeAttributeFunctionValue;
    return Object.freeze({
        createBuilder(page: PageInstance): CollectionLayoutBuilder {
            return new CollectionLayoutBuilder(page, escapeHtmlFunctionValue, iconResolverFunctionValue);
        },
        cards: Object.freeze({
            createFactory(page: PageInstance): CollectionCardFactory {
                return new CollectionCardFactory(page, escapeHtmlFunctionValue, iconResolverFunctionValue);
            }
        })
    });
};

export { CollectionCardFactory, createCollectionLayoutFactory };
