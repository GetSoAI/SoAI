/* SoAI - SoAIBench publication receipt contract [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchPublicationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchPublicationReceipt } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';

const readPublicationState = (value: string): GpuSoAIBenchPublicationReceipt['state'] => {
    if (value === 'published' || value === 'already_published' || value === 'held_for_review') return value;
    throw new TypeError('SoAI Bench publication receipt.state is invalid');
};

const readPublicationValidation = (value: string): GpuSoAIBenchPublicationReceipt['validation'] => {
    if (value === 'validated' || value === 'flagged') return value;
    throw new TypeError('SoAI Bench publication receipt.validation is invalid');
};

const decodeGpuSoAIBenchPublicationReceipt = (value: ApiResponsePayload): GpuSoAIBenchPublicationReceipt => {
    const record = requireRecord(value, 'SoAI Bench publication receipt');
    assertExactRecordKeys(record, ['state', 'submission_id', 'public_url', 'score_version', 'overall_score', 'validation', 'duplicate'], 'SoAI Bench publication receipt');
    const state = readPublicationState(readRequiredTrimmedStringValue(record['state'], 'SoAI Bench publication receipt.state'));
    const submissionId = readRequiredTrimmedStringValue(record['submission_id'], 'SoAI Bench publication receipt.submission_id');
    const publicUrl = readRequiredTrimmedStringValue(record['public_url'], 'SoAI Bench publication receipt.public_url');
    const scoreVersion = readRequiredTrimmedStringValue(record['score_version'], 'SoAI Bench publication receipt.score_version');
    const validation = readPublicationValidation(readRequiredTrimmedStringValue(record['validation'], 'SoAI Bench publication receipt.validation'));
    const duplicate = readRequiredBooleanValue(record['duplicate'], 'SoAI Bench publication receipt.duplicate');
    const overallScore = readRequiredFiniteNumberValue(record['overall_score'], 'SoAI Bench publication receipt.overall_score');
    if ((state === 'published' && duplicate) || (state === 'held_for_review') !== (validation === 'flagged')) throw new TypeError('SoAI Bench publication receipt.state is inconsistent');
    if (!/^sb_[A-Za-z0-9_-]{22}$/.test(submissionId) || publicUrl !== `https://soai.to/soaibench-leaderboard/results/${submissionId}` || scoreVersion !== 'soaibench-v2' || !Number.isSafeInteger(overallScore) || overallScore < 0) throw new TypeError('SoAI Bench publication receipt is inconsistent');
    return { state, submissionId, publicUrl, scoreVersion, overallScore, validation, duplicate };
};

const decodeGpuSoAIBenchPublicationPreview = (value: ApiResponsePayload): string => {
    const record = requireRecord(value, 'SoAI Bench publication preview');
    assertExactRecordKeys(record, ['projection_json'], 'SoAI Bench publication preview');
    return readRequiredTrimmedStringValue(record['projection_json'], 'SoAI Bench publication preview.projection_json');
};

export { decodeGpuSoAIBenchPublicationReceipt, decodeGpuSoAIBenchPublicationPreview };
