/* SoAI - AudioWorklet runtime type declarations [frontend/types/audioWorklet.d.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface AudioWorkletProcessor {
    readonly port: MessagePort;
}

declare var AudioWorkletProcessor: {
    prototype: AudioWorkletProcessor;
    new (): AudioWorkletProcessor;
};

declare function registerProcessor(name: string, processorCtor: new () => AudioWorkletProcessor): void;
