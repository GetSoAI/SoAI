/* SoAI - Chat attachment thumbnail DOM preservation [frontend/assets/ts/features/chat/attachments/attachmentThumbnailDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

const ATTACHMENT_VISUAL_SELECTOR = '.chat-attachment-visual';
const ATTACHMENT_THUMBNAIL_SELECTOR = 'img[data-chat-attachment-thumbnail="true"]';

const resolveAttachmentVisuals = (root: HTMLElement): HTMLElement[] => {
    const visuals = dom.resolveAll(ATTACHMENT_VISUAL_SELECTOR, root).filter((element): element is HTMLElement => element instanceof HTMLElement);
    if (root.matches(ATTACHMENT_VISUAL_SELECTOR)) {
        visuals.unshift(root);
    }
    return visuals;
};

const resolveAttachmentThumbnail = (visual: HTMLElement): HTMLImageElement | null => {
    const image = dom.resolve(ATTACHMENT_THUMBNAIL_SELECTOR, visual);
    return image instanceof HTMLImageElement ? image : null;
};

const hasAttachmentThumbnail = (root: HTMLElement): boolean => {
    return resolveAttachmentVisuals(root).some((visual) => resolveAttachmentThumbnail(visual) !== null);
};

const preserveStableAttachmentThumbnailVisuals = (currentRoot: HTMLElement, nextRoot: HTMLElement): number => {
    const currentVisuals = resolveAttachmentVisuals(currentRoot);
    const nextVisuals = resolveAttachmentVisuals(nextRoot);
    const available = new Set(currentVisuals);
    let preservedCount = 0;
    for (const [index, nextVisual] of nextVisuals.entries()) {
        const nextImage = resolveAttachmentThumbnail(nextVisual);
        if (nextImage === null) {
            continue;
        }
        const exactMatch = currentVisuals.find((currentVisual) => available.has(currentVisual) && resolveAttachmentThumbnail(currentVisual)?.getAttribute('src') === nextImage.getAttribute('src')) ?? null;
        const indexedCandidate = currentVisuals.length === 1 && nextVisuals.length === 1 ? (currentVisuals[index] ?? null) : null;
        const stableLoadedCandidate = indexedCandidate !== null && available.has(indexedCandidate) && indexedCandidate.getAttribute('data-attachment-image-state') === 'loaded' && resolveAttachmentThumbnail(indexedCandidate) !== null ? indexedCandidate : null;
        const currentVisual = exactMatch ?? stableLoadedCandidate;
        if (currentVisual === null) {
            continue;
        }
        nextVisual.replaceWith(currentVisual);
        available.delete(currentVisual);
        preservedCount += 1;
    }
    return preservedCount;
};

export { hasAttachmentThumbnail, preserveStableAttachmentThumbnailVisuals };
