/* SoAI - Shared UI primitives view service [frontend/assets/ts/core/uiprimitives/view/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { isArray, isNullOrUndefined, isObject, isPlainObject, isString, hasOwn } from '@core/typeGuards.ts';

import { escapeAttribute, safeStr } from '@core/uiprimitives/adapters.ts';
import { combineClasses, cloneAttributes, renderAria, renderAttributes, renderDataset } from '@core/uiprimitives/dom.ts';
import { normalizeCollectionNodeType, renderCollectionCard, renderCollectionHeading, renderCollectionParagraph } from '@core/uiprimitives/view/mappers.ts';
import { composeCollectionButtonContent } from '@core/uiprimitives/view/effects.ts';
import type { BuildConfig, BuildResult, ButtonConfig, CardConfig, ClassValue, EmptyStateConfig, EscapableValue, GridConfig, IconConfig, IconOptions, LayoutNodeValue, MarkupContent, NodeConfig, PageInstance } from '@core/uiprimitives/types.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';

const renderMarkupContent = (content: MarkupContent): string => (isTrustedHtml(content) ? content.html : content);

const isGridConfigNode = (node: LayoutNodeValue): node is GridConfig => isObject(node) && normalizeCollectionNodeType(node) === 'grid';

const isEmptyStateConfigNode = (node: LayoutNodeValue): node is EmptyStateConfig => isObject(node) && normalizeCollectionNodeType(node) === 'emptyState';

const isButtonConfigNode = (node: LayoutNodeValue): node is ButtonConfig => isObject(node) && normalizeCollectionNodeType(node) === 'button';

const isCardConfigNode = (node: LayoutNodeValue): node is CardConfig => isObject(node) && normalizeCollectionNodeType(node) === 'card';

const isNodeConfigNode = (node: LayoutNodeValue): node is NodeConfig => isObject(node);

class CollectionLayoutBuilder {
    page: PageInstance;
    escapeHtml: (value: string) => string;
    iconResolver: (name: string, options?: IconOptions) => TrustedHtml;

    constructor(page: PageInstance, escapeHtmlFunctionValue: (value: string) => string, iconResolverFunctionValue: (name: string, options?: IconOptions) => TrustedHtml) {
        if (!page) throw new Error('CollectionLayoutBuilder requires a page instance');
        this.page = page;
        this.escapeHtml = escapeHtmlFunctionValue;
        this.iconResolver = iconResolverFunctionValue;
    }

    combineClasses(...values: ClassValue[]): string {
        return combineClasses(...values);
    }

    build(config: BuildConfig = {}): BuildResult {
        return {
            header: config.header ?? {},
            content: Array.isArray(config.sections) ? config.sections.map((section) => this.resolveNode(section)).join('') : '',
            filters: config.filters ?? null,
            actions: Array.isArray(config.actions) ? config.actions : [],
            delegated: Array.isArray(config.delegated) ? config.delegated : []
        };
    }

    resolveNode(node: LayoutNodeValue): string {
        if (!node) return '';
        if (isString(node)) return node;
        if (isTrustedHtml(node)) return node.html;
        if (typeof node === 'function') return this.resolveNode(node(this));
        if (Array.isArray(node)) return node.map((item) => this.resolveNode(item)).join('');
        if (!isObject(node)) {
            throw new Error('Collection layout node must be an object');
        }
        const methodName = normalizeCollectionNodeType(node);
        switch (methodName) {
            case 'fragment':
                if (!isNodeConfigNode(node)) throw new Error('Collection fragment node must be an object');
                return this.fragment(node);
            case 'grid':
                if (!isGridConfigNode(node)) throw new Error('Collection grid node must be an object');
                return this.grid(node);
            case 'emptyState':
                if (!isEmptyStateConfigNode(node)) throw new Error('Collection empty state node must be an object');
                return this.emptyState(node);
            case 'button':
                if (!isButtonConfigNode(node)) throw new Error('Collection button node must be an object');
                return this.button(node);
            case 'card':
                if (!isCardConfigNode(node)) throw new Error('Collection card node must be an object');
                return this.card(node);
            case 'section':
            default:
                if (!isNodeConfigNode(node)) throw new Error('Collection section node must be an object');
                return this.section(node);
        }
    }

    fragment(config: NodeConfig = {}): string {
        return this.resolveNode(config.children);
    }

    section(config: NodeConfig = {}): string {
        const tag = config.tag || 'div';
        const idAttr = config.id ? ` id="${this.escapeAttributeValue(config.id)}"` : '';
        const classes = combineClasses(config.className, config.hidden === true ? CSS_CLASSES.HIDDEN : '', config.sizeClass, config.id);
        const classAttr = classes ? ` class="${this.escapeAttributeValue(classes)}"` : '';
        const roleAttr = config.role ? ` role="${this.escapeAttributeValue(config.role)}"` : '';
        return `<${tag}${idAttr}${classAttr}${roleAttr}${renderAria(config.aria, this.escapeAttributeValue)}${renderDataset(config.dataset, this.escapeAttributeValue)}${renderAttributes(config.attributes, this.escapeAttributeValue)}>${this.resolveNode(config.children)}</${tag}>`;
    }

    grid(config: GridConfig = {}): string {
        const children: string[] = [
            this.section({
                tag: config.tag || 'div',
                id: config.id,
                className: config.className || 'ui-collection-grid',
                role: config.role || 'list',
                aria: config.aria,
                dataset: config.dataset,
                attributes: config.attributes
            })
        ];
        if (isArray(config.emptyStates)) config.emptyStates.forEach((state) => children.push(this.emptyState(state)));
        return this.section({
            tag: 'div',
            id: config.wrapperId,
            className: config.wrapperClass || 'collection-grid-wrapper',
            hidden: config.hidden,
            children
        });
    }

    emptyState(config: EmptyStateConfig = {}): string {
        const containerClasses = combineClasses(config.className, config.hidden !== false ? CSS_CLASSES.HIDDEN : '', config.id);
        const containerAttr = (containerClasses ? ` class="${this.escapeAttributeValue(containerClasses)}"` : '') + (config.id ? ` id="${this.escapeAttributeValue(config.id)}"` : '') + renderAttributes(config.attributes, this.escapeAttributeValue);
        const icon = config.icon ? `<div class="ui-empty-state__icon">${this.resolveIcon(config.icon)}</div>` : '';
        const actions = isArray(config.actions) ? config.actions.map((action) => this.button(action)).join('') : '';
        const body = config.body ? renderMarkupContent(config.body) : '';
        return `<div${containerAttr}><div class="${this.escapeAttributeValue(config.contentClass || 'ui-empty-state')}">${icon}${renderCollectionHeading(config.title, config.titleId, 'h3', this.escapeHtml, this.escapeAttributeValue)}${renderCollectionParagraph(config.description, config.descriptionId, this.escapeHtml, this.escapeAttributeValue)}${body}${actions ? `<div class="ui-empty-state__actions">${actions}</div>` : ''}</div></div>`;
    }

    button(config: ButtonConfig | string | null | undefined = {}): string {
        if (!config) return '';
        if (isString(config)) return config;
        if (config.html) return renderMarkupContent(config.html);
        const tag = config.tag === 'a' ? 'a' : 'button';
        const cls = combineClasses(config.className, config.id);
        const attrs: Record<string, string | boolean | number | undefined> = {
            ...(config.id ? { id: config.id } : {}),
            ...(config.href ? { href: config.href } : {}),
            ...(config.target ? { target: config.target } : {}),
            ...(config.rel ? { rel: config.rel } : {}),
            ...(config.type && tag === 'button' ? { type: config.type } : {}),
            ...(config.disabled ? { disabled: true } : {}),
            ...cloneAttributes(config.attributes)
        };
        if (config.aria) Object.entries(config.aria).forEach(([key, value]) => (attrs[`aria-${key}`] = value));
        if (config.dataset) Object.entries(config.dataset).forEach(([key, value]) => (attrs[`data-${key}`] = value));
        if (!hasOwn(attrs, 'aria-label') && config.label) attrs['aria-label'] = config.label;

        if (hasOwn(attrs, 'title')) {
            throw new Error('Native title attribute is forbidden. Use data-tooltip instead.');
        }

        const tooltipText = typeof attrs['aria-label'] === 'string' && String(attrs['aria-label']).trim() ? String(attrs['aria-label']) : '';
        if (!hasOwn(attrs, 'data-tooltip') && tooltipText) {
            attrs['data-tooltip'] = tooltipText;
        }
        const content = !isNullOrUndefined(config.content) ? renderMarkupContent(config.content) : this.composeButtonContent(config);
        return `<${tag}${cls ? ` class="${this.escapeAttributeValue(cls)}"` : ''}${renderAttributes(attrs, this.escapeAttributeValue)}>${content}</${tag}>`;
    }

    composeButtonContent(config: ButtonConfig = {}): string {
        return composeCollectionButtonContent(config, (icon): string => this.resolveIcon(icon), this.escapeHtml);
    }

    card(config: CardConfig = {}): string {
        return renderCollectionCard(config, {
            button: (buttonConfig: ButtonConfig | string | null | undefined): string => this.button(buttonConfig),
            resolveRuntimeNode: (node: LayoutNodeValue): string => this.#resolve(node),
            section: (sectionConfig: NodeConfig): string => this.section(sectionConfig)
        });
    }

    escapeAttributeValue(value: EscapableValue): string {
        return escapeAttribute(safeStr(value));
    }

    resolveIcon(icon: string | IconConfig | undefined): string {
        if (!icon) return '';
        if (isString(icon)) return this.iconResolver(icon, {}).html;
        return isPlainObject(icon) && icon.name ? this.iconResolver(icon.name, isPlainObject(icon.options) ? icon.options : {}).html : '';
    }

    #resolve(node: LayoutNodeValue): string {
        if (!node) return '';
        if (Array.isArray(node)) return node.map((item) => this.#resolve(item)).join('');
        if (isString(node)) return node;
        if (isTrustedHtml(node)) return node.html;
        if (typeof node === 'function') return this.#resolve(node(this));
        return this.resolveNode(node);
    }
}

export { CollectionLayoutBuilder };
