/* SoAI - Shared AI setup attention service protocols [frontend/assets/ts/core/aisetup/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const AI_SETUP_ATTENTION_SERVICE_ID = 'features.wizard.aiSetupAttention';

interface AiSetupAttentionLifecycleContract {
    initialize(): void;
    dispose(): void;
}

export { AI_SETUP_ATTENTION_SERVICE_ID };
export type { AiSetupAttentionLifecycleContract };
