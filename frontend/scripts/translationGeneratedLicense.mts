/* SoAI - Generated translation header and license metadata [frontend/scripts/translationGeneratedLicense.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import fs from 'node:fs/promises';
import path from 'node:path';
import { isObject, type JsonValue } from './translationKeyCatalog.mts';

const BASE_GENERATED_LICENSE = 'LicenseRef-SoAI-Source-1.0';

export const buildGeneratedTranslationHeader = (relativePath: string, license: string, privateOutput: boolean, description: string): string => {
    const productName = privateOutput ? 'SoAI OS' : 'SoAI';
    const scopeDescription = privateOutput ? 'Private frontend' : 'Frontend core';
    return `/* ${productName} - ${scopeDescription} ${description} [${relativePath}] */\n// SPDX-License-Identifier: ${license}`;
};

export const resolveGeneratedTranslationLicense = async (soaiRoot: string, privateOutput: boolean): Promise<string> => {
    if (!privateOutput) return BASE_GENERATED_LICENSE;
    const metadataPath = path.join(soaiRoot, 'soai_os', 'licenses', 'frontend-generated-spdx.json');
    const value: JsonValue = JSON.parse(await fs.readFile(metadataPath, 'utf8'));
    if (!isObject(value) || Object.keys(value).length !== 2 || value['schema_version'] !== 1) {
        throw new Error('Private generated SPDX metadata must match schema V1');
    }
    const license = value['license'];
    if (typeof license !== 'string' || !/^LicenseRef-[A-Za-z0-9.-]+$/.test(license)) {
        throw new Error('Private generated SPDX license is invalid');
    }
    return license;
};
