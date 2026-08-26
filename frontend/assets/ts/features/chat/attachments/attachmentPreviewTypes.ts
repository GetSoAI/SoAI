/* SoAI - Chat attachment preview type contracts [frontend/assets/ts/features/chat/attachments/attachmentPreviewTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type SoaiFilePreviewType = 'text' | 'image' | 'audio' | 'video' | 'document' | 'file';
type SoaiPathPreviewType = SoaiFilePreviewType | 'folder';

const SOAI_FILE_PREVIEW_TYPES: ReadonlySet<string> = new Set(['text', 'image', 'audio', 'video', 'document', 'file']);

const isSoaiFilePreviewType = (value: string): value is SoaiFilePreviewType => SOAI_FILE_PREVIEW_TYPES.has(value);

const isSoaiPathPreviewType = (value: string): value is SoaiPathPreviewType => value === 'folder' || isSoaiFilePreviewType(value);

export { isSoaiFilePreviewType, isSoaiPathPreviewType };
export type { SoaiFilePreviewType, SoaiPathPreviewType };
