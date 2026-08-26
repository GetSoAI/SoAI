/* SoAI - Shared MIME type predicates [frontend/assets/ts/core/media/mimeTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isImageMimeType = (value: string): boolean => value.startsWith('image/');

export { isImageMimeType };
