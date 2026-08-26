/* SoAI - Shared UI operation progress [frontend/assets/ts/core/ui/operationProgress.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampPercent } from '@core/primitives/clampNumber.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';

type OperationProgressState = 'idle' | 'pending' | 'running' | 'success' | 'error';

interface OperationProgressOptions {
    label: string;
    state: OperationProgressState;
    percent?: number;
    detail?: string;
    statusText?: string;
}

const renderOperationProgress = ({ label, state, percent, detail, statusText }: OperationProgressOptions): TrustedHtml => {
    const badgeMarkup = statusText ? uiHtml`<span class="settings-operation-progress__badge">${statusText}</span>` : uiHtml``;
    const detailMarkup = detail ? uiHtml`<div class="settings-operation-progress__detail" data-operation-progress="detail">${detail}</div>` : uiHtml``;
    const progressMarkup = typeof percent === 'number' ? renderDeterminateProgress(label, percent) : uiHtml``;

    return uiHtml`<div class="settings-operation-progress settings-card-surface" data-state="${state}"><div class="settings-operation-progress__row">${badgeMarkup}<span class="settings-operation-progress__label" data-operation-progress="label">${label}</span></div>${progressMarkup}${detailMarkup}</div>`;
};

const renderDeterminateProgress = (label: string, percent: number): TrustedHtml => {
    const clampedPercent = clampPercent(percent);
    const percentText = `${Math.round(clampedPercent)}%`;
    return uiHtml`<progress class="settings-operation-progress__bar" data-operation-progress="bar" max="100" value="${clampedPercent}" aria-label="${label}"></progress><div class="settings-operation-progress__meta"><span data-operation-progress="message">${label}</span><span data-operation-progress="percent">${percentText}</span></div>`;
};

export { renderOperationProgress };
export type { OperationProgressOptions, OperationProgressState };
