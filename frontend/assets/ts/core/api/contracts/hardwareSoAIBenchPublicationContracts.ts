/* SoAI - SoAIBench publication receipt contract [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchPublicationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchPublicationReceipt } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';

const readPublicationState = (value: string): GpuSoAIBenchPublicationReceipt['state'] => {
    if (value === 'published' || value === 'already_published' || value === 'held_for_review') return value;
    throw new TypeError('SoAIBench publication receipt.state is invalid');
};

const readPublicationValidation = (value: string): GpuSoAIBenchPublicationReceipt['validation'] => {
    if (value === 'validated' || value === 'flagged') return value;
    throw new TypeError('SoAIBench publication receipt.validation is invalid');
};

const decodeGpuSoAIBenchPublicationReceipt = (value: ApiResponsePayload): GpuSoAIBenchPublicationReceipt => {
    const record = requireRecord(value, 'SoAIBench publication receipt');
    assertExactRecordKeys(record, ['state', 'submission_id', 'public_url', 'score_version', 'overall_score', 'validation', 'duplicate'], 'SoAIBench publication receipt');
    const state = readPublicationState(readRequiredTrimmedStringValue(record['state'], 'SoAIBench publication receipt.state'));
    const submissionId = readRequiredTrimmedStringValue(record['submission_id'], 'SoAIBench publication receipt.submission_id');
    const publicUrl = readRequiredTrimmedStringValue(record['public_url'], 'SoAIBench publication receipt.public_url');
    const scoreVersion = readRequiredTrimmedStringValue(record['score_version'], 'SoAIBench publication receipt.score_version');
    const validation = readPublicationValidation(readRequiredTrimmedStringValue(record['validation'], 'SoAIBench publication receipt.validation'));
    const duplicate = readRequiredBooleanValue(record['duplicate'], 'SoAIBench publication receipt.duplicate');
    const overallScore = readRequiredFiniteNumberValue(record['overall_score'], 'SoAIBench publication receipt.overall_score');
    if ((state === 'published' && duplicate) || (state === 'held_for_review') !== (validation === 'flagged')) throw new TypeError('SoAIBench publication receipt.state is inconsistent');
    if (!/^sb_[A-Za-z0-9_-]{22}$/.test(submissionId) || publicUrl !== `https://soai.to/soaibench-leaderboard/results/${submissionId}` || scoreVersion !== 'soaibench-v2' || !Number.isSafeInteger(overallScore) || overallScore < 0) throw new TypeError('SoAIBench publication receipt is inconsistent');
    return { state, submissionId, publicUrl, scoreVersion, overallScore, validation, duplicate };
};

const decodeGpuSoAIBenchPublicationPreview = (value: ApiResponsePayload): string => {
    const record = requireRecord(value, 'SoAIBench publication preview');
    assertExactRecordKeys(record, ['projection_json'], 'SoAIBench publication preview');
    return readRequiredTrimmedStringValue(record['projection_json'], 'SoAIBench publication preview.projection_json');
};

export { decodeGpuSoAIBenchPublicationReceipt, decodeGpuSoAIBenchPublicationPreview };
