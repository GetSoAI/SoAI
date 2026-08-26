/* SoAI - Chat feature timeline sequence index validation [frontend/assets/ts/features/chat/assistanteventtimeline/timelineSequenceIndexValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const canAttachSequenceIndexOwner = (sequenceOwnerByIndex: Map<number, string>, sequenceIndex: number, ownerId: string): boolean => {
    const existingSequenceOwner = sequenceOwnerByIndex.get(sequenceIndex);
    if (existingSequenceOwner !== undefined && existingSequenceOwner !== ownerId) {
        return false;
    }
    return existingSequenceOwner !== undefined || sequenceIndex === sequenceOwnerByIndex.size;
};

const validateSequenceIndexOwner = (sequenceOwnerByIndex: Map<number, string>, sequenceIndex: number, ownerId: string, duplicateOwnerError: string, contiguousSequenceError: string): void => {
    const existingSequenceOwner = sequenceOwnerByIndex.get(sequenceIndex);
    if (existingSequenceOwner !== undefined && existingSequenceOwner !== ownerId) {
        throw new Error(duplicateOwnerError);
    }
    if (!canAttachSequenceIndexOwner(sequenceOwnerByIndex, sequenceIndex, ownerId)) {
        throw new Error(contiguousSequenceError);
    }
    if (existingSequenceOwner === undefined) {
        sequenceOwnerByIndex.set(sequenceIndex, ownerId);
    }
};

const validateSparseSequenceIndexOwner = (sequenceOwnerByIndex: Map<number, string>, sequenceIndex: number, ownerId: string, duplicateOwnerError: string): void => {
    const existingSequenceOwner = sequenceOwnerByIndex.get(sequenceIndex);
    if (existingSequenceOwner !== undefined && existingSequenceOwner !== ownerId) {
        throw new Error(duplicateOwnerError);
    }
    if (existingSequenceOwner === undefined) {
        sequenceOwnerByIndex.set(sequenceIndex, ownerId);
    }
};

export { canAttachSequenceIndexOwner, validateSequenceIndexOwner, validateSparseSequenceIndexOwner };
