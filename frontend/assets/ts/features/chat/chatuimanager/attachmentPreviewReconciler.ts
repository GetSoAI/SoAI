/* SoAI - Keyed chat attachment preview reconciler [frontend/assets/ts/features/chat/chatuimanager/attachmentPreviewReconciler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { computeHash } from '@core/primitives/hash.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { hasAttachmentThumbnail, preserveStableAttachmentThumbnailVisuals } from '@features/chat/attachments/attachmentThumbnailDom.ts';

interface AttachmentPreviewReconcilerContext {
    dependencies: {
        dom: {
            getDocument: () => Document;
        };
        updateAttribute: (element: Element, attr: string, value: string | null) => void;
    };
}

type AttachmentPreviewEntry = {
    id: string;
    html: TrustedHtml;
};

type AttachmentPreviewReconciliation = {
    thumbnailsChanged: boolean;
};

const ATTACHMENT_UI_ID_ATTRIBUTE = 'data-attachment-ui-id';
const ATTACHMENT_SIGNATURE_ATTRIBUTE = 'data-attachment-render-signature';
const PRESENCE_ATTRIBUTE = 'data-presence';
const PRESENCE_ATOMIC_ATTRIBUTE = 'data-presence-atomic';
const PRESENCE_VISUAL_ONLY_ATTRIBUTE = 'data-presence-visual-only';

const resolveEntrySignature = (entry: AttachmentPreviewEntry): string => `${String(entry.html.html.length)}:${computeHash(entry.html.html).toString(36)}`;

const createEntryElement = (context: AttachmentPreviewReconcilerContext, entry: AttachmentPreviewEntry, signature: string): HTMLElement => {
    const documentRef = context.dependencies.dom.getDocument();
    const element = parseSingleRootElement({ documentRef, html: entry.html, context: documentRef });
    if (element === null) {
        throw new Error('Attachment preview entry must render one HTMLElement root');
    }
    context.dependencies.updateAttribute(element, ATTACHMENT_UI_ID_ATTRIBUTE, entry.id);
    context.dependencies.updateAttribute(element, ATTACHMENT_SIGNATURE_ATTRIBUTE, signature);
    context.dependencies.updateAttribute(element, PRESENCE_ATTRIBUTE, '');
    context.dependencies.updateAttribute(element, PRESENCE_ATOMIC_ATTRIBUTE, '');
    context.dependencies.updateAttribute(element, PRESENCE_VISUAL_ONLY_ATTRIBUTE, '');
    return element;
};

const collectExistingElements = (preview: HTMLElement): Map<string, HTMLElement> => {
    const elements = new Map<string, HTMLElement>();
    for (const child of preview.children) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        const id = child.getAttribute(ATTACHMENT_UI_ID_ATTRIBUTE);
        if (id === null || !id.trim()) {
            child.remove();
            continue;
        }
        elements.set(id, child);
    }
    return elements;
};

const patchEntryElement = (context: AttachmentPreviewReconcilerContext, current: HTMLElement, next: HTMLElement): boolean => {
    if (current.tagName !== next.tagName) {
        const entryId = current.getAttribute(ATTACHMENT_UI_ID_ATTRIBUTE) ?? 'untracked';
        throw new Error(`Attachment preview entry root element type changed for ${entryId}: ${current.tagName} -> ${next.tagName}`);
    }
    for (const name of current.getAttributeNames()) {
        if (!next.hasAttribute(name)) {
            context.dependencies.updateAttribute(current, name, null);
        }
    }
    for (const name of next.getAttributeNames()) {
        const value = next.getAttribute(name);
        if (value === null) {
            throw new Error('Attachment preview entry attribute disappeared while patching');
        }
        context.dependencies.updateAttribute(current, name, value);
    }
    if (!hasAttachmentThumbnail(current) && !hasAttachmentThumbnail(next)) {
        reconcileChildNodes(current, Array.from(next.childNodes));
        return false;
    }
    const thumbnailPreserved = preserveStableAttachmentThumbnailVisuals(current, next, 'clone') > 0;
    reconcileChildNodes(current, Array.from(next.childNodes));
    return !thumbnailPreserved && hasAttachmentThumbnail(current);
};

const reconcileAttachmentPreview = (context: AttachmentPreviewReconcilerContext, preview: HTMLElement, entries: readonly AttachmentPreviewEntry[], detached: Map<string, HTMLElement> = new Map()): AttachmentPreviewReconciliation => {
    const existing = collectExistingElements(preview);
    for (const [id, element] of detached.entries()) {
        if (!existing.has(id)) {
            existing.set(id, element);
        }
    }
    const retainedIds = new Set<string>();
    let thumbnailsChanged = false;
    for (const [index, entry] of entries.entries()) {
        retainedIds.add(entry.id);
        const current = existing.get(entry.id);
        const signature = resolveEntrySignature(entry);
        let element = current ?? createEntryElement(context, entry, signature);
        if (current === undefined) {
            thumbnailsChanged = hasAttachmentThumbnail(element) || thumbnailsChanged;
        }
        if (current && current.getAttribute(ATTACHMENT_SIGNATURE_ATTRIBUTE) !== signature) {
            thumbnailsChanged = patchEntryElement(context, current, createEntryElement(context, entry, signature)) || thumbnailsChanged;
            element = current;
        }
        const expectedCurrent = preview.children.item(index);
        if (expectedCurrent !== element) {
            preview.insertBefore(element, expectedCurrent);
        }
    }
    for (const [id, element] of existing.entries()) {
        if (!retainedIds.has(id)) {
            element.remove();
            detached.set(id, element);
        } else {
            detached.delete(id);
        }
    }
    return { thumbnailsChanged };
};

export { reconcileAttachmentPreview };
export type { AttachmentPreviewEntry, AttachmentPreviewReconciliation };
