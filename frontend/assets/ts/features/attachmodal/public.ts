/* SoAI - Reusable attachment dialog public surface [frontend/assets/ts/features/attachmodal/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { AttachModalController } from '@features/attachmodal/AttachModalController.ts';
export { createAttachModalDefinition } from '@features/attachmodal/definition.ts';
export { ATTACH_MODAL_ID } from '@features/attachmodal/constants.ts';
export { ATTACH_MODAL_ACTIONS, isAttachModalAction } from '@features/attachmodal/actions.ts';
export type { AttachModalAction } from '@features/attachmodal/actions.ts';
export { ATTACH_MODAL_TABS } from '@features/attachmodal/contracts.ts';
export type { AttachBrowseElements, AttachDraftListElements, AttachKnowledgeElements, AttachLinkElements, AttachModalConsumer, AttachModalContent, AttachModalOpenOptions, AttachModalPolicy, AttachModalSessionContext, AttachModalTab, AttachUploadElements } from '@features/attachmodal/contracts.ts';
export { createCameraCaptureRuntime } from '@features/attachmodal/cameraCapture.ts';
export type { AttachCameraElements, AttachCameraRuntime } from '@features/attachmodal/cameraCapture.ts';
export { createAttachBrowseElements, createAttachCameraElements, createAttachDraftListElements, createAttachKnowledgeElements, createAttachLinkElements, createAttachUploadElements, requireAttachModalButton, requireAttachModalChild } from '@features/attachmodal/elements.ts';
export { renderBrowseMessage, setBrowseFooterButtonState } from '@features/attachmodal/browseState.ts';
export { renderBrowseResultsTable } from '@features/attachmodal/browseTable.ts';

export { AttachDraftListController } from '@features/attachmodal/AttachDraftListController.ts';
export type { AttachDraftConsumer, AttachDraftDisplayRecord, AttachDraftEntry, AttachDraftPresentation } from '@features/attachmodal/draftContracts.ts';
export { createDraftAttachmentListRow, reconcileDraftAttachmentListRows } from '@features/attachmodal/draftRows.ts';

export { AttachUploadController, openAttachFilePicker } from '@features/attachmodal/AttachUploadController.ts';
export type { AttachUploadConsumer } from '@features/attachmodal/AttachUploadController.ts';
export { AttachLinkController } from '@features/attachmodal/AttachLinkController.ts';
export type { AttachLinkConsumer } from '@features/attachmodal/AttachLinkController.ts';

export { AttachBrowseController } from '@features/attachmodal/AttachBrowseController.ts';
export type { AttachBrowseConsumer, AttachBrowseSearchOutcome } from '@features/attachmodal/browseContracts.ts';
export type { AttachBrowseResult, AttachBrowseSortColumn, AttachBrowseSortState } from '@features/attachmodal/browseRecords.ts';
export { sortBrowseResults } from '@features/attachmodal/browseSorting.ts';
