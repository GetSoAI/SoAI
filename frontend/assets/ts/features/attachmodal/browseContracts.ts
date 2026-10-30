/* SoAI - Attachment browser acquisition and operation ports [frontend/assets/ts/features/attachmodal/browseContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AttachmentAcquisitionScope } from '@core/attachments/protocols.ts';
import type { AttachBrowseResult } from '@features/attachmodal/browseRecords.ts';

type AttachBrowseSearchOutcome<TResult> = { type: 'ready'; results: TResult[] } | { type: 'no-owner' } | { type: 'superseded'; refresh: boolean };
interface AttachBrowseConsumer<TResult extends AttachBrowseResult> {
    hasOwner(): boolean;
    captureScope(): AttachmentAcquisitionScope;
    captureSearch(): { search(query: string, signal: AbortSignal): Promise<AttachBrowseSearchOutcome<TResult>> };
    activateWorkspace(): void;
    deactivateWorkspace(): void;
    openWorkspacePathPicker(): Promise<void>;
    preview(result: TResult, isCurrent: () => boolean): Promise<void>;
    attach(result: TResult, isCurrent: () => boolean): Promise<boolean>;
    abortActions(): void;
    run(operation: string, task: () => Promise<void> | void): void;
}

export type { AttachBrowseConsumer, AttachBrowseSearchOutcome };
