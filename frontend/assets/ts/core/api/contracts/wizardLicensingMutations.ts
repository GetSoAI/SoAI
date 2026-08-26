/* SoAI - Wizard licensing mutation and document contracts [frontend/assets/ts/core/api/contracts/wizardLicensingMutations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type WizardLicensingPayloadValue = JsonValue | undefined;

interface WizardLicensingDocumentResponse {
    schemaVersion: 1;
    edition: 'soai-core' | 'soai-os';
    documentName: string;
    fingerprint: string;
    licenseText: string;
}

const requireString = (value: WizardLicensingPayloadValue, label: string): string => {
    if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be a non-empty string.`);
    return value;
};

const requireFingerprint = (value: WizardLicensingPayloadValue, label: string): string => {
    const fingerprint = requireString(value, label);
    if (!/^sha256:[a-f0-9]{64}$/.test(fingerprint)) throw new TypeError(`${label} must be a SHA-256 fingerprint.`);
    return fingerprint;
};

const decodeWizardLicensingDocument = (value: ApiResponsePayload): WizardLicensingDocumentResponse => {
    const record = requireRecord(value, 'Wizard licensing document');
    assertExactRecordKeys(record, ['schema_version', 'edition', 'document_name', 'fingerprint', 'license_text'], 'Wizard licensing document');
    if (record['schema_version'] !== 1) throw new TypeError('Wizard licensing document schema must be V1.');
    if (record['edition'] !== 'soai-core' && record['edition'] !== 'soai-os') throw new TypeError('Wizard licensing document edition is invalid.');
    return {
        schemaVersion: 1,
        edition: record['edition'],
        documentName: requireString(record['document_name'], 'Wizard licensing document.document_name'),
        fingerprint: requireFingerprint(record['fingerprint'], 'Wizard licensing document.fingerprint'),
        licenseText: requireString(record['license_text'], 'Wizard licensing document.license_text')
    };
};

export { decodeWizardLicensingDocument };
export type { WizardLicensingDocumentResponse };
