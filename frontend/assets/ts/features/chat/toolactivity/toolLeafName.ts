/* SoAI - Canonical tool name normalization for chat tool activity [frontend/assets/ts/features/chat/toolactivity/toolLeafName.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const normalizeToolLeafName = (toolName: string): string => {
    return toolName.split('.').slice(-1)[0]?.trim().toLowerCase().replace(/\s+/g, '_') ?? '';
};

export { normalizeToolLeafName };
