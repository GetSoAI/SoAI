"""SoAI - Vulkan instance and physical property ABI [backend/core/hardware/vulkan_abi.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

__all__ = (
    "VulkanInstanceCreateInfo",
    "VulkanApplicationInfo",
    "VulkanProperties",
    "VulkanProperties2",
    "VulkanPciProperties",
    "VulkanExtension",
    "VulkanIdentityProperties",
)


class VulkanApplicationInfo(ctypes.Structure):
    _fields_ = (
        ("structure_type", ctypes.c_uint32),
        ("next", ctypes.c_void_p),
        ("application_name", ctypes.c_char_p),
        ("application_version", ctypes.c_uint32),
        ("engine_name", ctypes.c_char_p),
        ("engine_version", ctypes.c_uint32),
        ("api_version", ctypes.c_uint32),
    )


class VulkanInstanceCreateInfo(ctypes.Structure):
    _fields_ = (
        ("structure_type", ctypes.c_uint32),
        ("next", ctypes.c_void_p),
        ("flags", ctypes.c_uint32),
        ("application", ctypes.POINTER(VulkanApplicationInfo)),
        ("layer_count", ctypes.c_uint32),
        ("layers", ctypes.POINTER(ctypes.c_char_p)),
        ("extension_count", ctypes.c_uint32),
        ("extensions", ctypes.POINTER(ctypes.c_char_p)),
    )


class VulkanLimits(ctypes.Structure):
    _fields_ = (
        ("max_image_dimension1_d", ctypes.c_uint32),
        ("max_image_dimension2_d", ctypes.c_uint32),
        ("max_image_dimension3_d", ctypes.c_uint32),
        ("max_image_dimension_cube", ctypes.c_uint32),
        ("max_image_array_layers", ctypes.c_uint32),
        ("max_texel_buffer_elements", ctypes.c_uint32),
        ("max_uniform_buffer_range", ctypes.c_uint32),
        ("max_storage_buffer_range", ctypes.c_uint32),
        ("max_push_constants_size", ctypes.c_uint32),
        ("max_memory_allocation_count", ctypes.c_uint32),
        ("max_sampler_allocation_count", ctypes.c_uint32),
        ("buffer_image_granularity", ctypes.c_uint64),
        ("sparse_address_space_size", ctypes.c_uint64),
        ("max_bound_descriptor_sets", ctypes.c_uint32),
        ("max_per_stage_descriptor_samplers", ctypes.c_uint32),
        ("max_per_stage_descriptor_uniform_buffers", ctypes.c_uint32),
        ("max_per_stage_descriptor_storage_buffers", ctypes.c_uint32),
        ("max_per_stage_descriptor_sampled_images", ctypes.c_uint32),
        ("max_per_stage_descriptor_storage_images", ctypes.c_uint32),
        ("max_per_stage_descriptor_input_attachments", ctypes.c_uint32),
        ("max_per_stage_resources", ctypes.c_uint32),
        ("max_descriptor_set_samplers", ctypes.c_uint32),
        ("max_descriptor_set_uniform_buffers", ctypes.c_uint32),
        ("max_descriptor_set_uniform_buffers_dynamic", ctypes.c_uint32),
        ("max_descriptor_set_storage_buffers", ctypes.c_uint32),
        ("max_descriptor_set_storage_buffers_dynamic", ctypes.c_uint32),
        ("max_descriptor_set_sampled_images", ctypes.c_uint32),
        ("max_descriptor_set_storage_images", ctypes.c_uint32),
        ("max_descriptor_set_input_attachments", ctypes.c_uint32),
        ("max_vertex_input_attributes", ctypes.c_uint32),
        ("max_vertex_input_bindings", ctypes.c_uint32),
        ("max_vertex_input_attribute_offset", ctypes.c_uint32),
        ("max_vertex_input_binding_stride", ctypes.c_uint32),
        ("max_vertex_output_components", ctypes.c_uint32),
        ("max_tessellation_generation_level", ctypes.c_uint32),
        ("max_tessellation_patch_size", ctypes.c_uint32),
        ("max_tessellation_control_per_vertex_input_components", ctypes.c_uint32),
        ("max_tessellation_control_per_vertex_output_components", ctypes.c_uint32),
        ("max_tessellation_control_per_patch_output_components", ctypes.c_uint32),
        ("max_tessellation_control_total_output_components", ctypes.c_uint32),
        ("max_tessellation_evaluation_input_components", ctypes.c_uint32),
        ("max_tessellation_evaluation_output_components", ctypes.c_uint32),
        ("max_geometry_shader_invocations", ctypes.c_uint32),
        ("max_geometry_input_components", ctypes.c_uint32),
        ("max_geometry_output_components", ctypes.c_uint32),
        ("max_geometry_output_vertices", ctypes.c_uint32),
        ("max_geometry_total_output_components", ctypes.c_uint32),
        ("max_fragment_input_components", ctypes.c_uint32),
        ("max_fragment_output_attachments", ctypes.c_uint32),
        ("max_fragment_dual_src_attachments", ctypes.c_uint32),
        ("max_fragment_combined_output_resources", ctypes.c_uint32),
        ("max_compute_shared_memory_size", ctypes.c_uint32),
        ("max_compute_work_group_count", ctypes.c_uint32 * 3),
        ("max_compute_work_group_invocations", ctypes.c_uint32),
        ("max_compute_work_group_size", ctypes.c_uint32 * 3),
        ("sub_pixel_precision_bits", ctypes.c_uint32),
        ("sub_texel_precision_bits", ctypes.c_uint32),
        ("mipmap_precision_bits", ctypes.c_uint32),
        ("max_draw_indexed_index_value", ctypes.c_uint32),
        ("max_draw_indirect_count", ctypes.c_uint32),
        ("max_sampler_lod_bias", ctypes.c_float),
        ("max_sampler_anisotropy", ctypes.c_float),
        ("max_viewports", ctypes.c_uint32),
        ("max_viewport_dimensions", ctypes.c_uint32 * 2),
        ("viewport_bounds_range", ctypes.c_float * 2),
        ("viewport_sub_pixel_bits", ctypes.c_uint32),
        ("min_memory_map_alignment", ctypes.c_size_t),
        ("min_texel_buffer_offset_alignment", ctypes.c_uint64),
        ("min_uniform_buffer_offset_alignment", ctypes.c_uint64),
        ("min_storage_buffer_offset_alignment", ctypes.c_uint64),
        ("min_texel_offset", ctypes.c_int32),
        ("max_texel_offset", ctypes.c_uint32),
        ("min_texel_gather_offset", ctypes.c_int32),
        ("max_texel_gather_offset", ctypes.c_uint32),
        ("min_interpolation_offset", ctypes.c_float),
        ("max_interpolation_offset", ctypes.c_float),
        ("sub_pixel_interpolation_offset_bits", ctypes.c_uint32),
        ("max_framebuffer_width", ctypes.c_uint32),
        ("max_framebuffer_height", ctypes.c_uint32),
        ("max_framebuffer_layers", ctypes.c_uint32),
        ("framebuffer_color_sample_counts", ctypes.c_uint32),
        ("framebuffer_depth_sample_counts", ctypes.c_uint32),
        ("framebuffer_stencil_sample_counts", ctypes.c_uint32),
        ("framebuffer_no_attachments_sample_counts", ctypes.c_uint32),
        ("max_color_attachments", ctypes.c_uint32),
        ("sampled_image_color_sample_counts", ctypes.c_uint32),
        ("sampled_image_integer_sample_counts", ctypes.c_uint32),
        ("sampled_image_depth_sample_counts", ctypes.c_uint32),
        ("sampled_image_stencil_sample_counts", ctypes.c_uint32),
        ("storage_image_sample_counts", ctypes.c_uint32),
        ("max_sample_mask_words", ctypes.c_uint32),
        ("timestamp_compute_and_graphics", ctypes.c_uint32),
        ("timestamp_period", ctypes.c_float),
        ("max_clip_distances", ctypes.c_uint32),
        ("max_cull_distances", ctypes.c_uint32),
        ("max_combined_clip_and_cull_distances", ctypes.c_uint32),
        ("discrete_queue_priorities", ctypes.c_uint32),
        ("point_size_range", ctypes.c_float * 2),
        ("line_width_range", ctypes.c_float * 2),
        ("point_size_granularity", ctypes.c_float),
        ("line_width_granularity", ctypes.c_float),
        ("strict_lines", ctypes.c_uint32),
        ("standard_sample_locations", ctypes.c_uint32),
        ("optimal_buffer_copy_offset_alignment", ctypes.c_uint64),
        ("optimal_buffer_copy_row_pitch_alignment", ctypes.c_uint64),
        ("non_coherent_atom_size", ctypes.c_uint64),
    )


class VulkanSparseProperties(ctypes.Structure):
    _fields_ = (
        ("residency_standard2_d_block_shape", ctypes.c_uint32),
        ("residency_standard2_d_multisample_block_shape", ctypes.c_uint32),
        ("residency_standard3_d_block_shape", ctypes.c_uint32),
        ("residency_aligned_mip_size", ctypes.c_uint32),
        ("residency_non_resident_strict", ctypes.c_uint32),
    )


class VulkanProperties(ctypes.Structure):
    _fields_ = (
        ("api_version", ctypes.c_uint32),
        ("driver_version", ctypes.c_uint32),
        ("vendor_id", ctypes.c_uint32),
        ("device_id", ctypes.c_uint32),
        ("device_type", ctypes.c_uint32),
        ("device_name", ctypes.c_char * 256),
        ("pipeline_cache_uuid", ctypes.c_uint8 * 16),
        ("limits", VulkanLimits),
        ("sparse_properties", VulkanSparseProperties),
    )


class VulkanProperties2(ctypes.Structure):
    _fields_ = (
        ("structure_type", ctypes.c_uint32),
        ("next", ctypes.c_void_p),
        ("properties", VulkanProperties),
    )


class VulkanPciProperties(ctypes.Structure):
    _fields_ = (
        ("structure_type", ctypes.c_uint32),
        ("next", ctypes.c_void_p),
        ("domain", ctypes.c_uint32),
        ("bus", ctypes.c_uint32),
        ("device", ctypes.c_uint32),
        ("function", ctypes.c_uint32),
    )


class VulkanExtension(ctypes.Structure):
    _fields_ = (("name", ctypes.c_char * 256), ("spec_version", ctypes.c_uint32))


class VulkanIdentityProperties(ctypes.Structure):
    _fields_ = (
        ("structure_type", ctypes.c_uint32),
        ("next", ctypes.c_void_p),
        ("device_uuid", ctypes.c_uint8 * 16),
        ("driver_uuid", ctypes.c_uint8 * 16),
        ("device_luid", ctypes.c_uint8 * 8),
        ("device_node_mask", ctypes.c_uint32),
        ("device_luid_valid", ctypes.c_uint32),
    )
