"""每个 step 输出落盘前的 schema 校验。"""

from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def validate_step_output(model_class: Type[T], data: dict, step_id: str) -> T:
    """校验 step 输出，失败时抛出带明确 step_id 的 ValidationError 信息。"""
    try:
        return model_class.model_validate(data)
    except ValidationError as e:
        raise ValueError(
            f"[SchemaValidator] {step_id} 输出不符合 {model_class.__name__} schema:\n{e}"
        ) from e
