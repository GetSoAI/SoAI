"""SoAI - Database repository for RAG documents and files [backend/database/repositories/files/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.files.service_file_catalog import (
    add_file,
    delete_file,
    delete_files_by_ids,
    get_all_file_records_for_reconciliation,
    get_file_info,
    get_file_info_with_path,
    list_files,
)
from database.repositories.files.service_rag_jobs import (
    acquire_rag_job_lease,
    acquire_rag_maintenance_lock,
    create_rag_processing_job,
    finalize_rag_processing_job,
    release_rag_job_lease,
    release_rag_maintenance_lock,
    renew_rag_job_lease,
    renew_rag_maintenance_lock,
    replace_rag_chunks_for_job,
    update_rag_document_status_for_job,
)
from database.repositories.files.service_rag_reads import (
    find_completed_rag_document_for_embedding_cache,
    find_recent_completed_rag_document_by_source_url_cache,
    get_active_linked_rag_documents,
    get_processing_rag_document_by_task_id,
    get_rag_chunk_by_id,
    get_rag_chunks_by_ids_completed,
    get_rag_chunks_for_conversation,
    get_rag_chunks_for_conversation_page,
    get_rag_chunks_for_document,
    get_rag_chunks_for_document_cleanup,
    get_rag_chunks_for_document_page,
    get_rag_collection_metadata,
    get_rag_config,
    get_rag_counts_for_conversation,
    get_rag_counts_for_conversation_with_active_links,
    get_rag_document_by_id,
    get_rag_documents_for_conversation,
    get_rag_documents_for_conversation_with_active_links,
    get_rag_processing_job,
    list_claimable_rag_processing_jobs,
)
from database.repositories.files.service_rag_writes import (
    activate_rag_collection,
    create_rag_chunks,
    create_rag_document,
    create_rag_document_with_knowledge_item,
    delete_rag_collection_metadata_for_conversation,
    delete_rag_document,
    delete_rag_documents_for_conversation,
    update_rag_collection_metadata,
    update_rag_config,
    update_rag_config_with_defaults,
    update_rag_document_status,
)

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseFiles",)


class DatabaseFiles:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    get_rag_documents_for_conversation = get_rag_documents_for_conversation
    get_rag_documents_for_conversation_with_active_links = (
        get_rag_documents_for_conversation_with_active_links
    )
    get_rag_document_by_id = get_rag_document_by_id
    get_rag_processing_job = get_rag_processing_job
    list_claimable_rag_processing_jobs = list_claimable_rag_processing_jobs
    get_processing_rag_document_by_task_id = get_processing_rag_document_by_task_id
    find_completed_rag_document_for_embedding_cache = (
        find_completed_rag_document_for_embedding_cache
    )
    find_recent_completed_rag_document_by_source_url_cache = (
        find_recent_completed_rag_document_by_source_url_cache
    )
    update_rag_document_status = update_rag_document_status
    update_rag_document_status_for_job = update_rag_document_status_for_job
    delete_rag_document = delete_rag_document
    delete_rag_documents_for_conversation = delete_rag_documents_for_conversation
    create_rag_chunks = create_rag_chunks
    replace_rag_chunks_for_job = replace_rag_chunks_for_job
    get_rag_chunks_for_document = get_rag_chunks_for_document
    get_rag_chunks_for_document_cleanup = get_rag_chunks_for_document_cleanup
    get_rag_chunks_for_document_page = get_rag_chunks_for_document_page
    get_rag_chunk_by_id = get_rag_chunk_by_id
    get_rag_chunks_by_ids_completed = get_rag_chunks_by_ids_completed
    get_rag_chunks_for_conversation = get_rag_chunks_for_conversation
    get_rag_chunks_for_conversation_page = get_rag_chunks_for_conversation_page
    get_rag_counts_for_conversation = get_rag_counts_for_conversation
    get_rag_counts_for_conversation_with_active_links = (
        get_rag_counts_for_conversation_with_active_links
    )
    get_rag_config = get_rag_config
    get_rag_collection_metadata = get_rag_collection_metadata
    get_active_linked_rag_documents = get_active_linked_rag_documents
    update_rag_config = update_rag_config
    update_rag_config_with_defaults = update_rag_config_with_defaults
    update_rag_collection_metadata = update_rag_collection_metadata
    activate_rag_collection = activate_rag_collection
    delete_rag_collection_metadata_for_conversation = (
        delete_rag_collection_metadata_for_conversation
    )
    create_rag_document = create_rag_document
    create_rag_document_with_knowledge_item = create_rag_document_with_knowledge_item
    create_rag_processing_job = create_rag_processing_job
    acquire_rag_job_lease = acquire_rag_job_lease
    renew_rag_job_lease = renew_rag_job_lease
    release_rag_job_lease = release_rag_job_lease
    finalize_rag_processing_job = finalize_rag_processing_job
    acquire_rag_maintenance_lock = acquire_rag_maintenance_lock
    renew_rag_maintenance_lock = renew_rag_maintenance_lock
    release_rag_maintenance_lock = release_rag_maintenance_lock
    add_file = add_file
    get_file_info = get_file_info
    get_file_info_with_path = get_file_info_with_path
    list_files = list_files
    delete_file = delete_file
    get_all_file_records_for_reconciliation = get_all_file_records_for_reconciliation
    delete_files_by_ids = delete_files_by_ids
