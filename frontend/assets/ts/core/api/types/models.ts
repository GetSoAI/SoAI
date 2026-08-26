/* SoAI - Shared frontend API types models [frontend/assets/ts/core/api/types/models.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ModelDownloadParameters {
    universalId?: string;
    plugin?: string;
    modelId?: string;
    quantization?: string;
}

interface GetVariantsOptions {
    includeSpeedTests?: boolean;
}

export type { ModelDownloadParameters, GetVariantsOptions };
