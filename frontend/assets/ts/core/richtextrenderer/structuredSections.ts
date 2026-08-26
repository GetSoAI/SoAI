/* SoAI - Shared rich text renderer structured sections [frontend/assets/ts/core/richtextrenderer/structuredSections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { isArray, isFunction, isObject } from '@core/typeGuards.ts';

type StructuredTextProvider = () => string;

interface StructuredTextListItemObject {
    getText: StructuredTextProvider;
    children?: readonly StructuredTextProvider[] | undefined;
}

type StructuredTextListItem = StructuredTextProvider | StructuredTextListItemObject;

interface StructuredTextParagraphBlock {
    type: 'paragraph';
    getText: StructuredTextProvider;
}

interface StructuredTextHeadingBlock {
    type: 'heading';
    getText: StructuredTextProvider;
    level: string | number;
}

interface StructuredTextListBlock {
    type: 'list';
    ordered?: boolean;
    items: readonly StructuredTextListItem[];
}

type StructuredTextBlock = StructuredTextParagraphBlock | StructuredTextHeadingBlock | StructuredTextListBlock;

interface StructuredTextSection {
    id: string;
    getTitle: StructuredTextProvider;
    getHeading: StructuredTextProvider;
    blocks: readonly StructuredTextBlock[];
}

interface StructuredTextSectionRenderOptions {
    idPrefix: string;
    sectionClassName: string;
    titleClassName: string;
}

const isStructuredTextListItemObject = (value: StructuredTextListItem): value is StructuredTextListItemObject => {
    return isObject(value) && isFunction(value['getText']);
};

const clampHeadingLevel = (candidate: string | number): number => {
    const parsed = Number.parseInt(String(candidate), 10);
    if (!Number.isFinite(parsed)) {
        return 3;
    }
    return clampNumber(parsed, 1, 6);
};

const renderStructuredTextList = (block: StructuredTextListBlock): string => {
    if (!isArray(block.items) || block.items.length === 0) {
        return '';
    }
    const renderItem = (item: StructuredTextListItem): string => {
        if (isFunction(item)) {
            return `<li>${item()}</li>`;
        }
        if (!isStructuredTextListItemObject(item)) {
            throw new Error('Structured text list item object requires getText()');
        }
        const children = isArray(item.children) && item.children.length > 0 ? `<ul>${item.children.map((child) => `<li>${child()}</li>`).join('')}</ul>` : '';
        return `<li>${item.getText()}${children}</li>`;
    };
    const elementName = block.ordered === true ? 'ol' : 'ul';
    return `<${elementName}>${block.items.map((item) => renderItem(item)).join('')}</${elementName}>`;
};

const renderStructuredTextBlock = (block: StructuredTextBlock): string => {
    if (block.type === 'paragraph') {
        return `<p>${block.getText()}</p>`;
    }
    if (block.type === 'heading') {
        const level = clampHeadingLevel(block.level);
        return `<h${level}>${block.getText()}</h${level}>`;
    }
    if (block.type === 'list') {
        return renderStructuredTextList(block);
    }
    const exhaustive: never = block;
    throw new Error(`Unsupported structured text block type: ${String(exhaustive)}`);
};

const renderStructuredTextSection = (section: StructuredTextSection, options: StructuredTextSectionRenderOptions): TrustedHtml => {
    const id = `${options.idPrefix}${section.id}`;
    return toTrustedUiHtml(
        `
        <div class="${uiAttr(options.sectionClassName).html}" id="${uiAttr(id).html}">
            <div class="${uiAttr(options.titleClassName).html}">${section.getTitle()}</div>
            <h2>${section.getHeading()}</h2>
            ${section.blocks.map((block) => renderStructuredTextBlock(block)).join('')}
        </div>
    `.trim()
    );
};

const renderStructuredTextSections = (sections: readonly StructuredTextSection[], options: StructuredTextSectionRenderOptions): TrustedHtml => {
    return toTrustedUiHtml(sections.map((section) => renderStructuredTextSection(section, options).html).join(''));
};

export { renderStructuredTextSection, renderStructuredTextSections };
export type { StructuredTextBlock, StructuredTextHeadingBlock, StructuredTextListBlock, StructuredTextListItem, StructuredTextListItemObject, StructuredTextParagraphBlock, StructuredTextProvider, StructuredTextSection, StructuredTextSectionRenderOptions };
