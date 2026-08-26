/* SoAI - Shared routing collection view builders [frontend/assets/ts/core/routing/pages/collections/collectionViewBuilders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import type { HeaderActionDefinition, HeaderStatDefinition, IconDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { AttributeProps, ButtonConfig, LayoutNodeValue, MarkupContent } from '@core/uiprimitives/types.ts';

interface CardGridHeaderOptions {
    title: string;
    description?: string;
    actions?: HeaderActionDefinition[];
    stats?: HeaderStatDefinition[];
    containerClass?: string;
    floating?: boolean;
}

interface CardGridHeader {
    title: string;
    description?: string;
    floating: boolean;
    actions: HeaderActionDefinition[];
    stats: HeaderStatDefinition[];
    contentLayout: 'card-grid';
    containerClass?: string;
}

interface CollectionSectionOptions {
    id: string;
    className: string;
    role?: string;
    tag?: string;
}

interface CollectionSection {
    type: string;
    tag: string;
    id: string;
    className: string;
    role: string;
    children?: LayoutNodeValue;
}

type EmptyStateIcon = IconDefinition;

interface EmptyStateOptions {
    id: string;
    className: string;
    title: string;
    description?: string;
    icon?: EmptyStateIcon;
    body?: MarkupContent;
    actions?: ButtonConfig[];
}

interface EmptyState {
    type: string;
    id: string;
    className: string;
    hidden: boolean;
    title: string;
    description?: string;
    icon?: EmptyStateIcon;
    body?: MarkupContent;
    actions?: ButtonConfig[];
}

interface CollectionSectionsOptions {
    gridId: string;
    gridClassName: string;
    emptyStates?: EmptyState[];
}

interface ModalButton {
    className: string;
    id?: string;
    attributes?: AttributeProps;
    disabled?: boolean;
    content: string;
}

interface FooterSection {
    align: string;
    className?: string;
    buttons: ModalButton[];
}

interface SplitModalFooter {
    layout: string;
    sections: FooterSection[];
}

interface SplitModalFooterOptions {
    closeId?: string | undefined;
    closeLabel: string;
    closeAttributes?: AttributeProps | undefined;
    closeClassName?: string | undefined;
    rightButtons: ModalButton[];
    rightSectionClassName?: string | undefined;
}

interface ConfirmModalFooterOptions {
    closeId?: string | undefined;
    closeLabel: string;
    closeAttributes?: AttributeProps | undefined;
    closeClassName?: string | undefined;
    confirmId?: string | undefined;
    confirmLabel: string;
    confirmAttributes?: AttributeProps | undefined;
    confirmClassName?: string | undefined;
    confirmDisabled?: boolean | undefined;
    extraRightButtons?: ModalButton[] | undefined;
    rightSectionClassName?: string | undefined;
    confirmFirst?: boolean | undefined;
}

const buildCardGridHeader = ({ title, description, actions = [], stats = [], containerClass, floating = true }: CardGridHeaderOptions): CardGridHeader => {
    const header: CardGridHeader = {
        title,
        floating,
        actions,
        stats,
        contentLayout: 'card-grid'
    };
    if (description !== undefined) header.description = description;
    if (containerClass) header.containerClass = containerClass;
    return header;
};

const buildCollectionSection = ({ id, className, role = 'list', tag = 'div' }: CollectionSectionOptions): CollectionSection => ({
    type: 'section',
    tag,
    id,
    className,
    role
});

const buildEmptyState = ({ id, className, title, description, icon, body, actions }: EmptyStateOptions): EmptyState => {
    const emptyState: EmptyState = {
        type: 'empty-state',
        id,
        className,
        hidden: true,
        title,
        ...(icon ? { icon } : {})
    };
    if (description !== undefined) emptyState.description = description;
    if (body !== undefined) emptyState.body = body;
    if (actions !== undefined) emptyState.actions = actions;
    return emptyState;
};

const buildCollectionSections = ({ gridId, gridClassName, emptyStates = [] }: CollectionSectionsOptions): (CollectionSection | EmptyState)[] => {
    const sections: (CollectionSection | EmptyState)[] = [buildCollectionSection({ id: gridId, className: gridClassName })];
    if (isArray(emptyStates) && emptyStates.length) sections.push(...emptyStates);
    return sections;
};

const buildSplitModalFooter = ({ closeId, closeLabel, closeAttributes, closeClassName = 'ui-button ui-variant-neutral', rightButtons, rightSectionClassName }: SplitModalFooterOptions): SplitModalFooter => ({
    layout: 'split',
    sections: [
        {
            align: 'left',
            buttons: [
                {
                    className: closeClassName,
                    ...(closeId ? { id: closeId } : {}),
                    ...(closeAttributes ? { attributes: closeAttributes } : {}),
                    content: closeLabel
                }
            ]
        },
        {
            align: 'right',
            ...(rightSectionClassName ? { className: rightSectionClassName } : {}),
            buttons: rightButtons
        }
    ]
});

const buildConfirmModalFooter = ({ closeId, closeLabel, closeAttributes, closeClassName = 'ui-button ui-variant-neutral', confirmId, confirmLabel, confirmAttributes, confirmClassName = 'ui-button ui-variant-danger', confirmDisabled = false, extraRightButtons = [], rightSectionClassName, confirmFirst = true }: ConfirmModalFooterOptions): SplitModalFooter => {
    const confirmButton: ModalButton = {
        className: confirmClassName,
        ...(confirmId ? { id: confirmId } : {}),
        ...(confirmAttributes ? { attributes: confirmAttributes } : {}),
        ...(confirmDisabled ? { disabled: true } : {}),
        content: confirmLabel
    };
    const extras = Array.isArray(extraRightButtons) ? [...extraRightButtons] : [];
    const buttons = confirmFirst ? [confirmButton, ...extras] : [...extras, confirmButton];
    return buildSplitModalFooter({
        closeId,
        closeLabel,
        closeAttributes,
        closeClassName,
        rightButtons: buttons,
        rightSectionClassName
    });
};

export { buildCardGridHeader, buildCollectionSection, buildCollectionSections, buildEmptyState, buildSplitModalFooter, buildConfirmModalFooter };
export type { CardGridHeaderOptions, CardGridHeader, CollectionSectionOptions, CollectionSection, EmptyStateOptions, EmptyState, CollectionSectionsOptions, ModalButton, SplitModalFooterOptions, ConfirmModalFooterOptions, SplitModalFooter };
