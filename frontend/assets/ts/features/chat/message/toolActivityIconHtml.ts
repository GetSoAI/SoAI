/* SoAI - Main-thread tool icon resolution for chat tool activities [frontend/assets/ts/features/chat/message/toolActivityIconHtml.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { sanitizeSvgDataUriToHtml } from '@core/svgSanitizer.ts';
import type { ChatToolIconServiceContract } from '@core/chat/protocols.ts';

const resolveInlineToolIconHtml = (toolIconService: ChatToolIconServiceContract, toolName: string): string | null => {
    const toolIconDataUri = toolIconService.getToolIcon(toolName);
    if (!toolIconDataUri) {
        return null;
    }
    try {
        return sanitizeSvgDataUriToHtml(toolIconDataUri, { ariaHidden: true });
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ChatMessageManager', 'Tool icon SVG sanitization failed', { toolName, error: runtimeError });
        throw runtimeError;
    }
};

export { resolveInlineToolIconHtml };
