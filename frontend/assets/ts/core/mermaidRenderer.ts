/* SoAI - Shared frontend mermaid renderer [frontend/assets/ts/core/mermaidRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import mermaid from 'mermaid';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { securityApi } from '@core/security/public.ts';
import { getCspNonce } from '@core/security/cspNonce.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { replaceChildrenFromHtml } from '@core/dom/html.ts';
import { createMermaidPlaceholder } from '@core/mermaid/placeholder.ts';

function detectCurrentTheme(): 'dark' | 'default' {
    const root = document.documentElement;
    const isDarkMode = root.classList.contains('theme-dark');
    return isDarkMode ? 'dark' : 'default';
}

function getMermaidFontFamily(): string {
    const body = document.body;
    if (!body) {
        throw new Error('Mermaid rendering requires document.body');
    }
    const fontFamily = getComputedStyle(body).fontFamily.trim();
    if (!fontFamily) {
        throw new Error('Mermaid rendering requires a base font family');
    }
    return fontFamily;
}

function getMermaidFontSize(container: HTMLElement): string {
    const fontSize = getComputedStyle(container).fontSize.trim();
    if (!fontSize) {
        throw new Error('Mermaid rendering requires a computed font size');
    }
    return fontSize;
}

function addNonceToSvgStyles(svgContent: string): string {
    const nonce = getCspNonce();
    if (!nonce) {
        return svgContent;
    }
    const escapedNonce = securityApi.escapeAttribute(nonce);
    return svgContent.replace(/<style([^>]*)>/gi, (styleOpenTag: string, rawAttributes: string): string => {
        const attributes = String(rawAttributes ?? '').replace(/\snonce\s*=\s*(?:"[^"]*"|'[^']*')/gi, '');
        const tagNamePrefix = styleOpenTag.slice(0, '<style'.length);
        return `${tagNamePrefix}${attributes} nonce="${escapedNonce}">`;
    });
}

type MermaidTheme = 'dark' | 'default';

interface MermaidThemeConfig {
    theme: MermaidTheme;
    fontFamily: string;
    fontSize: string;
}

const buildMermaidConfig = (container: HTMLElement): MermaidThemeConfig => ({
    theme: detectCurrentTheme(),
    fontFamily: getMermaidFontFamily(),
    fontSize: getMermaidFontSize(container)
});

const computeMermaidConfigKey = ({ theme, fontFamily, fontSize }: MermaidThemeConfig): string => `${theme}:${fontFamily}:${fontSize}`;

let lastMermaidConfigKey: string | null = null;
const applyMermaidConfig = (config: MermaidThemeConfig): void => {
    const configKey = computeMermaidConfigKey(config);
    if (configKey === lastMermaidConfigKey) {
        return;
    }
    lastMermaidConfigKey = configKey;
    mermaid.initialize({
        startOnLoad: false,
        theme: config.theme,
        securityLevel: 'strict',
        fontFamily: config.fontFamily,
        themeVariables: {
            fontFamily: config.fontFamily,
            fontSize: config.fontSize
        },
        flowchart: {
            useMaxWidth: true,
            htmlLabels: false,
            curve: 'basis'
        },
        sequence: {
            useMaxWidth: true,
            wrap: true
        },
        gantt: {
            useMaxWidth: true
        }
    });
};

let renderQueue: Promise<void> = Promise.resolve();
const enqueueMermaidRender = async (task: () => Promise<void>): Promise<void> => {
    renderQueue = renderQueue
        .catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('MermaidRenderer', 'Mermaid render queue recovered from previous error', runtimeError);
        })
        .then(async () => {
            await task();
        });
    return await renderQueue;
};

function initializeMermaid(container: HTMLElement): void {
    applyMermaidConfig(buildMermaidConfig(container));
}

async function renderMermaidDiagram(container: HTMLElement): Promise<void> {
    await enqueueMermaidRender(async () => {
        const diagramDefinition = container.getAttribute('data-mermaid-definition');
        if (!diagramDefinition) {
            return;
        }

        initializeMermaid(container);
        const diagramId = generateSecureId({ prefix: 'mermaid', format: 'hex', separator: '-' });
        try {
            const { svg } = await mermaid.render(diagramId, diagramDefinition, container);
            const svgWithNonce = addNonceToSvgStyles(svg);
            if (!container.isConnected) {
                return;
            }
            replaceChildrenFromHtml({ element: container, html: securityApi.sanitizeSvg(svgWithNonce), context: container });
            container.classList.remove('mermaid-loading');
            container.classList.add('mermaid-rendered');
        } catch (error) {
            const errorMessage = ensureError(error).message;
            if (!container.isConnected) {
                return;
            }
            replaceChildrenFromHtml({
                element: container,
                html: securityApi.sanitizeHtml(`<div class="mermaid-error"><span class="mermaid-error-icon">&#9888;</span><span class="mermaid-error-text">${securityApi.escapeHtml(errorMessage)}</span></div>`),
                context: container
            });
            container.classList.remove('mermaid-loading');
            container.classList.add('mermaid-error-container');
        }
    });
}

async function renderAllMermaidDiagrams(rootElement: HTMLElement): Promise<void> {
    const mermaidContainers = dom.resolveAll('.mermaid-container.mermaid-loading', rootElement).filter((node): node is HTMLElement => isHTMLElement(node));
    const renderPromises = mermaidContainers.map((container) => renderMermaidDiagram(container));
    await Promise.all(renderPromises);
}

export { renderAllMermaidDiagrams, createMermaidPlaceholder };
