/* SoAI - Attachment draft presentation ports [frontend/assets/ts/features/attachmodal/draftContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

interface AttachDraftDisplayRecord {
    readonly id: string;
    readonly name: string;
    readonly parseStatus: 'processing' | 'ready' | 'error';
    readonly parseError?: string;
    readonly missingCapabilities?: readonly string[];
    readonly mimeType?: string;
    readonly type: string;
    readonly sizeBytes?: number;
    readonly size: number;
    readonly isImage: boolean;
}
interface AttachDraftEntry {
    readonly attachment: AttachDraftDisplayRecord;
    readonly iconName: IconName;
    readonly previewUrl: string | null;
}
interface AttachDraftPresentation {
    status(attachment: AttachDraftDisplayRecord): { label: string; className: string };
    createVisual(documentRef: Document, entry: AttachDraftEntry): HTMLElement;
    preserveVisuals(current: HTMLElement, next: HTMLElement): boolean;
    hasThumbnails(element: HTMLElement): boolean;
    prepareThumbnails(element: HTMLElement): void;
    afterRender(entries: readonly AttachDraftEntry[]): void;
}
interface AttachDraftConsumer {
    snapshot(): readonly AttachDraftEntry[];
    subscribe(handler: () => void): () => void;
    remove(id: string): Promise<void>;
    run(task: () => Promise<void>): void;
}

export type { AttachDraftConsumer, AttachDraftDisplayRecord, AttachDraftEntry, AttachDraftPresentation };
