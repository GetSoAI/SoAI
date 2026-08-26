/* SoAI - Shared frontend SVG sanitizer [frontend/assets/ts/core/svgSanitizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { coerceErrorMessage } from '@core/errors/coerce.ts';

type SvgSanitizeOptions = {
    className?: string;
    ariaHidden?: boolean;
};

const SVG_MIME_PREFIX = 'data:image/svg+xml';
const SUPPORTED_SVG_DATA_URI_METADATA = new Set<string>([SVG_MIME_PREFIX, `${SVG_MIME_PREFIX};charset=utf-8`, `${SVG_MIME_PREFIX};base64`, `${SVG_MIME_PREFIX};charset=utf-8;base64`]);

const ALLOWED_TAG_NAMES = new Set<string>(['svg', 'g', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse', 'title', 'desc']);

const ALLOWED_ATTRIBUTE_NAMES = new Set<string>(['xmlns', 'viewbox', 'width', 'height', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit', 'stroke-dasharray', 'stroke-dashoffset', 'opacity', 'fill-opacity', 'stroke-opacity', 'd', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'points', 'transform', 'focusable', 'role', 'aria-hidden', 'class']);

const resolveSvgDataUriParts = (dataUri: string): { metadata: string; payload: string } => {
    const trimmed = dataUri.trim();
    const commaIndex = trimmed.indexOf(',');
    if (commaIndex === -1) {
        throw new Error('SVG data URI is missing payload separator');
    }
    const rawMetadata = trimmed.slice(0, commaIndex);
    const metadata = rawMetadata.toLowerCase();
    if (!rawMetadata.startsWith(SVG_MIME_PREFIX) || !SUPPORTED_SVG_DATA_URI_METADATA.has(metadata)) {
        throw new Error('SVG data URI metadata is unsupported');
    }
    const payload = trimmed.slice(commaIndex + 1);
    if (!payload) {
        throw new Error('SVG data URI payload is empty');
    }
    return { metadata, payload };
};

const decodeSvgDataUriPayload = (dataUri: string): string => {
    const { metadata, payload } = resolveSvgDataUriParts(dataUri);
    if (metadata.includes(';base64')) {
        try {
            return atob(payload);
        } catch (error) {
            const message = coerceErrorMessage(error);
            throw new Error(`SVG data URI base64 decoding failed: ${message}`);
        }
    }
    try {
        return decodeURIComponent(payload);
    } catch (error) {
        const message = coerceErrorMessage(error);
        throw new Error(`SVG data URI decoding failed: ${message}`);
    }
};

const requireSupportedSvgDataUri = (dataUri: string): string => {
    decodeSvgDataUriPayload(dataUri);
    return dataUri.trim();
};

const isUnsafeAttributeValue = (value: string): boolean => {
    const normalized = value.trim().toLowerCase();
    if (!normalized) {
        return false;
    }
    if (normalized.includes('url(')) {
        return true;
    }
    if (normalized.startsWith('javascript:') || normalized.startsWith('vbscript:')) {
        return true;
    }
    return false;
};

const sanitizeSvgElementInPlace = (svg: SVGSVGElement): void => {
    const nodesToRemove: Element[] = [];
    const walker = svg.ownerDocument.createTreeWalker(svg, NodeFilter.SHOW_ELEMENT);
    let current: Node | null = walker.currentNode;
    while (current) {
        if (current instanceof Element) {
            const tagName = current.tagName.toLowerCase();
            if (!ALLOWED_TAG_NAMES.has(tagName)) {
                nodesToRemove.push(current);
            } else {
                const attributeNames = current.getAttributeNames();
                for (const rawAttributeName of attributeNames) {
                    const attributeName = rawAttributeName.toLowerCase();
                    if (attributeName.startsWith('on')) {
                        current.removeAttribute(rawAttributeName);
                        continue;
                    }
                    if (!ALLOWED_ATTRIBUTE_NAMES.has(attributeName)) {
                        current.removeAttribute(rawAttributeName);
                        continue;
                    }
                    const value = current.getAttribute(rawAttributeName);
                    if (isString(value) && isUnsafeAttributeValue(value)) {
                        current.removeAttribute(rawAttributeName);
                    }
                }
            }
        }
        current = walker.nextNode();
    }
    nodesToRemove.forEach((node) => node.remove());
};

const parseSvgText = (svgText: string): SVGSVGElement => {
    const parser = new DOMParser();
    const document = parser.parseFromString(svgText, 'image/svg+xml');
    const element = document.documentElement;
    if (!(element instanceof SVGSVGElement)) {
        throw new Error('Parsed SVG root element is not an SVGSVGElement');
    }
    return element;
};

const applySvgDefaults = (svg: SVGSVGElement, options: SvgSanitizeOptions): void => {
    const className = isString(options.className) && options.className.trim() ? options.className.trim() : null;
    if (className) {
        svg.classList.add(...className.split(/\s+/).filter(Boolean));
    }
    const ariaHidden = options.ariaHidden !== false;
    svg.setAttribute('aria-hidden', ariaHidden ? 'true' : 'false');
};

const sanitizeSvgDataUriToElement = (dataUri: string, options: SvgSanitizeOptions = {}): SVGSVGElement => {
    const svgText = decodeSvgDataUriPayload(dataUri);
    const svg = parseSvgText(svgText);
    sanitizeSvgElementInPlace(svg);
    applySvgDefaults(svg, options);
    return svg;
};

const sanitizeSvgDataUriToHtml = (dataUri: string, options: SvgSanitizeOptions = {}): string => {
    const svg = sanitizeSvgDataUriToElement(dataUri, options);
    return new XMLSerializer().serializeToString(svg);
};

export { requireSupportedSvgDataUri, sanitizeSvgDataUriToElement, sanitizeSvgDataUriToHtml };
export type { SvgSanitizeOptions };
