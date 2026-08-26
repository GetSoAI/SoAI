/* SoAI - Chat feature inline activity status rendering [frontend/assets/ts/features/chat/message/messageview/inlineActivityStatusRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { resolveToolActivityStatusLabel } from '@features/chat/message/toolActivityStatusLabel.ts';

interface InlineActivityStatusRenderDependencies {
    escapeAttribute: (value: string) => string;
    getIconHtml: (name: IconName, options?: IconOptions) => string;
}

const INLINE_ACTIVITY_ICON_STROKE_WIDTH = 1.7;

const renderInlineStatusDot = (dependencies: InlineActivityStatusRenderDependencies, statusKey: string): string => {
    const statusLabel = resolveToolActivityStatusLabel(statusKey);
    return `<span class="inline-activity-status-led" role="img" aria-label="${dependencies.escapeAttribute(statusLabel)}"></span>`;
};

const resolveInlineStatusIconName = (status: string, defaultIconName: IconName): IconName => {
    if (status === 'error' || status === 'cancelled') {
        return 'close';
    }
    return defaultIconName;
};

const renderInlineStatusIcon = (dependencies: InlineActivityStatusRenderDependencies, status: string, defaultIconName: IconName): string => {
    const iconName = resolveInlineStatusIconName(status, defaultIconName);
    const icon = dependencies.getIconHtml(iconName, { size: 16, strokeWidth: INLINE_ACTIVITY_ICON_STROKE_WIDTH });
    return `<span class="inline-activity-icon" aria-hidden="true">${icon}</span>`;
};

export { renderInlineStatusDot, renderInlineStatusIcon, resolveInlineStatusIconName };
export type { InlineActivityStatusRenderDependencies };
