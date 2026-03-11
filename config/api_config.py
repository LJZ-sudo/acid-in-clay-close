# -*- coding: utf-8 -*-
"""
API配置文件
包含OpenRouter API密钥和模型配置

更新时间: 2026-01-11
"""

# ============================================================================
# OpenRouter API配置
# ============================================================================

import os

OPENROUTER_CONFIG = {
    # API密钥:
    # 1. GitHub版本中不再内置真实密钥
    # 2. 请通过环境变量 OPENROUTER_API_KEY 提供
    'api_key': os.environ.get('OPENROUTER_API_KEY', ''),
    
    # API端点
    'base_url': 'https://openrouter.ai/api/v1/chat/completions',
    
    # 默认模型 - 使用Claude Sonnet 4 (GPT-5.x配额不足)
    'default_model': 'anthropic/claude-sonnet-4',
    
    # 请求头
    'headers': {
        'HTTP-Referer': 'https://github.com/eis-data-analysis',
        'X-Title': 'EIS Data Analysis - Phase 2 Deep Analysis'
    }
}

# ============================================================================
# GPT-5.2 模型配置 (深度机理分析首选)
# ============================================================================

GPT52_CONFIG = {
    'model_id': 'openai/gpt-5.2',
    'description': '最新顶级模型 - 深度机理分析首选',
    
    # 生成参数 (更新于 2026-01-26)
    'temperature': 0.6,          # 较低温度保证科学准确性
    'max_tokens': 65536,         # GPT-5.2支持最大128K输出，设置为64K保证完整输出
    'top_p': 1.0,
    'frequency_penalty': 0.0,
    'presence_penalty': 0.0,
    
    # 上下文长度
    'context_length': 400000,    # GPT-5.2支持400K上下文
    'max_output_tokens': 128000, # 最大输出tokens
    
    # 成本估算 (每1M tokens, USD) - 2026价格
    'cost_per_1m_input': 1.75,
    'cost_per_1m_output': 14.0
}

# ============================================================================
# Claude Opus 4.5 模型配置 (深度分析推荐)
# ============================================================================

OPUS45_CONFIG = {
    'model_id': 'anthropic/claude-opus-4.5',
    'description': 'Anthropic前沿推理模型 - 复杂分析任务首选',
    
    # 生成参数
    'temperature': 0.5,          # 较低温度保证科学准确性
    'max_tokens': 32000,         # Opus 4.5支持大输出
    'top_p': 1.0,
    
    # 上下文长度
    'context_length': 200000,    # 200K上下文
    
    # 成本估算 (每1M tokens, USD)
    'cost_per_1m_input': 5.0,
    'cost_per_1m_output': 25.0,
    
    # 特殊参数: verbosity控制token效率 (low/medium/high)
    'verbosity': 'high',  # 深度分析使用high
}

# ============================================================================
# Claude Sonnet 4 模型配置 (批量任务推荐)
# ============================================================================

SONNET4_CONFIG = {
    'model_id': 'anthropic/claude-sonnet-4',
    'description': 'Claude Sonnet 4 - 批量任务高效选择',
    
    # 生成参数
    'temperature': 0.5,
    'max_tokens': 8000,
    'top_p': 1.0,
    
    # 上下文长度
    'context_length': 200000,
    
    # 成本估算 (每1M tokens, USD)
    'cost_per_1m_input': 3.0,
    'cost_per_1m_output': 15.0,
}

# ============================================================================
# 备选模型配置
# ============================================================================

BACKUP_MODELS = {
    'gpt-4o': {
        'model_id': 'openai/gpt-4o',
        'temperature': 0.7,
        'max_tokens': 8000
    },
    'deepseek-v3': {
        'model_id': 'deepseek/deepseek-chat',
        'temperature': 0.7,
        'max_tokens': 8000
    },
    'gemini-flash': {
        'model_id': 'google/gemini-2.0-flash-001',
        'temperature': 0.7,
        'max_tokens': 8000
    }
}

# ============================================================================
# 辅助函数
# ============================================================================

def get_api_key():
    """获取API密钥"""
    # 优先使用环境变量
    env_key = os.environ.get('OPENROUTER_API_KEY')
    if env_key:
        return env_key
    # GitHub版本不再回退到硬编码真实密钥
    return OPENROUTER_CONFIG['api_key']


def get_model_config(model_name: str = 'gpt-5.2') -> dict:
    """获取模型配置"""
    if model_name == 'gpt-5.2':
        return GPT52_CONFIG
    elif model_name in BACKUP_MODELS:
        return BACKUP_MODELS[model_name]
    else:
        return GPT52_CONFIG  # 默认返回GPT-5.2配置


# ============================================================================
# 测试
# ============================================================================

if __name__ == '__main__':
    print("OpenRouter API配置")
    print("=" * 60)
    key = OPENROUTER_CONFIG['api_key']
    masked = f"{key[:20]}..." if key else "<EMPTY: use OPENROUTER_API_KEY>"
    print(f"API Key: {masked}")
    print(f"默认模型: {OPENROUTER_CONFIG['default_model']}")
    print()
    print("GPT-5.2配置:")
    for key, value in GPT52_CONFIG.items():
        print(f"  {key}: {value}")
