/* SoAI - Model detail page rendering layer layout implementation [frontend/assets/ts/pages/modeldetail/rendering/layout/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RowDefinition } from '@pages/modeldetail/rendering/layout/types.ts';

const renderRows = (type: string, items: readonly RowDefinition[]): string => {
    return items
        .map((item) => {
            const label = item.getLabel();
            const className = item.className ?? '';
            const rowClassName = item.rowClassName ? ` ${item.rowClassName}` : '';
            return `
    <div class="modeldetail-${type}-row${rowClassName}" id="${item.id}-row">
    <span class="modeldetail-${type}-label">${label}</span>
    <span class="modeldetail-${type}-value${className ? ' ' + className : ''}" id="${item.id}"></span>
    </div>`;
        })
        .join('');
};

const renderCard = (options: { id: string; title: string; content: string; hidden?: boolean }): string => {
    const hidden = options.hidden === true;
    return `
    <div class="modeldetail-card glass-surface-full${hidden ? ' u-hidden' : ''}" id="${options.id}">
    <div class="modeldetail-card-header"><h3 class="modeldetail-card-title">${options.title}</h3></div>
    <div class="modeldetail-card-body">${options.content}</div>
    </div>`;
};

export { renderCard, renderRows };
