/* SoAI - Speech setup presentation contracts [frontend/assets/ts/core/speechsetup/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelData } from '@core/types/modelTypes.ts';

interface SpeechSetupCandidate {
    pluginName: string;
    displayName: string;
    state: string;
    backendInstallable: boolean;
    modelsDownloadable: boolean;
    enableRequired: boolean;
}

type SpeechSetupReason = 'no_stt_plugin' | 'no_tts_plugin' | 'backend_not_installed' | 'plugin_disabled' | 'no_model_installed' | 'model_disabled' | 'configured_model_missing' | 'not_local' | 'translation_unsupported' | 'unsupported_option';
type SpeechSetupScope = 'media' | 'voice' | 'synthesis';
type SpeechSetupNotePlacement = 'inline' | 'composer' | 'labelled' | 'settings';

interface SpeechSetupNoteOptions {
    reason?: SpeechSetupReason;
    persisted?: boolean;
    selector?: string;
    modelLabel?: string;
    candidates?: readonly SpeechSetupCandidate[];
    scope?: SpeechSetupScope;
    placement?: SpeechSetupNotePlacement;
    addModelVisible?: boolean;
}

interface SpeechSetupSnapshot {
    fresh: boolean;
    models: readonly ModelData[];
    candidates: readonly SpeechSetupCandidate[];
    reason: SpeechSetupReason | null;
}

interface SpeechSetupProtocol {
    snapshot(scope?: SpeechSetupScope): SpeechSetupSnapshot;
    ensureReady(): Promise<void>;
    subscribe(listener: () => void): () => void;
}

export type { SpeechSetupCandidate, SpeechSetupNoteOptions, SpeechSetupNotePlacement, SpeechSetupProtocol, SpeechSetupReason, SpeechSetupScope, SpeechSetupSnapshot };
