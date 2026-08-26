/* SoAI - Cross-feature OpenAI capability descriptor protocols [frontend/assets/ts/core/openai/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface CapabilityDescriptor {
    id: string;
    label: string;
    className: string;
    title?: string;
}

export type { CapabilityDescriptor };
