# -*- coding: utf-8 -*-
"""
材料配置模块

定义材料白名单、分类和属性信息，用于数据过滤和分析。

更新日期: 2026-01-26
"""

from typing import List, Dict, Set


# ============================================================
# 材料白名单/黑名单配置
# ============================================================

# 保留的材料（均为限域材料）
MATERIAL_WHITELIST: List[str] = [
    "S8",   # 海泡石 + H3PO4（主要研究材料）
    "S14",  # 埃洛石 + H3PO4
    "S16",  # 膨润土 + H3PO4
    "S95",  # 海泡石 + H2SO4
    "S96",  # 膨润土 + H2SO4
    "S97",  # 埃洛石 + H2SO4
    "S6",   # 海泡石 + 植酸
    "S13",  # 膨润土 + 植酸
    "S15",  # 高岭土 + 植酸
]

# 移除的材料
MATERIAL_BLACKLIST: List[str] = [
    "S60",  # 纯H3PO4液体（无限域效应）
    "S12",  # 纯水体系
]

# 转换为集合以便快速查找
MATERIAL_WHITELIST_SET: Set[str] = set(MATERIAL_WHITELIST)
MATERIAL_BLACKLIST_SET: Set[str] = set(MATERIAL_BLACKLIST)


# ============================================================
# 材料分类
# ============================================================

# 按黏土基材分类
MATERIAL_BY_CLAY: Dict[str, List[str]] = {
    "Sepiolite":   ["S8", "S6", "S95"],      # 海泡石基
    "Halloysite":  ["S14", "S97"],           # 埃洛石基
    "Bentonite":   ["S13", "S16", "S96"],    # 膨润土基
    "Kaolin":      ["S15"],                   # 高岭土基
}

# 按酸体系分类
MATERIAL_BY_ACID: Dict[str, List[str]] = {
    "H3PO4":  ["S8", "S14", "S16"],          # 磷酸体系（主要）
    "H2SO4":  ["S95", "S96", "S97"],         # 硫酸体系
    "Phytic": ["S6", "S13", "S15"],          # 植酸体系
}

# 反向映射：材料 -> 黏土类型
CLAY_TYPE_MAP: Dict[str, str] = {}
for clay, materials in MATERIAL_BY_CLAY.items():
    for mat in materials:
        CLAY_TYPE_MAP[mat] = clay

# 反向映射：材料 -> 酸类型
ACID_TYPE_MAP: Dict[str, str] = {}
for acid, materials in MATERIAL_BY_ACID.items():
    for mat in materials:
        ACID_TYPE_MAP[mat] = acid


# ============================================================
# 材料属性信息
# ============================================================

# 黏土材料物理特性
CLAY_PROPERTIES: Dict[str, Dict] = {
    "Sepiolite": {
        "chinese_name": "海泡石",
        "pore_diameter_nm": 0.5,           # 孔径 (nm)
        "surface_area_m2_g": 300,          # 比表面积 (m²/g)
        "structure": "纳米管状结构，具有大量纳米孔道",
        "features": "高比表面积，强限域效应，适合低温质子传导",
        "formula": "Mg8Si12O30(OH)4·8H2O",
    },
    "Halloysite": {
        "chinese_name": "埃洛石",
        "pore_diameter_nm": 15,            # 管内径 (nm)
        "surface_area_m2_g": 50,           # 比表面积 (m²/g)
        "structure": "卷曲管状结构，内腔可容纳客体分子",
        "features": "管状孔道，适度限域效应，可调控内径",
        "formula": "Al2Si2O5(OH)4·nH2O",
    },
    "Bentonite": {
        "chinese_name": "膨润土",
        "pore_diameter_nm": 1.2,           # 层间距 (nm)
        "surface_area_m2_g": 80,           # 比表面积 (m²/g)
        "structure": "层状结构，可插层膨胀",
        "features": "层间限域效应，亲水性强，可吸水膨胀",
        "formula": "(Na,Ca)0.33(Al,Mg)2(Si4O10)(OH)2·nH2O",
    },
    "Kaolin": {
        "chinese_name": "高岭土",
        "pore_diameter_nm": 0.7,           # 层间距 (nm)
        "surface_area_m2_g": 20,           # 比表面积 (m²/g)
        "structure": "层状硅酸盐，1:1型结构",
        "features": "稳定性好，层间空间有限",
        "formula": "Al2Si2O5(OH)4",
    },
}

