/* SoAI - Voice call runtime asset URLs [frontend/assets/ts/app/entrypoints/voicecall/runtimeAssets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import captureWorkletUrl from '@app/entrypoints/voicecall/voiceCallCaptureProcessor.ts?worker&url';
import wavEncoderWorkerUrl from '@app/entrypoints/voicecall/voiceCallWavEncoderWorker.ts?worker&url';
import type { VoiceCallRuntimeAssets } from '@core/media/voiceCallRuntimeAssets.ts';

const voiceCallRuntimeAssets: VoiceCallRuntimeAssets = {
    captureWorkletUrl,
    wavEncoderWorkerUrl
};

export { voiceCallRuntimeAssets };
