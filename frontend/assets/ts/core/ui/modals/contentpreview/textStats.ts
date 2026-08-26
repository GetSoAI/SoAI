/* SoAI - Content preview text stats rendering [frontend/assets/ts/core/ui/modals/contentpreview/textStats.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { appendContentPreviewSourceReferenceMetric } from '@core/ui/modals/contentpreview/sourceReference.ts';
import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewTextMetric = Readonly<{
    label: string;
    value: string;
}>;

const countTextLines = (content: string): number => {
    if (content.length === 0) {
        return 0;
    }
    return content.split(/\r\n|\r|\n/).length;
};

const countTextCharacters = (content: string): number => Array.from(content).length;

const countTextWords = (content: string): number => {
    const trimmed = content.trim();
    if (!trimmed) {
        return 0;
    }
    return trimmed.split(/\s+/).length;
};

const countTextBytes = (content: string): number => new TextEncoder().encode(content).length;

const createTextInfoItem = (documentRef: Document, metric: ContentPreviewTextMetric): HTMLDivElement => {
    const item = documentRef.createElement('div');
    item.className = 'content-preview-text-info-item';

    const label = documentRef.createElement('dt');
    label.className = 'content-preview-text-info-label';
    label.textContent = metric.label;

    const value = documentRef.createElement('dd');
    value.className = 'content-preview-text-info-value';
    value.textContent = metric.value;

    item.appendChild(label);
    item.appendChild(value);
    return item;
};

const resolveTextMetrics = (content: string): readonly ContentPreviewTextMetric[] => [
    {
        label: i18n.t('contentPreview.textInfo.lines'),
        value: i18n.formatNumber(countTextLines(content))
    },
    {
        label: i18n.t('contentPreview.textInfo.characters'),
        value: i18n.formatNumber(countTextCharacters(content))
    },
    {
        label: i18n.t('contentPreview.textInfo.words'),
        value: i18n.formatNumber(countTextWords(content))
    },
    {
        label: i18n.t('contentPreview.textInfo.size'),
        value: formatBytes(countTextBytes(content))
    }
];

const renderContentPreviewTextStats = (host: HTMLElement, content: string, sourceReference: ContentPreviewSourceReference | null): void => {
    const documentRef = dom.getDocument();
    host.textContent = '';
    if (!(host instanceof HTMLDListElement)) {
        throw new TypeError('Content preview text stats host must be a description list');
    }
    appendContentPreviewSourceReferenceMetric(documentRef, host, sourceReference, {
        item: 'content-preview-text-info-item',
        label: 'content-preview-text-info-label',
        value: 'content-preview-text-info-value'
    });
    for (const metric of resolveTextMetrics(content)) {
        host.appendChild(createTextInfoItem(documentRef, metric));
    }
    host.classList.remove('u-hidden');
    host.setAttribute('aria-hidden', 'false');
};

const hideContentPreviewTextStats = (host: HTMLElement): void => {
    host.textContent = '';
    host.classList.add('u-hidden');
    host.setAttribute('aria-hidden', 'true');
};

export { hideContentPreviewTextStats, renderContentPreviewTextStats };
