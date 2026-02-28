from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 2048


@dataclass
class MemoryConfig:
    short_term_limit: int = 10
    episodic_limit: int = 100
    long_term_limit: int = 100


@dataclass
class AgentConfig:
    max_steps: int = 30
    allow_self_repair: bool = True


@dataclass
class ObservabilityConfig:
    enable_trace_collection: bool = True
    enable_decision_logging: bool = True
    trace_output_path: Optional[str] = None
    log_level: str = "INFO"


@dataclass
class ToolsEmbeddingConfig:
    """Embedding-based tool selection config."""
    enabled: bool = True
    # API 模式配置（使用 DashScope/百炼 Embedding API）
    api_provider: str = "dashscope"  # 当前支持: "dashscope"
    api_model: str = "text-embedding-v2"  # DashScope Embedding 模型名称
    api_key: Optional[str] = None  # API Key，如果为 None 则从环境变量 DASHSCOPE_API_KEY 读取
    # 旧版本地模型配置（已废弃，保留用于兼容）
    model_name: Optional[str] = None  # 已废弃，使用 API 模式
    top_k: int = 15
    similarity_threshold: float = 0.20  # 相似度阈值
    translate_query: bool = True  # 是否将中文查询翻译为英文（提高工具检索准确性）
    max_basic_tools: int = 5  # 最多添加的基础工具数量
    include_basic_prefixes: tuple = ("ui.", "os.")
    essential_tools: tuple = ("os.open_shell", "os.get_axtree")  # 核心基础工具


@dataclass
class OCRConfig:
    """OCR configuration for screenshot text recognition."""
    enabled: bool = False  # 是否启用 OCR
    provider: str = "aliyun"  # OCR 提供商，当前支持: "aliyun"
    access_key_id: Optional[str] = None  # 阿里云 AccessKey ID，从环境变量 ALIYUN_ACCESS_KEY_ID 读取
    access_key_secret: Optional[str] = None  # 阿里云 AccessKey Secret，从环境变量 ALIYUN_ACCESS_KEY_SECRET 读取
    endpoint: str = "ocr-api.cn-hangzhou.aliyuncs.com"  # OCR API 端点


@dataclass
class Config:
    llm: LLMConfig
    memory: MemoryConfig
    agent: AgentConfig
    logging: dict
    tools_embedding: Optional[ToolsEmbeddingConfig] = None
    observability: Optional[ObservabilityConfig] = None
    ocr: Optional[OCRConfig] = None

    @staticmethod
    def from_dict(data: dict):
        observability_data = data.get("observability", {})
        observability = ObservabilityConfig(**observability_data) if observability_data else None
        
        # 处理 tools_embedding 配置，将列表转换为元组
        embedding_data = data.get("tools_embedding", {})
        if embedding_data:
            # 将 YAML 中的列表转换为元组（dataclass 要求）
            if "include_basic_prefixes" in embedding_data and isinstance(embedding_data["include_basic_prefixes"], list):
                embedding_data["include_basic_prefixes"] = tuple(embedding_data["include_basic_prefixes"])
            if "essential_tools" in embedding_data and isinstance(embedding_data["essential_tools"], list):
                embedding_data["essential_tools"] = tuple(embedding_data["essential_tools"])
            
            # 从环境变量读取 API key（如果配置中未提供）
            if "api_key" not in embedding_data or not embedding_data.get("api_key"):
                api_key = os.getenv("DASHSCOPE_API_KEY")
                if api_key:
                    embedding_data["api_key"] = api_key
            
            # 从环境变量读取模型名称（如果配置中未提供）
            if "api_model" not in embedding_data or not embedding_data.get("api_model"):
                api_model = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v2")
                embedding_data["api_model"] = api_model
            
            embedding_cfg = ToolsEmbeddingConfig(**embedding_data)
        else:
            embedding_cfg = None
        
        # 处理 OCR 配置
        ocr_data = data.get("ocr", {})
        if ocr_data:
            # 从环境变量读取 AccessKey（如果配置中未提供）
            if "access_key_id" not in ocr_data or not ocr_data.get("access_key_id"):
                access_key_id = os.getenv("ALIYUN_ACCESS_KEY_ID")
                if access_key_id:
                    ocr_data["access_key_id"] = access_key_id
            
            if "access_key_secret" not in ocr_data or not ocr_data.get("access_key_secret"):
                access_key_secret = os.getenv("ALIYUN_ACCESS_KEY_SECRET")
                if access_key_secret:
                    ocr_data["access_key_secret"] = access_key_secret
            
            ocr_cfg = OCRConfig(**ocr_data)
        else:
            ocr_cfg = None
        
        return Config(
            llm=LLMConfig(**data["llm"]),
            memory=MemoryConfig(**data["memory"]),
            agent=AgentConfig(**data["agent"]),
            logging=data.get("logging", {}),
            tools_embedding=embedding_cfg,
            observability=observability,
            ocr=ocr_cfg,
        )
