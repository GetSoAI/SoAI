/* SoAI - Exact governing-document response contracts [frontend/assets/ts/core/api/contracts/licensingLegalDocumentContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type LicensingLegalFlow = 'core_evaluation' | 'commercial_activation' | 'os_evaluation_conversion' | 'personal_os_activation';

interface LicensingLegalDocument {
    documentId: string;
    documentName: string;
    version: string;
    effectiveDate: string;
    fingerprint: string;
    licenseText: string;
}

interface LicensingLegalDocumentSet {
    schemaVersion: 1;
    flow: LicensingLegalFlow;
    documents: readonly LicensingLegalDocument[];
}

const stringValue = (value: JsonValue | undefined, label: string): string => {
    if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be a non-empty string.`);
    return value;
};

const decodeDocument = (value: JsonValue | undefined, index: number): LicensingLegalDocument => {
    const label = `Licensing legal document[${String(index)}]`;
    const record = requireRecord(value, label);
    assertExactRecordKeys(record, ['document_id', 'document_name', 'version', 'effective_date', 'fingerprint', 'license_text'], label);
    const documentId = stringValue(record['document_id'], `${label}.document_id`);
    const version = stringValue(record['version'], `${label}.version`);
    const effectiveDate = stringValue(record['effective_date'], `${label}.effective_date`);
    const fingerprint = stringValue(record['fingerprint'], `${label}.fingerprint`);
    if (!/^[a-z][a-z0-9_]{1,63}$/.test(documentId) || !/^[1-9][0-9]*\.[0-9]+$/.test(version) || !/^\d{4}-\d{2}-\d{2}$/.test(effectiveDate) || !/^sha256:[a-f0-9]{64}$/.test(fingerprint)) throw new TypeError(`${label} metadata is invalid.`);
    return { documentId, documentName: stringValue(record['document_name'], `${label}.document_name`), version, effectiveDate, fingerprint, licenseText: stringValue(record['license_text'], `${label}.license_text`) };
};

const decodeLicensingLegalDocumentSet = (value: ApiResponsePayload): LicensingLegalDocumentSet => {
    const record = requireRecord(value, 'Licensing legal document set');
    assertExactRecordKeys(record, ['schema_version', 'flow', 'documents'], 'Licensing legal document set');
    if (record['schema_version'] !== 1) throw new TypeError('Licensing legal document schema must be V1.');
    const flow = record['flow'];
    if (flow !== 'core_evaluation' && flow !== 'commercial_activation' && flow !== 'os_evaluation_conversion' && flow !== 'personal_os_activation') throw new TypeError('Licensing legal flow is invalid.');
    if (!Array.isArray(record['documents']) || record['documents'].length < 1) throw new TypeError('Licensing legal documents must be a non-empty array.');
    const documents = record['documents'].map(decodeDocument);
    const identities = documents.map((document) => document.documentId);
    if (identities.join('\0') !== [...new Set(identities)].sort((left, right) => left.localeCompare(right, 'en')).join('\0')) throw new TypeError('Licensing legal documents must be sorted and unique.');
    return { schemaVersion: 1, flow, documents };
};

export { decodeLicensingLegalDocumentSet };
export type { LicensingLegalDocument, LicensingLegalDocumentSet, LicensingLegalFlow };
