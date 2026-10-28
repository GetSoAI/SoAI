/* SoAI - Skill library and selection payload validation [frontend/assets/ts/core/api/contracts/webuiSkillContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SkillBatchImportReceipt, SkillDetails, SkillImportReceipt, SkillLibrary, SkillResource, SkillSelection, SkillSummary } from '@core/api/contracts/webuiSkillContractTypes.ts';
import { requireRecord, assertExactRecordKeys, readRequiredJsonObjectArrayValue } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredEpochMsValue, readRequiredNonEmptyStringValue, readRequiredStringValue, readNullableTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const requireSkillId = (value: JsonValue | undefined): string => {
    const identity = readRequiredNonEmptyStringValue(value, 'Skill identity');
    if (!/^skill_[0-9a-f]{32}$/u.test(identity)) throw new TypeError('Skill identity is invalid.');
    return identity;
};

const requireSkillRevision = (value: JsonValue | undefined): number => {
    const revision = readRequiredNonNegativeIntegerValue(value, 'Skill revision');
    if (!Number.isSafeInteger(revision)) throw new TypeError('Skill revision is outside the supported range.');
    return revision;
};

const requireSkillIds = (value: JsonValue | undefined): string[] => {
    if (!Array.isArray(value)) throw new TypeError('Skill selection must be an array.');
    const identities = value.map(requireSkillId);
    if (new Set(identities).size !== identities.length) throw new TypeError('Skill selection contains duplicate identities.');
    return identities.sort((left, right) => (left < right ? -1 : left > right ? 1 : 0));
};

const requireDigest = (value: JsonValue | undefined): string => {
    const digest = readRequiredNonEmptyStringValue(value, 'Skill digest');
    if (!/^[0-9a-f]{64}$/u.test(digest)) throw new TypeError('Skill digest is invalid.');
    return digest;
};

const decodeSkillSummary = (value: JsonValue): SkillSummary => {
    const record = requireRecord(value, 'Skill');
    return {
        skillId: requireSkillId(record['skill_id']),
        name: readRequiredNonEmptyStringValue(record['name'], 'Skill name'),
        description: readRequiredNonEmptyStringValue(record['description'], 'Skill description'),
        disableModelInvocation: readRequiredBooleanValue(record['disable_model_invocation'], 'Skill automatic invocation'),
        userInvocable: readRequiredBooleanValue(record['user_invocable'], 'Skill direct invocation'),
        packageDigest: requireDigest(record['package_digest']),
        sizeBytes: readRequiredNonNegativeIntegerValue(record['size_bytes'], 'Skill size'),
        createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], 'Skill creation time')
    };
};

const decodeSkillLibrary = (value: JsonValue): SkillLibrary => {
    const record = requireRecord(value, 'Skill library');
    assertExactRecordKeys(record, ['revision', 'retained_bytes', 'skills', 'limits'], 'Skill library');
    const limits = requireRecord(record['limits'], 'Skill library limits');
    const skills = readRequiredJsonObjectArrayValue(record['skills'], 'Skills').map(decodeSkillSummary);
    if (new Set(skills.map((skill) => skill.skillId)).size !== skills.length || new Set(skills.map((skill) => skill.name)).size !== skills.length) throw new TypeError('Skill library contains duplicate identities.');
    return {
        revision: requireSkillRevision(record['revision']),
        retainedBytes: readRequiredNonNegativeIntegerValue(record['retained_bytes'], 'Retained skill storage'),
        skills,
        limits: {
            installedSkills: readRequiredNonNegativeIntegerValue(limits['installed_skills'], 'Installed skill limit'),
            retainedBytes: readRequiredNonNegativeIntegerValue(limits['retained_bytes'], 'Retained skill limit'),
            uploadBytes: readRequiredNonNegativeIntegerValue(limits['upload_bytes'], 'Skill upload limit'),
            packageBytes: readRequiredNonNegativeIntegerValue(limits['package_bytes'], 'Skill package limit')
        }
    };
};

const decodeSkillSelection = (value: JsonValue): SkillSelection => {
    const record = requireRecord(value, 'Skill selection');
    assertExactRecordKeys(record, ['conv_id', 'revision', 'skill_ids'], 'Skill selection');
    return { conversationId: readRequiredNonEmptyStringValue(record['conv_id'], 'Skill conversation'), revision: requireSkillRevision(record['revision']), skillIds: requireSkillIds(record['skill_ids']) };
};

const decodeSkillImportReceipt = (value: JsonValue): SkillImportReceipt => {
    const record = requireRecord(value, 'Skill import receipt');
    assertExactRecordKeys(record, ['skill_id', 'upload_id', 'upload_digest', 'package_digest', 'name', 'removed'], 'Skill import receipt');
    return {
        skillId: requireSkillId(record['skill_id']),
        uploadId: readRequiredNonEmptyStringValue(record['upload_id'], 'Skill upload identity'),
        uploadDigest: requireDigest(record['upload_digest']),
        packageDigest: requireDigest(record['package_digest']),
        name: readRequiredNonEmptyStringValue(record['name'], 'Skill name'),
        removed: readRequiredBooleanValue(record['removed'], 'Removed skill')
    };
};

const decodeSkillResource = (value: JsonValue): SkillResource => {
    const record = requireRecord(value, 'Skill resource');
    return { path: readRequiredNonEmptyStringValue(record['path'], 'Skill resource path'), isDirectory: readRequiredBooleanValue(record['is_directory'], 'Skill directory'), sizeBytes: readRequiredNonNegativeIntegerValue(record['size_bytes'], 'Skill resource size'), digest: requireDigest(record['digest']) };
};

const decodeSkillBatchImportReceipt = (value: JsonValue): SkillBatchImportReceipt => {
    const record = requireRecord(value, 'Skill collection receipt');
    assertExactRecordKeys(record, ['upload_id', 'upload_digest', 'members'], 'Skill collection receipt');
    const uploadId = readRequiredNonEmptyStringValue(record['upload_id'], 'Skill collection upload identity');
    const uploadDigest = requireDigest(record['upload_digest']);
    const members = readRequiredJsonObjectArrayValue(record['members'], 'Skill collection members').map((member) => {
        assertExactRecordKeys(member, ['skill_id', 'upload_id', 'upload_digest', 'package_digest', 'name', 'removed', 'source_root'], 'Skill collection member');
        const sourceRoot = member['source_root'];
        const receipt = { ...member };
        delete receipt['source_root'];
        const decoded = decodeSkillImportReceipt(receipt);
        if (decoded.uploadDigest !== uploadDigest) throw new TypeError('Skill collection member belongs to another upload.');
        return { ...decoded, sourceRoot: readRequiredStringValue(sourceRoot, 'Skill source root') };
    });
    if (members.length === 0 || new Set(members.map((member) => member.skillId)).size !== members.length || new Set(members.map((member) => member.sourceRoot)).size !== members.length) throw new TypeError('Skill collection receipt has missing or duplicate members.');
    return { uploadId, uploadDigest, members };
};

const decodeSkillDetails = (value: JsonValue): SkillDetails => {
    const record = requireRecord(value, 'Skill details');
    const manifest = requireRecord(record['manifest'], 'Skill manifest');
    return {
        skillId: requireSkillId(record['skill_id']),
        name: readRequiredNonEmptyStringValue(record['name'], 'Skill name'),
        description: readRequiredNonEmptyStringValue(record['description'], 'Skill description'),
        packageDigest: requireDigest(record['package_digest']),
        source: readRequiredStringValue(manifest['source'], 'Skill manifest source'),
        compatibility: readNullableTrimmedStringValue(manifest['compatibility'], 'Skill compatibility'),
        resources: readRequiredJsonObjectArrayValue(record['resources'], 'Skill resources').map(decodeSkillResource)
    };
};

const decodeSkillRemoval = (value: JsonValue): { removed: boolean; revision: number } => {
    const record = requireRecord(value, 'Skill removal');
    assertExactRecordKeys(record, ['removed', 'revision'], 'Skill removal');
    return { removed: readRequiredBooleanValue(record['removed'], 'Skill removal result'), revision: requireSkillRevision(record['revision']) };
};

export { decodeSkillBatchImportReceipt, decodeSkillDetails, decodeSkillImportReceipt, decodeSkillLibrary, decodeSkillRemoval, decodeSkillSelection, requireSkillId, requireSkillIds, requireSkillRevision };
