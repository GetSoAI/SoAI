/* SoAI - Chat attachment overflow modal bounded list renderer [frontend/assets/ts/features/chat/message/attachmentoverflowmodal/listRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BoundedCollectionRenderer } from '@core/data/boundedcollectionrenderer/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { AttachmentOverflowModalShell } from '@features/chat/message/attachmentoverflowmodal/view.ts';
import { renderAttachmentOverflowItem } from '@features/chat/message/attachmentoverflowmodal/rendering.ts';
import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';

class AttachmentOverflowListRenderer {
    #renderer: BoundedCollectionRenderer<AttachmentOverflowRecord> | null = null;
    #shell: AttachmentOverflowModalShell | null = null;

    update(inputArguments: { shell: AttachmentOverflowModalShell; records: readonly AttachmentOverflowRecord[] }): void {
        const itemLookup: Map<string, AttachmentOverflowRecord> = new Map();
        const ids: string[] = [];
        for (const record of inputArguments.records) {
            ids.push(record.id);
            itemLookup.set(record.id, record);
        }
        this.#ensureRenderer(inputArguments.shell).update({ ids, lookup: itemLookup });
    }

    dispose(): void {
        this.#renderer?.dispose();
        this.#renderer = null;
        this.#shell = null;
    }

    #ensureRenderer(shell: AttachmentOverflowModalShell): BoundedCollectionRenderer<AttachmentOverflowRecord> {
        if (this.#renderer !== null && this.#shell === shell) {
            return this.#renderer;
        }
        this.#renderer?.dispose();
        this.#shell = shell;
        this.#renderer = new BoundedCollectionRenderer<AttachmentOverflowRecord>({
            resolveContainer: () => shell.list,
            resolveEmptyState: () => shell.empty,
            renderItem: (item) => renderAttachmentOverflowItem(item),
            resolveItemIdentifier: (element) => element.dataset['collectionId'] ?? null,
            loadingLabel: () => i18n.t('chat.attachments.modal.loadingMore')
        });
        return this.#renderer;
    }
}

export { AttachmentOverflowListRenderer };
