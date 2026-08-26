/* SoAI - Shared frontend MCP tool presentation [frontend/assets/ts/core/mcp/toolPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { McpTool } from '@core/mcp/configTypes.ts';
import { replaceUnderscoresWithSpaces } from '@core/primitives/text.ts';
import { sanitizeSvgDataUriToElement } from '@core/svgSanitizer.ts';
import { isObject, isString } from '@core/typeGuards.ts';

const normalizeToolNameForDisplay = (toolName: string): string => replaceUnderscoresWithSpaces(toolName);

const resolveToolIconSrc = (tool: McpTool): string | null => {
    const icons = tool.icons;
    if (icons.length === 0) {
        return null;
    }
    const firstIcon = icons[0];
    if (!isObject(firstIcon)) {
        return null;
    }
    const src = firstIcon['src'];
    if (!isString(src) || !src.trim()) {
        return null;
    }
    return src;
};

const decodeAndInjectSvgIcon = (dataUri: string): SVGSVGElement | null => {
    try {
        return sanitizeSvgDataUriToElement(dataUri, { className: 'mcp-tool-icon', ariaHidden: true });
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('MCP', 'Failed to sanitize MCP tool icon SVG', runtimeError);
        throw runtimeError;
    }
};

const resolveToolDescription = (tool: McpTool): string | null => {
    const definition = tool.definition;
    if (!definition || !isObject(definition)) return null;
    const functionDef = definition['function'];
    if (!isObject(functionDef)) return null;
    const description = functionDef['description'];
    if (!isString(description) || !description.trim()) return null;
    return description;
};

export { decodeAndInjectSvgIcon, normalizeToolNameForDisplay, resolveToolDescription, resolveToolIconSrc };
