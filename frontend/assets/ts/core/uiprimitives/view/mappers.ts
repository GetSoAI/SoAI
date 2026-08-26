/* SoAI - Shared UI primitives mappers [frontend/assets/ts/core/uiprimitives/view/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNullOrUndefined, isObject, isPlainObject, isString } from '@core/typeGuards.ts';
import { combineClasses } from '@core/uiprimitives/dom.ts';
import type { ButtonConfig, CardConfig, LayoutNodeValue, NodeConfig, ParagraphConfig } from '@core/uiprimitives/types.ts';

interface CollectionCardRenderDependencies {
    button: (config: ButtonConfig | string | null | undefined) => string;
    resolveRuntimeNode: (node: LayoutNodeValue) => string;
    section: (config: NodeConfig) => string;
}

const normalizeCollectionNodeType = <T>(node: T): string | null => {
    if (!isObject(node)) {
        return null;
    }
    if (!('type' in node)) return null;
    const rawType = node['type'];
    if (typeof rawType !== 'string' || rawType.length === 0) return null;
    const key = rawType;
    if (!key.includes('-')) return key;
    return key
        .split('-')
        .map((part: string, index: number) => (index === 0 ? part : part.charAt(0).toUpperCase() + part.slice(1)))
        .join('');
};

const renderCollectionHeading = (content: string | undefined, id: string | undefined, tag: string, escapeHtml: (value: string) => string, escapeAttributeValue: (value: string) => string): string => {
    if (!content) return '';
    return `<${tag}${id ? ` id="${escapeAttributeValue(id)}"` : ''}>${escapeHtml(String(content))}</${tag}>`;
};

const renderCollectionParagraph = (content: string | ParagraphConfig | undefined, id: string | undefined, escapeHtml: (value: string) => string, escapeAttributeValue: (value: string) => string): string => {
    if (!content) return '';
    if (isPlainObject(content)) {
        const config = content;
        const idValue = config['id'];
        const resolvedId = isString(idValue) && idValue ? idValue : '';
        const rawValue = config['raw'];
        const rawText = config['text'];
        const raw = rawValue === true;
        const text = raw ? (isNullOrUndefined(rawText) ? '' : String(rawText)) : escapeHtml(String(rawText ?? ''));
        return `<p${resolvedId ? ` id="${escapeAttributeValue(resolvedId)}"` : ''}>${text}</p>`;
    }
    return `<p${id ? ` id="${escapeAttributeValue(id)}"` : ''}>${escapeHtml(String(content))}</p>`;
};

const renderCollectionCard = (config: CardConfig, dependencies: CollectionCardRenderDependencies): string => {
    const children: string[] = [];
    if (isArray(config.actions) && config.actions.length > 0) {
        children.push(
            dependencies.section({
                tag: 'div',
                className: config.actionsWrapperClass || 'ui-collection-card__action-bar',
                children: config.actions.map((action) => (isString(action) ? action : dependencies.button(action))).join('')
            })
        );
    }
    const content = dependencies.resolveRuntimeNode(config.children ?? config.sections ?? config.content ?? '');
    if (content) children.push(content);
    if (config.statusLine)
        children.push(
            dependencies.section({
                tag: config.statusLine.tag || 'div',
                className: combineClasses('ui-collection-card__status-line', config.statusLine.className),
                dataset: config.statusLine.dataset,
                attributes: config.statusLine.attributes,
                aria: config.statusLine.aria
            })
        );
    return dependencies.section({
        tag: config.tag || 'div',
        id: config.id,
        aria: config.aria,
        dataset: config.dataset,
        attributes: config.attributes,
        className: combineClasses(config.includeCollectionRoot === false ? '' : 'ui-collection-card', config.className),
        children: children.join('')
    });
};

export { normalizeCollectionNodeType, renderCollectionCard, renderCollectionHeading, renderCollectionParagraph };
