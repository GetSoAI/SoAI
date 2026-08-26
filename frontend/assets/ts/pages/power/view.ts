/* SoAI - Power page rendering [frontend/assets/ts/pages/power/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { isArray, isFunction, isString } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { primitives } from '@core/uiprimitives/public.ts';
import type { PageInstance } from '@core/uiprimitives/types.ts';

export interface PowerPageViewActionOption {
    parameter: string;
    type?: 'checkbox' | 'number';
    label?: string;
    defaultValue?: number | boolean;
    min?: number;
    max?: number;
    step?: number;
}

export interface PowerPageViewAction {
    key: string;
    title: string;
    description: string;
    icon: IconName;
    buttonVariant: string;
    tone: string;
    options?: PowerPageViewActionOption[];
}

export interface PowerPageViewHost {
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
    getOptionId: (actionKey: string, parameter: string) => string;
}

export interface PowerPageViewResult {
    header: GenerateStandardHeaderOptions;
    content: string;
}

const createBuilderHost = (): PageInstance => ({ pageId: 'power' });

const RESTART_NOTICE_ACTION_KEYS = new Set<string>(['restartApplication', 'rebootSystem']);

const renderRestartNotice = (host: PowerPageViewHost, actionKey: string, escapeHtml: (value: string) => string): string => {
    const message = i18n.t('power.restartReminder.message');
    const icon = host.getIconSync('warning', { size: 20, strokeWidth: 1.8 });
    return `<div class="power-restart-notice u-hidden" id="power-restart-notice-${actionKey}" aria-hidden="true">
                <span class="power-restart-notice-icon">${icon.html}</span>
                <div class="power-restart-notice-content">
                    <p class="power-restart-notice-message" id="power-restart-notice-message-${actionKey}">${escapeHtml(message)}</p>
                </div>
            </div>`;
};

const renderOption = (dependencies: { host: PowerPageViewHost; actionKey: string; option: PowerPageViewActionOption; escapeHtml: (value: string) => string; escapeAttributeValue: (value: string | number | boolean) => string }): string => {
    const { host, actionKey, option, escapeHtml, escapeAttributeValue } = dependencies;
    if (!option.parameter) {
        throw new Error('Power option requires param');
    }
    const optionId = host.getOptionId(actionKey, option.parameter);
    const escapedId = escapeAttributeValue(optionId);

    if (option.type === 'checkbox') {
        const label = escapeHtml(option.label ?? '');
        const checked = option.defaultValue ? ' checked' : '';
        return `<label class="toggle-switch power-option">
                    <input type="checkbox" id="${escapedId}"${checked}>
                    <span class="slider"></span>
                    <span>${label}</span>
                </label>`;
    }

    if (option.type === 'number') {
        const label = escapeHtml(option.label ?? '');
        const attributes: string[] = [`id="${escapedId}"`, 'class="power-option-input"', `value="${escapeAttributeValue(option.defaultValue ?? 0)}"`];
        if (option.min !== undefined) attributes.push(`min="${escapeAttributeValue(option.min)}"`);
        if (option.max !== undefined) attributes.push(`max="${escapeAttributeValue(option.max)}"`);
        if (option.step !== undefined) attributes.push(`step="${escapeAttributeValue(option.step)}"`);
        return `<div class="delay-option">
                    <label for="${escapedId}">${label}</label>
                    <input type="number" ${attributes.join(' ')}>
                </div>`;
    }

    return '';
};

const renderActionBody = (host: PowerPageViewHost, action: PowerPageViewAction): string => {
    const segments: string[] = [];
    const escapeHtml = primitives.escapeHtml;
    const builder = primitives.collection.createBuilder(createBuilderHost());
    const escapeAttributeValue = (value: string | number | boolean): string => builder.escapeAttributeValue(value);

    if (RESTART_NOTICE_ACTION_KEYS.has(action.key)) {
        segments.push(renderRestartNotice(host, action.key, escapeHtml));
    }

    if (isArray(action.options) && action.options.length > 0) {
        const optionsMarkup = action.options
            .map((option) =>
                renderOption({
                    host,
                    actionKey: action.key,
                    option,
                    escapeHtml,
                    escapeAttributeValue
                })
            )
            .filter(Boolean)
            .join('');
        if (optionsMarkup) {
            segments.push(
                builder.section({
                    tag: 'div',
                    className: 'power-options',
                    children: optionsMarkup
                })
            );
        }
    }

    if (!segments.length) {
        return '';
    }

    return builder.section({
        tag: 'div',
        className: 'action-body',
        children: segments
    });
};

const renderActionCard = (host: PowerPageViewHost, action: PowerPageViewAction): string => {
    const builder = primitives.collection.createBuilder(createBuilderHost());
    const title = builder.escapeHtml(action.title);
    const description = builder.escapeHtml(action.description);
    const icon = host.getIconSync(action.icon, { size: 36, strokeWidth: 1.8 });
    const buttonClass = ['ui-button', action.buttonVariant, 'power-icon'].filter(Boolean).join(' ');

    const header = builder.section({
        tag: 'header',
        className: 'ui-collection-card__header action-header power-action-header',
        children: [
            builder.section({
                tag: 'div',
                className: 'action-info',
                children: [
                    builder.button({
                        className: buttonClass,
                        type: 'button',
                        dataset: { action: action.key },
                        aria: { label: action.title },
                        content: `<span class="power-icon-symbol">${icon.html}</span>`
                    }),
                    `<h3 class="action-title">${title}</h3>`
                ]
            })
        ]
    });

    const descriptionBlock = description
        ? builder.section({
              tag: 'div',
              className: 'ui-collection-card__content power-action-content',
              children: `<p class="action-description">${description}</p>`
          })
        : '';

    const body = renderActionBody(host, action);
    const toneClass = action.tone ? `power-action--${builder.escapeAttributeValue(action.tone)}` : 'power-action--neutral';
    const cardChildren: string[] = [header];
    if (descriptionBlock) cardChildren.push(descriptionBlock);
    if (body) {
        cardChildren.push(
            builder.section({
                tag: 'div',
                className: 'ui-collection-card__body power-action-body',
                children: body
            })
        );
    }

    return builder.section({
        tag: 'article',
        role: 'listitem',
        className: ['ui-collection-card', 'power-action', 'power-action-card', toneClass].join(' '),
        dataset: { 'action-key': action.key },
        children: cardChildren
    });
};

const buildHeader = (): GenerateStandardHeaderOptions => {
    return {
        containerClass: 'power-container collections-page page-scrollable',
        title: i18n.t('pages.power.title'),
        description: i18n.t('power.description'),
        contentLayout: 'card-grid'
    };
};

export const renderPowerPageView = (host: PowerPageViewHost, actions: PowerPageViewAction[]): PowerPageViewResult => {
    if (!isFunction(host.getIconSync) || !isFunction(host.getOptionId)) {
        throw new Error('Power view host is missing required functions');
    }
    const builder = primitives.collection.createBuilder(createBuilderHost());
    const cards = actions.map((action) => renderActionCard(host, action)).join('');
    const grid = builder.section({
        tag: 'div',
        id: 'power-grid',
        className: 'ui-collection-grid',
        role: 'list',
        children: cards
    });
    const content = builder.section({
        tag: 'div',
        className: 'power-content',
        children: grid
    });
    if (!isString(content) || !content.trim()) {
        throw new Error('Power view must produce content markup');
    }
    return { header: buildHeader(), content };
};
