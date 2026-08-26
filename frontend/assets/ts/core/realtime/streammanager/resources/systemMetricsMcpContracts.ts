/* SoAI - System metrics V1 MCP block contracts [frontend/assets/ts/core/realtime/streammanager/resources/systemMetricsMcpContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { decodeSystemMetricsTimings } from '@core/realtime/streammanager/resources/systemMetricsTimingContracts.ts';
import { assignOptionalSection, decodeFiniteNumberFields, decodeFiniteNumberMap, optionalMetricsObject } from '@core/realtime/streammanager/resources/systemMetricsValueDecoding.ts';

const decodeMcpServerMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'mcp_server', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const notifications = optionalMetricsObject(source, 'notifications', 'system.metrics.mcp_server');
    const requests = optionalMetricsObject(source, 'requests', 'system.metrics.mcp_server');
    const tools = optionalMetricsObject(source, 'tools', 'system.metrics.mcp_server');
    const resources = optionalMetricsObject(source, 'resources', 'system.metrics.mcp_server');
    const tasks = optionalMetricsObject(source, 'tasks', 'system.metrics.mcp_server');
    if (notifications) decoded['notifications'] = decodeFiniteNumberFields(notifications, { dropped: 'dropped', failures: 'failures', sent: 'sent' }, 'system.metrics.mcp_server.notifications');
    if (requests) decoded['requests'] = decodeFiniteNumberFields(requests, { total: 'total', handled: 'handled', failed: 'failed' }, 'system.metrics.mcp_server.requests');
    if (tools) {
        const decodedTools = decodeFiniteNumberFields(tools, { 'calls_total': 'callsTotal' }, 'system.metrics.mcp_server.tools');
        const calls = optionalMetricsObject(tools, 'calls', 'system.metrics.mcp_server.tools');
        if (calls) decodedTools['calls'] = decodeFiniteNumberFields(calls, { succeeded: 'succeeded', failed: 'failed' }, 'system.metrics.mcp_server.tools.calls');
        decoded['tools'] = decodedTools;
    }
    if (resources) {
        const decodedResources = decodeFiniteNumberFields(resources, { subscriptions: 'subscriptions', unsubscriptions: 'unsubscriptions' }, 'system.metrics.mcp_server.resources');
        const reads = optionalMetricsObject(resources, 'reads', 'system.metrics.mcp_server.resources');
        if (reads) decodedResources['reads'] = decodeFiniteNumberFields(reads, { total: 'total', failed: 'failed', succeeded: 'succeeded' }, 'system.metrics.mcp_server.resources.reads');
        decoded['resources'] = decodedResources;
    }
    if (tasks) decoded['tasks'] = decodeFiniteNumberFields(tasks, { created: 'created', completed: 'completed', failed: 'failed', cancelled: 'cancelled' }, 'system.metrics.mcp_server.tasks');
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.mcp_server', { 'request_latency_ms': 'requestLatencyMs', 'tool_execution_ms': 'toolExecutionMs', 'resource_read_ms': 'resourceReadMs' }));
    return decoded;
};

const decodeMcpRemoteMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'mcp_remote', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const connections = optionalMetricsObject(source, 'connections', 'system.metrics.mcp_remote');
    if (connections) decoded['connections'] = decodeFiniteNumberFields(connections, { total: 'total', successful: 'successful', failed: 'failed', disconnections: 'disconnections' }, 'system.metrics.mcp_remote.connections');
    return decoded;
};

const decodeMcpSearchMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'mcp_search', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const searches = optionalMetricsObject(source, 'searches', 'system.metrics.mcp_search');
    const fetches = optionalMetricsObject(source, 'fetches', 'system.metrics.mcp_search');
    const retries = optionalMetricsObject(source, 'retries', 'system.metrics.mcp_search');
    if (searches) {
        const decodedSearches = decodeFiniteNumberFields(searches, { total: 'total', succeeded: 'succeeded', failed: 'failed' }, 'system.metrics.mcp_search.searches');
        const byProvider = optionalMetricsObject(searches, 'by_provider', 'system.metrics.mcp_search.searches');
        if (byProvider) decodedSearches['byProvider'] = decodeFiniteNumberMap(byProvider, 'system.metrics.mcp_search.searches.by_provider');
        decoded['searches'] = decodedSearches;
    }
    if (fetches) decoded['fetches'] = decodeFiniteNumberFields(fetches, { total: 'total', succeeded: 'succeeded', failed: 'failed' }, 'system.metrics.mcp_search.fetches');
    if (retries) {
        const decodedRetries = decodeFiniteNumberFields(retries, { total: 'total' }, 'system.metrics.mcp_search.retries');
        const byProvider = optionalMetricsObject(retries, 'by_provider', 'system.metrics.mcp_search.retries');
        if (byProvider) decodedRetries['byProvider'] = decodeFiniteNumberMap(byProvider, 'system.metrics.mcp_search.retries.by_provider');
        decoded['retries'] = decodedRetries;
    }
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.mcp_search', { 'search_latency_ms': 'searchLatencyMs', 'fetch_latency_ms': 'fetchLatencyMs' }));
    return decoded;
};

const decodeMcpRagMetrics = (root: JsonObject): JsonObject | undefined => {
    const source = optionalMetricsObject(root, 'mcp_rag', 'system.metrics');
    if (!source) return undefined;
    const decoded: JsonObject = {};
    const backpressure = optionalMetricsObject(source, 'backpressure', 'system.metrics.mcp_rag');
    const documents = optionalMetricsObject(source, 'documents', 'system.metrics.mcp_rag');
    const parsing = optionalMetricsObject(source, 'parsing', 'system.metrics.mcp_rag');
    const chunking = optionalMetricsObject(source, 'chunking', 'system.metrics.mcp_rag');
    const embeddings = optionalMetricsObject(source, 'embeddings', 'system.metrics.mcp_rag');
    const searches = optionalMetricsObject(source, 'searches', 'system.metrics.mcp_rag');
    const gauges = optionalMetricsObject(source, 'gauges', 'system.metrics.mcp_rag');
    if (backpressure) decoded['backpressure'] = decodeFiniteNumberFields(backpressure, { dropped: 'dropped' }, 'system.metrics.mcp_rag.backpressure');
    if (documents) decoded['documents'] = decodeFiniteNumberFields(documents, { 'uploads_queued': 'uploadsQueued', 'uploads_completed': 'uploadsCompleted', 'uploads_failed': 'uploadsFailed', deletions: 'deletions', 'web_fetch_ingests_queued': 'webFetchIngestsQueued', 'web_fetch_ingests_completed': 'webFetchIngestsCompleted', 'web_fetch_ingests_failed': 'webFetchIngestsFailed' }, 'system.metrics.mcp_rag.documents');
    if (parsing) {
        const decodedParsing = decodeFiniteNumberFields(parsing, { total: 'total', succeeded: 'succeeded', failed: 'failed' }, 'system.metrics.mcp_rag.parsing');
        const byType = optionalMetricsObject(parsing, 'by_type', 'system.metrics.mcp_rag.parsing');
        if (byType) decodedParsing['byType'] = decodeFiniteNumberMap(byType, 'system.metrics.mcp_rag.parsing.by_type');
        decoded['parsing'] = decodedParsing;
    }
    if (chunking) decoded['chunking'] = decodeFiniteNumberFields(chunking, { 'chunks_created': 'chunksCreated' }, 'system.metrics.mcp_rag.chunking');
    if (embeddings) decoded['embeddings'] = decodeFiniteNumberFields(embeddings, { requests: 'requests', batches: 'batches', deduplicated: 'deduplicated', failed: 'failed' }, 'system.metrics.mcp_rag.embeddings');
    if (searches) decoded['searches'] = decodeFiniteNumberFields(searches, { total: 'total', similarity: 'similarity', mmr: 'mmr', hybrid: 'hybrid', failed: 'failed' }, 'system.metrics.mcp_rag.searches');
    if (gauges) decoded['gauges'] = decodeFiniteNumberFields(gauges, { 'processing_queue_size': 'processingQueueSize', 'active_workers': 'activeWorkers' }, 'system.metrics.mcp_rag.gauges');
    assignOptionalSection(decoded, 'timings', decodeSystemMetricsTimings(source, 'system.metrics.mcp_rag', { 'document_processing_ms': 'documentProcessingMs', 'search_latency_ms': 'searchLatencyMs', 'embedding_latency_ms': 'embeddingLatencyMs' }));
    return decoded;
};

export { decodeMcpRagMetrics, decodeMcpRemoteMetrics, decodeMcpSearchMetrics, decodeMcpServerMetrics };
