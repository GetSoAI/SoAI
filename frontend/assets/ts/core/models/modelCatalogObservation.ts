/* SoAI - Meaningful shared model catalog observations [frontend/assets/ts/core/models/modelCatalogObservation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ClientDataHub, ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { stableModelFingerprint } from '@core/models/modelFingerprint.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';

interface ModelCatalogObservation {
    readonly type: 'current' | 'stale' | 'unavailable';
}

type ModelCatalogSubscriber = (listener: (observation: ModelCatalogObservation) => void) => () => void;

const readObservation = (snapshot: ResourceSnapshot): ModelCatalogObservation => ({
    type: !snapshot.hasAuthoritativeSnapshot ? 'unavailable' : snapshot.status === 'ready' && snapshot.staleSinceMonotonicMs === null ? 'current' : 'stale'
});

const observationSignature = (snapshot: ResourceSnapshot, observation: ModelCatalogObservation): string => stableJsonStringify({ type: observation.type, models: snapshot.items.map((model) => stableModelFingerprint(toJsonCompatibleValue(model))).sort((left, right) => (left < right ? -1 : left > right ? 1 : 0)) });

const subscribeModelCatalog = (source: Pick<ClientDataHub, 'snapshot' | 'subscribe'>, listener: (observation: ModelCatalogObservation) => void): (() => void) => {
    const initial = source.snapshot(MODELS);
    let signature = observationSignature(initial, readObservation(initial));
    let active = true;
    let releaseFailure: Error | null = null;
    const unsubscribe = source.subscribe(
        MODELS,
        (snapshot) => {
            if (!active) return;
            const observation = readObservation(snapshot);
            const nextSignature = observationSignature(snapshot, observation);
            if (signature === nextSignature) return;
            signature = nextSignature;
            listener(observation);
        },
        { emitInitial: false }
    );
    return (): void => {
        if (releaseFailure !== null) throw releaseFailure;
        if (!active) return;
        active = false;
        try {
            unsubscribe();
        } catch (error) {
            releaseFailure = ensureError(error);
            throw releaseFailure;
        }
    };
};

export { subscribeModelCatalog };
export type { ModelCatalogObservation, ModelCatalogSubscriber };
