"""Inferno -- Potato OS inference layer.

Inferno owns the runtime-facing side of inference: backend proxying,
model family classification, model registry, settings normalization,
projector management, and adapter processes.  Everything between
"Potato says run this model" and "here is the OpenAI-compatible response"
lives here.

Boundary contract
-----------------
Potato (caller) provides:
    - Base URL of the active inference runtime
    - Chat backend mode ("llama" | "fake" | "auto")
    - Model filename and optional source URL (for projector resolution)
    - POTATO_MODEL_PATH env var (for LiteRT adapter startup)
    - Hardware/device/OS inputs (memory, device class, runtime binaries)
    - ModelStoreConfig with filesystem paths and product-level defaults

Inferno (this package) provides:
    - BackendProxyError            exception for proxy failures
    - BackendResponse              dataclass for HTTP responses (body or stream)
    - ChatCompletionRepository     protocol for backend implementations
    - LlamaCppRepository           real llama.cpp HTTP proxy
    - FakeLlamaRepository          fake backend for dev/test
    - ChatRepositoryManager        dispatch to named backends
    - is_qwen35_filename           detect Qwen 3.5 model files
    - is_gemma4_filename           detect Gemma 4 model files
    - projector_repo_for_model     resolve HuggingFace projector repo
    - recommended_runtime_for_model  preferred runtime family for a model
    - build_llama_server_args      pure function to build CLI args
    - ModelStoreConfig             filesystem/policy config for registry ops
    - Model registry functions     ensure/save/register/delete/update state
    - Format handling              model_format_for_filename, validate_model_url
    - Settings normalization       normalize_model_settings, build_model_capabilities
    - Projector management         build_model_projector_status, download, candidates
    - litert_adapter               standalone FastAPI app (core.inferno.litert_adapter:app)

Inferno does NOT import from core.model_state, core.runtime_state,
core.settings, core.deps, or any apps/ code.  The dependency arrow
points one way: Potato -> Inferno, never Inferno -> Potato.
"""

from .backend import (
    BackendProxyError,
    BackendResponse,
    ChatCompletionRepository,
    ChatRepositoryManager,
    FakeLlamaRepository,
    LlamaCppRepository,
)
from .launch_config import build_llama_server_args
from .model_families import (
    build_model_projector_status,
    default_projector_candidates_for_model,
    is_gemma4_filename,
    is_qwen35_filename,
    projector_repo_for_model,
    recommended_runtime_for_model,
)
from .model_registry import (
    DEFAULT_MODEL_CHAT_SETTINGS,
    DEFAULT_MODEL_VISION_SETTINGS,
    MODELS_STATE_VERSION,
    VALID_MODEL_EXTENSIONS,
    ModelSettingsValidationError,
    ModelStoreConfig,
    any_model_ready,
    apply_model_chat_defaults,
    build_model_capabilities,
    delete_model,
    describe_model_storage,
    discover_local_model_filenames,
    download_default_projector_for_model,
    ensure_models_state,
    get_model_by_id,
    is_qwen35_a3b_filename,
    model_file_path,
    model_file_present,
    model_format_for_filename,
    model_supports_vision_filename,
    normalize_model_settings,
    register_model_url,
    resolve_model_runtime_path,
    save_models_state,
    update_model_settings,
    validate_model_url,
)

__all__ = [
    "BackendProxyError",
    "BackendResponse",
    "ChatCompletionRepository",
    "ChatRepositoryManager",
    "DEFAULT_MODEL_CHAT_SETTINGS",
    "DEFAULT_MODEL_VISION_SETTINGS",
    "FakeLlamaRepository",
    "LlamaCppRepository",
    "MODELS_STATE_VERSION",
    "ModelSettingsValidationError",
    "ModelStoreConfig",
    "VALID_MODEL_EXTENSIONS",
    "any_model_ready",
    "apply_model_chat_defaults",
    "build_llama_server_args",
    "build_model_capabilities",
    "build_model_projector_status",
    "default_projector_candidates_for_model",
    "delete_model",
    "describe_model_storage",
    "discover_local_model_filenames",
    "download_default_projector_for_model",
    "ensure_models_state",
    "get_model_by_id",
    "is_gemma4_filename",
    "is_qwen35_a3b_filename",
    "is_qwen35_filename",
    "model_file_path",
    "model_file_present",
    "model_format_for_filename",
    "model_supports_vision_filename",
    "normalize_model_settings",
    "projector_repo_for_model",
    "recommended_runtime_for_model",
    "register_model_url",
    "resolve_model_runtime_path",
    "save_models_state",
    "update_model_settings",
    "validate_model_url",
]
