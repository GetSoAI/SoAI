/* SoAI - Conversation skill draft and revision conflict ownership [frontend/assets/ts/features/chat/conversationsettings/skills/selectionDraft.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SkillLibrary, SkillSelection } from '@core/api/contracts/webuiSkillContractTypes.ts';
import { requireSkillIds } from '@core/api/contracts/webuiSkillContracts.ts';
import { arraysEqual } from '@core/primitives/equality.ts';

interface SkillSaveIntent {
    conversationId: string;
    revision: number;
    skillIds: string[];
}

class SkillSelectionDraft {
    #baseline: SkillSelection | null = null;
    #latest: SkillSelection | null = null;
    #working: string[] = [];
    #library: SkillLibrary | null = null;
    #fresh = false;

    get baseline(): SkillSelection | null {
        return this.#baseline;
    }
    get selected(): readonly string[] {
        return this.#working;
    }
    get dirty(): boolean {
        return this.#baseline !== null && !arraysEqual(this.#working, this.#baseline.skillIds);
    }
    get conflicted(): boolean {
        return this.#latest !== null && this.#baseline !== null && this.#latest.revision > this.#baseline.revision;
    }
    get fresh(): boolean {
        return this.#fresh;
    }
    get valid(): boolean {
        return this.#baseline !== null && this.#library !== null && this.#fresh && !this.conflicted && this.#working.length <= this.#library.limits.installedSkills && this.#working.every((identity) => this.#library?.skills.some((skill) => skill.skillId === identity && (!skill.disableModelInvocation || skill.userInvocable)));
    }

    reset(): void {
        this.#baseline = null;
        this.#latest = null;
        this.#working = [];
        this.#library = null;
        this.#fresh = false;
    }

    setFresh(fresh: boolean): void {
        this.#fresh = fresh;
    }

    receiveLibrary(library: SkillLibrary): void {
        if (this.#library && library.revision < this.#library.revision) return;
        this.#library = library;
    }

    receiveSelection(selection: SkillSelection): void {
        if (this.#baseline && selection.conversationId !== this.#baseline.conversationId) throw new Error('Skill selection belongs to another conversation.');
        if (this.#latest && selection.revision < this.#latest.revision) return;
        if (this.#latest && selection.revision === this.#latest.revision && !arraysEqual(selection.skillIds, this.#latest.skillIds)) throw new Error('Skill selection changed without advancing its revision.');
        const wasDirty = this.dirty;
        this.#latest = { ...selection, skillIds: [...selection.skillIds] };
        if (!wasDirty) {
            this.#baseline = this.#latest;
            this.#working = [...selection.skillIds];
        }
    }

    stage(identities: string[]): void {
        if (this.#baseline === null || !this.#fresh) throw new Error('Skill selection is not ready for editing.');
        this.#working = requireSkillIds(identities);
    }

    reviewLatest(keepDraft: boolean): void {
        if (!this.#latest || !this.#fresh) throw new Error('Current skill selection must be loaded before reviewing a conflict.');
        this.#baseline = this.#latest;
        if (!keepDraft) this.#working = [...this.#latest.skillIds];
    }

    capture(): SkillSaveIntent {
        if (!this.valid || !this.#baseline) throw new Error('Skill selection is not ready to save.');
        return { conversationId: this.#baseline.conversationId, revision: this.#baseline.revision, skillIds: [...this.#working] };
    }

    acceptSave(intent: SkillSaveIntent, selection: SkillSelection): void {
        if (selection.conversationId !== intent.conversationId || selection.revision < intent.revision || !arraysEqual(selection.skillIds, intent.skillIds)) throw new Error('Saved skill selection differs from the accepted intent.');
        if (this.#baseline?.conversationId !== intent.conversationId) return;
        const unchangedIntent = arraysEqual(this.#working, intent.skillIds);
        this.#baseline = { ...selection, skillIds: [...selection.skillIds] };
        if (this.#latest === null || this.#latest.revision <= selection.revision) this.#latest = this.#baseline;
        if (unchangedIntent && this.#latest.revision === selection.revision) this.#working = [...selection.skillIds];
        else if (unchangedIntent) {
            this.#baseline = this.#latest;
            this.#working = [...this.#latest.skillIds];
        }
    }
}

export { SkillSelectionDraft };
export type { SkillSaveIntent };
