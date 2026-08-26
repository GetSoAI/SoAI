/* SoAI - Canonical chat service tier domain [frontend/assets/ts/core/chat/parameters/serviceTier.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ChatServiceTier = 'auto' | 'default' | 'flex' | 'priority';

const CHAT_SERVICE_TIERS: ReadonlyArray<ChatServiceTier> = Object.freeze(['auto', 'default', 'flex', 'priority']);
const CHAT_SERVICE_TIER_SET: ReadonlySet<string> = new Set(CHAT_SERVICE_TIERS);

const isChatServiceTier = (value: string): value is ChatServiceTier => CHAT_SERVICE_TIER_SET.has(value);

export { CHAT_SERVICE_TIERS, isChatServiceTier };
export type { ChatServiceTier };
