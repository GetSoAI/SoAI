/* SoAI - Shared discovery manual resource message [frontend/assets/ts/core/discovery/manualResourceMessage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

interface ManualResourceMessageOptions {
    sanitizeHtml: (value: string) => string;
    folderPath?: string | undefined;
    defaultFolderName: string;
    resolvedPath?: string | undefined;
    renderDescription: (folder: string) => string;
    renderDescriptionWithResolvedPath: (values: { folder: string; resolvedPath: string }) => string;
}

const requireSanitizeHtml = (sanitizeHtml: (value: string) => string): ((value: string) => string) => {
    return (value: string): string => {
        const sanitized = sanitizeHtml(value);
        if (typeof sanitized !== 'string') {
            throw new Error('Manual resource message sanitizeHtml must return string');
        }
        return sanitized;
    };
};

const buildManualResourceMessage = (options: ManualResourceMessageOptions): string => {
    const sanitizeHtml = requireSanitizeHtml(options.sanitizeHtml);
    const resourcePath = toTrimmedString(options.folderPath);
    const folderName = resourcePath ? resourcePath : options.defaultFolderName;
    const folder = `<code>${sanitizeHtml(folderName)}</code>`;
    const resolvedPath = toTrimmedString(options.resolvedPath);
    if (resolvedPath) {
        return options.renderDescriptionWithResolvedPath({
            folder,
            resolvedPath: `<code>${sanitizeHtml(resolvedPath)}</code>`
        });
    }
    return options.renderDescription(folder);
};

export { buildManualResourceMessage };