# 酸体系特性
ACID_PROPERTIES: Dict[str, Dict] = {
    "H3PO4": {
        "chinese_name": "磷酸",
        "proton_donor": True,
        "viscosity": "中等",
        "mechanism": "可参与Grotthuss和Vehicle机制",
        "features": "质子传导性好，与水形成氢键网络",
    },
    "H2SO4": {
        "chinese_name": "硫酸",
        "proton_donor": True,
        "viscosity": "较低",
        "mechanism": "强酸，质子解离度高",
        "features": "高离子浓度，可能腐蚀黏土结构",
    },
    "Phytic": {
        "chinese_name": "植酸",
        "proton_donor": True,
        "viscosity": "高",
        "mechanism": "多磷酸基团，形成交联网络",
        "features": "六个磷酸基团，可形成稳定的质子传导网络",
        "formula": "C6H18O24P6",
    },
}


# ============================================================
# 辅助函数
# ============================================================

def is_material_allowed(material_id: str) -> bool:
    """
    判断材料是否在白名单中
    
    Args:
        material_id: 材料ID（如 "S8", "S60"）
        
    Returns:
        True if allowed, False otherwise
    """
    return material_id in MATERIAL_WHITELIST_SET


def get_material_from_sample_id(sample_id: str) -> str:
    """
    从样品ID提取材料类型
    
    Args:
        sample_id: 样品ID（如 "S8-3-2-1", "S60-2-2-1"）
        
    Returns:
        材料类型（如 "S8", "S60"）
    """
    return sample_id.split("-")[0]


def filter_samples_by_whitelist(sample_ids: List[str]) -> List[str]:
    """
    过滤样品列表，只保留白名单中的材料
    
    Args:
        sample_ids: 样品ID列表
        
    Returns:
        过滤后的样品ID列表
    """
    return [
        sid for sid in sample_ids 
        if get_material_from_sample_id(sid) in MATERIAL_WHITELIST_SET
    ]


def get_clay_type(material_id: str) -> str:
    """
    获取材料对应的黏土类型
    
    Args:
        material_id: 材料ID
        
    Returns:
        黏土类型（如 "Sepiolite"）
    """
    return CLAY_TYPE_MAP.get(material_id, "Unknown")


def get_acid_type(material_id: str) -> str:
    """
    获取材料对应的酸类型
    
    Args:
        material_id: 材料ID
        
    Returns:
        酸类型（如 "H3PO4"）
    """
    return ACID_TYPE_MAP.get(material_id, "Unknown")


def get_material_info(material_id: str) -> Dict:
    """
    获取材料的完整信息
    
    Args:
        material_id: 材料ID
        
    Returns:
        包含黏土和酸信息的字典
    """
    clay_type = get_clay_type(material_id)
    acid_type = get_acid_type(material_id)
    
    return {
        "material_id": material_id,
        "clay_type": clay_type,
        "clay_properties": CLAY_PROPERTIES.get(clay_type, {}),
        "acid_type": acid_type,
        "acid_properties": ACID_PROPERTIES.get(acid_type, {}),
        "is_allowed": is_material_allowed(material_id),
    }


def print_material_summary():
    """打印材料配置摘要"""
    print("\n" + "=" * 60)
    print("材料配置摘要")
    print("=" * 60)
    
    print(f"\n白名单材料 ({len(MATERIAL_WHITELIST)}种):")
    for mat in MATERIAL_WHITELIST:
        clay = get_clay_type(mat)
        acid = get_acid_type(mat)
        clay_cn = CLAY_PROPERTIES.get(clay, {}).get("chinese_name", "未知")
        acid_cn = ACID_PROPERTIES.get(acid, {}).get("chinese_name", "未知")
        print(f"  - {mat}: {clay_cn} + {acid_cn}")
    
    print(f"\n黑名单材料 ({len(MATERIAL_BLACKLIST)}种):")
    for mat in MATERIAL_BLACKLIST:
        print(f"  - {mat}")
    
    print("\n按黏土分类:")
    for clay, materials in MATERIAL_BY_CLAY.items():
        print(f"  - {clay}: {materials}")
    
    print("\n按酸体系分类:")
    for acid, materials in MATERIAL_BY_ACID.items():
        print(f"  - {acid}: {materials}")


# ============================================================
# 测试代码
# ============================================================

if __name__ == "__main__":
    print_material_summary()
    
    # 测试过滤功能
    test_samples = ["S8-3-2-1", "S60-2-2-1", "S14-1-1-1", "S12-1-1-1"]
    filtered = filter_samples_by_whitelist(test_samples)
    print(f"\n过滤测试:")
    print(f"  输入: {test_samples}")
    print(f"  输出: {filtered}")
    
    # 测试材料信息获取
    print(f"\nS8材料信息:")
    info = get_material_info("S8")
    print(f"  黏土类型: {info['clay_type']} ({info['clay_properties'].get('chinese_name', '')})")
    print(f"  酸类型: {info['acid_type']}")
    print(f"  孔径: {info['clay_properties'].get('pore_diameter_nm', 'N/A')} nm")
