# -*- coding: utf-8 -*-
"""
多模型LLM客户端
支持：gpt-oss-120b, gpt-4o, deepseek-v3.1
"""
import requests
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime


class MultiModelClient:
    """多模型LLM客户端 - 通过OpenRouter API"""
    
    # 模型配置
    MODEL_CONFIGS = {
        'gpt-5.2': {
            'id': 'openai/gpt-5.2',
            'description': '最新顶级模型 - 深度机理分析首选',
            'max_tokens': 128000,
            'cost_per_1k_input': 0.005,
            'cost_per_1k_output': 0.015
        },
        'gpt-oss-120b': {
            'id': 'openai/gpt-oss-120b',
            'description': '主力分析模型',
            'max_tokens': 100000,
            'cost_per_1k_input': 0.0,
            'cost_per_1k_output': 0.0
        },
        'gpt-4o': {
            'id': 'openai/gpt-4o',
            'description': '批量处理模型',
            'max_tokens': 128000,
            'cost_per_1k_input': 0.0025,
            'cost_per_1k_output': 0.010
        },
        'deepseek-v3': {
            'id': 'deepseek/deepseek-chat',  # DeepSeek V3/V3.1
            'description': '关键验证模型',
            'max_tokens': 64000,
            'cost_per_1k_input': 0.00014,
            'cost_per_1k_output': 0.00028
        }
    }
    
    def __init__(
        self, 
        api_key: str,
        default_model: str = 'gpt-4o',
        base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    ):
        """
        初始化多模型客户端
        
        Args:
            api_key: OpenRouter API密钥
            default_model: 默认模型 (gpt-oss-120b/gpt-4o/deepseek-v3)
            base_url: API基础URL
        """
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url
        
        # 统计信息
        self.call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        
        # 模型调用次数
        self.model_usage = {
            'gpt-5.2': 0,
            'gpt-oss-120b': 0,
            'gpt-4o': 0,
            'deepseek-v3': 0
        }
        
    def get_model_id(self, model_key: str) -> str:
        """获取模型的完整ID"""
        if model_key in self.MODEL_CONFIGS:
            return self.MODEL_CONFIGS[model_key]['id']
        return model_key  # 如果是完整ID，直接返回
    
    def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        retry_times: int = 3,
        retry_delay: float = 2.0
    ) -> Dict[str, Any]:
        """
        生成文本
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            model: 使用的模型 (不指定则用default_model)
            temperature: 温度参数
            max_tokens: 最大输出token数
            retry_times: 重试次数
            retry_delay: 重试延迟（秒）
            
        Returns:
            包含content和usage的字典
        """
        model_key = model or self.default_model
        model_id = self.get_model_id(model_key)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/eis_analysis",
            "X-Title": "EIS Data Analysis"
        }
        
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        for attempt in range(retry_times):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # 提取内容
                    content = result['choices'][0]['message']['content']
                    
                    # 提取usage
                    usage = result.get('usage', {})
                    input_tokens = usage.get('prompt_tokens', 0)
                    output_tokens = usage.get('completion_tokens', 0)
                    
                    # 更新统计
                    self.call_count += 1
                    self.total_input_tokens += input_tokens
                    self.total_output_tokens += output_tokens
                    
                    # 计算成本
                    if model_key in self.MODEL_CONFIGS:
                        config = self.MODEL_CONFIGS[model_key]
                        cost = (input_tokens / 1000 * config['cost_per_1k_input'] +
                               output_tokens / 1000 * config['cost_per_1k_output'])
                        self.total_cost += cost
                        self.model_usage[model_key] = self.model_usage.get(model_key, 0) + 1
                    
                    return {
                        'content': content,
                        'usage': {
                            'input_tokens': input_tokens,
                            'output_tokens': output_tokens,
                            'total_tokens': input_tokens + output_tokens
                        },
                        'model': model_id,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    error_msg = f"API调用失败 (HTTP {response.status_code}): {response.text}"
                    print(f"[ERROR] {error_msg}")
                    
                    if attempt < retry_times - 1:
                        print(f"[INFO] 等待{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        return {
                            'error': error_msg,
                            'content': '',
                            'model': model_id
                        }
                        
            except Exception as e:
                error_msg = f"API调用异常: {str(e)}"
                print(f"[ERROR] {error_msg}")
                
                if attempt < retry_times - 1:
                    print(f"[INFO] 等待{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:
                    return {
                        'error': error_msg,
                        'content': '',
                        'model': model_id
                    }
        
        return {
            'error': '重试次数耗尽',
            'content': '',
            'model': model_id
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_calls': self.call_count,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_cost_usd': self.total_cost,
            'model_usage': self.model_usage,
            'avg_input_tokens': self.total_input_tokens / max(self.call_count, 1),
            'avg_output_tokens': self.total_output_tokens / max(self.call_count, 1)
        }
    
    def print_statistics(self):
        """打印统计信息"""
        stats = self.get_statistics()
        
        print("\n" + "="*80)
        print("LLM调用统计")
        print("="*80)
        print(f"总调用次数: {stats['total_calls']}")
        print(f"总输入tokens: {stats['total_input_tokens']:,}")
        print(f"总输出tokens: {stats['total_output_tokens']:,}")
        print(f"总成本: ${stats['total_cost_usd']:.4f}")
        print()
        print("模型使用情况:")
        for model, count in stats['model_usage'].items():
            if count > 0:
                print(f"  - {model}: {count}次")
        print()
        print(f"平均输入tokens: {stats['avg_input_tokens']:.0f}")
        print(f"平均输出tokens: {stats['avg_output_tokens']:.0f}")
        print("="*80)


def test_multi_model_client():
    """测试多模型客户端"""
    import os
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("[ERROR] 未设置OPENROUTER_API_KEY环境变量")
        return
    
    client = MultiModelClient(api_key=api_key, default_model='gpt-4o')
    
    test_prompt = "请用一句话介绍你自己。"
    
    # 测试三个模型
    models = ['gpt-oss-120b', 'gpt-4o', 'deepseek-v3']
    
    for model in models:
        print(f"\n测试模型: {model}")
        print("-" * 60)
        
        result = client.generate(
            system_prompt="你是一个AI助手。",
            user_message=test_prompt,
            model=model,
            max_tokens=100
        )
        
        if 'error' in result:
            print(f"[ERROR] {result['error']}")
        else:
            print(f"[OK] 响应: {result['content'][:200]}")
            print(f"[OK] Tokens: 输入={result['usage']['input_tokens']}, "
                  f"输出={result['usage']['output_tokens']}")
    
    # 打印统计
    client.print_statistics()


if __name__ == '__main__':
    test_multi_model_client()

