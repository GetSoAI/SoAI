/* SoAI - Indicators feature rendering [frontend/assets/ts/features/indicators/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatEpochMsTimeSecondOrEmpty } from '@core/primitives/dateTime.ts';
import { isArray, isBoolean, isFiniteNumber, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { BundleInfo, TelemetryEvent, TelemetryMetric, LiveStatusOverlayNodes, LogLevel } from '@features/indicators/contracts.ts';
import { LIVE_STATUS_OVERLAY_ELEMENT_ID, LIVE_STATUS_OVERLAY_MAX_BUNDLES } from '@features/indicators/constants.ts';
import { countPendingBundleResources } from '@features/indicators/mappers.ts';

type ErrorReporter = (message: string, error: Error, level?: LogLevel) => void;

interface TelemetrySnapshot {
    queueDepth?: number | null | undefined;
    bundles?: BundleInfo[] | undefined;
}

const createValueElement = (className: string, role: string | null, text: string): HTMLElement => {
    const value = dom.create('span', { className, textContent: text });
    if (role) {
        dom.setData(value, 'role', role);
    }
    return value;
};

const createLabelElement = (text: string): HTMLElement => {
    return dom.create('span', {
        className: 'live-status-overlay-label',
        textContent: text
    });
};

const createOverlayElements = (): LiveStatusOverlayNodes => {
    const container = dom.create('div', {
        id: LIVE_STATUS_OVERLAY_ELEMENT_ID,
        className: 'live-status-overlay'
    });

    const streamSection = dom.create('div', { className: 'live-status-overlay-section' });
    const statusValue = createValueElement('live-status-overlay-value live-status-overlay-status', 'status', i18n.t('liveStatusOverlay.values.pending'));
    dom.appendChild(streamSection, [createLabelElement(i18n.t('liveStatusOverlay.labels.stream')), statusValue]);

    const latencySection = dom.create('div', { className: 'live-status-overlay-section' });
    const latencyValue = createValueElement('live-status-overlay-value', 'latency', '–');
    dom.appendChild(latencySection, [createLabelElement(i18n.t('liveStatusOverlay.labels.latency')), latencyValue]);

    const queueSection = dom.create('div', { className: 'live-status-overlay-section' });
    const queueValue = createValueElement('live-status-overlay-value', 'queue', '–');
    dom.appendChild(queueSection, [createLabelElement(i18n.t('liveStatusOverlay.labels.queue')), queueValue]);

    const eventSection = dom.create('div', { className: 'live-status-overlay-section live-status-overlay-section--event' });
    const eventValue = createValueElement('live-status-overlay-value live-status-overlay-event', 'event', '–');
    dom.appendChild(eventSection, [createLabelElement(i18n.t('liveStatusOverlay.labels.lastEvent')), eventValue]);

    const bundleSection = dom.create('div', { className: 'live-status-overlay-section live-status-overlay-section--bundles' });
    const bundleLabel = createLabelElement(i18n.t('liveStatusOverlay.labels.bundles'));
    const bundleList = dom.create('div', { className: 'live-status-overlay-bundle-list' });
    dom.setData(bundleList, 'role', 'bundles');
    dom.appendChild(bundleSection, [bundleLabel, bundleList]);

    [streamSection, latencySection, queueSection, eventSection, bundleSection].forEach((section) => {
        dom.appendChild(container, section);
    });

    return {
        container,
        statusElement: statusValue,
        latencyElement: latencyValue,
        queueElement: queueValue,
        eventElement: eventValue,
        bundleContainer: bundleList
    };
};

const setConnectionStatus = (statusElement: HTMLElement | null, metric: TelemetryMetric | null, onInvalid: ErrorReporter): void => {
    if (!statusElement) {
        return;
    }

    if (!metric || !metric.value) {
        statusElement.textContent = i18n.t('liveStatusOverlay.values.pending');
        statusElement.classList.remove('live-status-overlay-status--connected', 'live-status-overlay-status--disconnected');
        return;
    }

    const metricValue = metric.value;
    if (!isObject(metricValue)) {
        onInvalid('Telemetry connection metric must be an object', new TypeError('Telemetry connection metric must be an object'));
        return;
    }

    if (!('connected' in metricValue)) {
        onInvalid('Telemetry connection metric connected must be a boolean', new TypeError('Telemetry connection metric connected must be a boolean'));
        return;
    }
    const connectedValue = metricValue['connected'];
    if (!isBoolean(connectedValue)) {
        onInvalid('Telemetry connection metric connected must be a boolean', new TypeError('Telemetry connection metric connected must be a boolean'));
        return;
    }

    statusElement.textContent = connectedValue ? i18n.t('liveStatusOverlay.values.connected') : i18n.t('liveStatusOverlay.values.disconnected');
    statusElement.classList.toggle('live-status-overlay-status--connected', connectedValue);
    statusElement.classList.toggle('live-status-overlay-status--disconnected', !connectedValue);
};

const setLatencyValue = (latencyElement: HTMLElement | null, metric: TelemetryMetric | null): void => {
    if (!latencyElement) {
        return;
    }

    const metricValue = metric ? metric.value : null;
    if (!isFiniteNumber(metricValue)) {
        latencyElement.textContent = '–';
        return;
    }

    latencyElement.textContent = i18n.t('liveStatusOverlay.values.latencyMs', { value: Math.max(0, Math.round(metricValue)) });
};

const setQueueValue = (queueElement: HTMLElement | null, metric: TelemetryMetric | null): void => {
    if (!queueElement) {
        return;
    }

    if (!metric || isNullOrUndefined(metric.value)) {
        queueElement.textContent = '–';
        return;
    }

    queueElement.textContent = String(metric.value);
};

const setLastEvent = (eventElement: HTMLElement | null, event: TelemetryEvent | null): void => {
    if (!eventElement) {
        return;
    }

    if (!event) {
        eventElement.textContent = i18n.t('liveStatusOverlay.values.noEvent');
        return;
    }

    const stage = event.stage ?? '';
    const timestamp = event.timestamp ? formatEpochMsTimeSecondOrEmpty(event.timestamp) : '';
    eventElement.textContent = stage ? (timestamp ? `${stage} · ${timestamp}` : stage) : timestamp || i18n.t('liveStatusOverlay.values.noEvent');
};

const renderSnapshot = (bundleContainer: HTMLElement | null, snapshot: TelemetrySnapshot): void => {
    if (!bundleContainer) {
        return;
    }

    const doc = getDocument();
    bundleContainer.textContent = '';

    const bundles = snapshot.bundles;
    if (!isArray(bundles) || !bundles.length) {
        const empty = doc.createElement('span');
        empty.className = 'live-status-overlay-bundle live-status-overlay-bundle--empty';
        empty.textContent = i18n.t('liveStatusOverlay.values.noBundles');
        bundleContainer.appendChild(empty);
        return;
    }

    bundles.slice(0, LIVE_STATUS_OVERLAY_MAX_BUNDLES).forEach((bundle) => {
        const item = doc.createElement('div');
        item.className = 'live-status-overlay-bundle';
        const name = doc.createElement('span');
        name.className = 'live-status-overlay-bundle-name';
        name.textContent = bundle?.name || i18n.t('liveStatusOverlay.values.unknownBundle');

        const status = doc.createElement('span');
        status.className = 'live-status-overlay-bundle-status';
        const pendingCount = countPendingBundleResources(bundle?.resources);
        if (pendingCount > 0) {
            status.textContent = i18n.t('liveStatusOverlay.values.pendingCount', { count: pendingCount });
            item.classList.add('live-status-overlay-bundle--pending');
        } else {
            status.textContent = i18n.t('liveStatusOverlay.values.ready');
            item.classList.add('live-status-overlay-bundle--ready');
        }

        item.appendChild(name);
        item.appendChild(status);
        bundleContainer.appendChild(item);
    });
};

export { createOverlayElements, renderSnapshot, setConnectionStatus, setLastEvent, setLatencyValue, setQueueValue };
