/* SoAI - Shared primitives download [frontend/assets/ts/core/primitives/download.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isHTMLElement, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const sanitizeDownloadFilename = (name: string | null | undefined, fallback: string, maxLength: number = 140): string => {
    const base = isString(name) ? name.trim() : '';
    const sanitized = base
        .replace(/[\0<>:"/\\|?*]+/g, '')
        .replace(/\s+/g, ' ')
        .trim();
    const candidate = sanitized || fallback;
    return candidate.slice(0, Math.max(1, maxLength));
};

const triggerDownloadLink = (options: { href: string; filename?: string; forceDownload?: boolean; revokeObjectUrl?: boolean }): void => {
    const href = toTrimmedString(options.href);
    if (!href) throw new Error('Download href is required');
    const filename = options.filename ? toTrimmedString(options.filename) : '';
    const forceDownload = Boolean(options.forceDownload);
    const created = dom.create('a', {
        href,
        ...(filename ? { download: filename } : forceDownload ? { download: '' } : {})
    });
    if (!(created instanceof HTMLAnchorElement)) {
        throw new Error('Expected an anchor element for download link');
    }
    const anchor: HTMLAnchorElement = created;
    const body = dom.resolve('body');
    if (!isHTMLElement(body)) throw new Error('Document body is unavailable');
    dom.appendChild(body, anchor);
    dom.flush();
    anchor.click();
    setTimeout(() => {
        if (options.revokeObjectUrl) URL.revokeObjectURL(href);
        dom.remove(anchor);
        dom.flush();
    }, 0);
};

export const downloadFile = (data: string | JsonValue, filename: string, type: string = 'application/json'): void => {
    const blob = new Blob([isString(data) ? data : JSON.stringify(data, null, 2)], { type });
    triggerDownloadLink({
        href: URL.createObjectURL(blob),
        filename,
        revokeObjectUrl: true
    });
};

export const downloadUrl = (url: string): void => {
    const href = toTrimmedString(url);
    if (!href) throw new Error('downloadUrl requires a url');
    triggerDownloadLink({ href, forceDownload: true });
};

export { sanitizeDownloadFilename, triggerDownloadLink };
