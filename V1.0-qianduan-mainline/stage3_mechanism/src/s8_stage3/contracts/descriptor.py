"""描述符层合同 — Step 07 Descriptor Extractor。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MechanismDescriptor(BaseModel):
    """单条抽象材料描述符（不得含具体材料名）。"""

    descriptor_id: str = Field(...)
    descriptor_text: str = Field(..., description="抽象描述符文本，不含具体材料名")
    mechanism_role: str = Field(..., description="该描述符对应机理中哪个要素")
    required_material_features: list[str] = Field(default_factory=list)
    priority: Literal["critical", "important", "optional"] = Field("important")
    derived_from_mechanism: str = Field("", description="来源机理步骤/标签")


class DescriptorSheet(BaseModel):
    """描述符层完整输出。"""

    step_id: str = Field(default="s07_descriptors")
    descriptors: list[MechanismDescriptor] = Field(default_factory=list)
    extraction_notes: str = Field("")
