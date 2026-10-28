/* SoAI - Model detail page rendering layer layout implementation [frontend/assets/ts/pages/modeldetail/rendering/layout/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, securityApi } from '@core/security/public.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { ACTION_COPY_MODEL_DETAIL_VALUE } from '@features/modeldetail/public.ts';
import type { RowDefinition } from '@pages/modeldetail/rendering/layout/types.ts';

const MODEL_DETAIL_FACT_CLASS = 'modeldetail-fact';

const renderCopyButton = (sourceId: string, label: string): string => {
    const copyLabel = `${i18n.t('common.copy')}: ${label}`;
    const icon = renderIconSlot(getIconSync('copy', { size: 14, strokeWidth: 1.5 }));
    return `<button type="button" class="ui-icon-button ui-icon-button-small modeldetail-copy-button" data-action="${ACTION_COPY_MODEL_DETAIL_VALUE}" data-copy-source="${sourceId}" ${renderLabelAttributes(copyLabel).html}>${icon.html}</button>`;
};

const renderSpecRow = (options: { id?: string | undefined; label: string; value?: string | undefined; tooltip?: string | undefined; labelClassName?: string | undefined; valueClassName?: string | undefined; copyable?: boolean | undefined; hidden?: boolean | undefined; trailing?: string | undefined }): string => {
    const rowClassName = ['modeldetail-spec-row', options.id ? MODEL_DETAIL_FACT_CLASS : '', options.hidden ? 'u-hidden' : ''].filter(Boolean).join(' ');
    const labelClassName = ['modeldetail-spec-label', options.labelClassName ?? ''].filter(Boolean).join(' ');
    const valueClassName = ['modeldetail-spec-value', options.valueClassName ?? ''].filter(Boolean).join(' ');
    const rowId = options.id ? ` id="${options.id}-row"` : '';
    const valueId = options.id ? ` id="${options.id}" data-fact-tooltip="true"` : '';
    const tooltip = options.tooltip ? ` data-tooltip="${securityApi.escapeAttribute(options.tooltip)}"` : '';
    const copy = options.copyable && options.id ? renderCopyButton(options.id, options.label) : '';
    return `<div class="${rowClassName}"${rowId}><dt class="${labelClassName}"${tooltip}>${options.label}</dt><dd class="modeldetail-spec-data"><span dir="auto" class="${valueClassName}"${valueId}>${options.value ?? ''}</span>${copy}${options.trailing ?? ''}</dd></div>`;
};

const renderSpecRows = (items: readonly RowDefinition[]): string => items.map((item) => renderSpecRow({ id: item.id, label: item.getLabel(), copyable: item.copyable, hidden: true })).join('');

const renderCard = (options: { id: string; title: string; content: string; hidden?: boolean; className?: string; bodyClassName?: string; headerActions?: string }): string => {
    const className = ['modeldetail-card', 'glass-surface-full', options.className ?? '', options.hidden === true ? 'u-hidden' : ''].filter(Boolean).join(' ');
    const bodyClassName = ['modeldetail-card-body', options.bodyClassName ?? ''].filter(Boolean).join(' ');
    return `
    <section class="${className}" id="${options.id}" aria-label="${options.title}">
    <div class="card-title-bar modeldetail-card-header"><h3 class="card-title modeldetail-card-title">${options.title}</h3>${options.headerActions ? `<div class="card-title-controls">${options.headerActions}</div>` : ''}</div>
    <div class="${bodyClassName}">${options.content}</div>
    </section>`;
};

export { MODEL_DETAIL_FACT_CLASS, renderCard, renderSpecRow, renderSpecRows };
