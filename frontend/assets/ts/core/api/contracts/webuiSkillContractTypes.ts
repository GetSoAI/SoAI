/* SoAI - Owner-private skill library contracts [frontend/assets/ts/core/api/contracts/webuiSkillContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface SkillSummary {
    skillId: string;
    name: string;
    description: string;
    disableModelInvocation: boolean;
    userInvocable: boolean;
    packageDigest: string;
    sizeBytes: number;
    createdAtMs: number;
}

interface SkillLibrary {
    revision: number;
    retainedBytes: number;
    skills: SkillSummary[];
    limits: { installedSkills: number; retainedBytes: number; uploadBytes: number; packageBytes: number };
}

interface SkillSelection {
    conversationId: string;
    revision: number;
    skillIds: string[];
}

interface SkillImportReceipt {
    skillId: string;
    uploadId: string;
    uploadDigest: string;
    packageDigest: string;
    name: string;
    removed: boolean;
}

interface SkillBatchImportReceipt {
    uploadId: string;
    uploadDigest: string;
    members: Array<SkillImportReceipt & { sourceRoot: string }>;
}

interface SkillResource {
    path: string;
    isDirectory: boolean;
    sizeBytes: number;
    digest: string;
}

interface SkillDetails {
    skillId: string;
    name: string;
    description: string;
    packageDigest: string;
    source: string;
    compatibility: string | null;
    resources: SkillResource[];
}

export type { SkillBatchImportReceipt, SkillDetails, SkillImportReceipt, SkillLibrary, SkillResource, SkillSelection, SkillSummary };
