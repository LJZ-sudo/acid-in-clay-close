# -*- coding: utf-8 -*-
"""
Phase 1 性能优化和调试工具
"""
import time
import psutil
import numpy as np
from typing import Dict, List, Callable, Any
from functools import wraps
import cProfile
import pstats
import io
from contextlib import contextmanager
import logging

class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self):
        self.profiles = {}
        self.benchmarks = {}
        self.logger = logging.getLogger(__name__)
    
    def profile_function(self, func_name: str = None):
        """函数性能分析装饰器"""
        def decorator(func):
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 内存使用监控
                process = psutil.Process()
                memory_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # 时间监控
                start_time = time.time()
                
                # 执行函数
                result = func(*args, **kwargs)
                
                # 记录性能指标
                execution_time = time.time() - start_time
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_delta = memory_after - memory_before
                
                # 存储性能数据
                if name not in self.profiles:
                    self.profiles[name] = []
                
                self.profiles[name].append({
                    'execution_time': execution_time,
                    'memory_before': memory_before,
                    'memory_after': memory_after,
                    'memory_delta': memory_delta,
                    'timestamp': time.time()
                })
                
                return result
            
            return wrapper
        return decorator
    
    @contextmanager
    def profile_block(self, block_name: str):
        """代码块性能分析上下文管理器"""
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024
        start_time = time.time()
        
        try:
            yield
        finally:
            execution_time = time.time() - start_time
            memory_after = process.memory_info().rss / 1024 / 1024
            memory_delta = memory_after - memory_before
            
            if block_name not in self.profiles:
                self.profiles[block_name] = []
            
            self.profiles[block_name].append({
                'execution_time': execution_time,
                'memory_before': memory_before,
                'memory_after': memory_after,
                'memory_delta': memory_delta,
                'timestamp': time.time()
            })
    
    def detailed_profile(self, func: Callable, *args, **kwargs):
        """详细的函数性能分析"""
        pr = cProfile.Profile()
        pr.enable()
        
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        pr.disable()
        
        # 生成性能报告
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats()
        
        return {
            'result': result,
            'execution_time': execution_time,
            'profile_report': s.getvalue()
        }
    
    def get_performance_summary(self) -> Dict:
        """获取性能摘要"""
        summary = {}
        
        for func_name, records in self.profiles.items():
            if not records:
                continue
            
            times = [r['execution_time'] for r in records]
            memories = [r['memory_delta'] for r in records]
            
            summary[func_name] = {
                'call_count': len(records),
                'avg_time': np.mean(times),
                'min_time': np.min(times),
                'max_time': np.max(times),
                'std_time': np.std(times),
                'total_time': np.sum(times),
                'avg_memory_delta': np.mean(memories),
                'max_memory_delta': np.max(memories),
                'last_call': max(r['timestamp'] for r in records)
            }
        
        return summary
    
    def generate_performance_report(self) -> str:
        """生成性能报告"""
        summary = self.get_performance_summary()
        
        report = [
            "Phase 1 性能分析报告",
            "=" * 50,
            f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"监控函数数量: {len(summary)}",
            ""
        ]
        
        # 按平均执行时间排序
        sorted_funcs = sorted(summary.items(), key=lambda x: x[1]['avg_time'], reverse=True)
        
        for func_name, stats in sorted_funcs:
            report.extend([
                f"函数: {func_name}",
                f"  调用次数: {stats['call_count']}",
                f"  平均时间: {stats['avg_time']:.4f}s",
                f"  最小时间: {stats['min_time']:.4f}s",
                f"  最大时间: {stats['max_time']:.4f}s",
                f"  标准差: {stats['std_time']:.4f}s",
                f"  总时间: {stats['total_time']:.4f}s",
                f"  平均内存增量: {stats['avg_memory_delta']:.2f}MB",
                f"  最大内存增量: {stats['max_memory_delta']:.2f}MB",
                ""
            ])
        
        return "\n".join(report)
    
    def clear_profiles(self):
        """清除性能数据"""
        self.profiles.clear()

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.profiler = PerformanceProfiler()
        self.optimization_suggestions = []
    
    def optimize_numpy_operations(self):
        """优化NumPy操作"""
        suggestions = []
        
        # 检查NumPy配置
        try:
            import numpy as np
            config = np.__config__.show()
            
            # 检查BLAS库
            if 'mkl' not in str(config).lower():
                suggestions.append({
                    'type': 'numpy_optimization',
                    'priority': 'high',
                    'suggestion': '建议安装Intel MKL优化的NumPy版本以提升线性代数运算性能',
                    'command': 'pip install numpy[mkl] 或 conda install mkl'
                })
            
        except Exception as e:
            suggestions.append({
                'type': 'numpy_check',
                'priority': 'medium',
                'suggestion': f'无法检查NumPy配置: {str(e)}'
            })
        
        return suggestions
    
    def optimize_memory_usage(self, target_functions: List[str] = None):
        """内存使用优化建议"""
        suggestions = []
        summary = self.profiler.get_performance_summary()
        
        if target_functions:
            summary = {k: v for k, v in summary.items() if k in target_functions}
        
        for func_name, stats in summary.items():
            # 检查内存使用
            if stats['max_memory_delta'] > 500:  # 超过500MB
                suggestions.append({
                    'type': 'memory_optimization',
                    'priority': 'high',
                    'function': func_name,
                    'suggestion': f'函数 {func_name} 内存使用过高 ({stats["max_memory_delta"]:.1f}MB)，建议使用流式处理或分块计算',
                    'current_memory': stats['max_memory_delta']
                })
            
            elif stats['avg_memory_delta'] > 100:  # 平均超过100MB
                suggestions.append({
                    'type': 'memory_optimization',
                    'priority': 'medium',
                    'function': func_name,
                    'suggestion': f'函数 {func_name} 平均内存使用较高 ({stats["avg_memory_delta"]:.1f}MB)，建议优化数据结构',
                    'current_memory': stats['avg_memory_delta']
                })
        
        return suggestions
    
    def optimize_execution_time(self, time_threshold: float = 5.0):
        """执行时间优化建议"""
        suggestions = []
        summary = self.profiler.get_performance_summary()
        
        for func_name, stats in summary.items():
            if stats['avg_time'] > time_threshold:
                suggestions.append({
                    'type': 'time_optimization',
                    'priority': 'high',
                    'function': func_name,
                    'suggestion': f'函数 {func_name} 执行时间过长 ({stats["avg_time"]:.2f}s)，建议并行化或算法优化',
                    'current_time': stats['avg_time'],
                    'call_count': stats['call_count']
                })
            
            # 检查时间变异性
            if stats['std_time'] / stats['avg_time'] > 0.5:  # 变异系数>50%
                suggestions.append({
                    'type': 'time_stability',
                    'priority': 'medium',
                    'function': func_name,
                    'suggestion': f'函数 {func_name} 执行时间不稳定 (CV={stats["std_time"]/stats["avg_time"]:.2f})，建议检查输入数据或算法稳定性',
                    'coefficient_of_variation': stats['std_time'] / stats['avg_time']
                })
        
        return suggestions
    
    def suggest_parallel_optimization(self):
        """并行化优化建议"""
        suggestions = []
        
        # 检查CPU核心数
        cpu_count = psutil.cpu_count()
        logical_cpu_count = psutil.cpu_count(logical=True)
        
        suggestions.append({
            'type': 'parallel_info',
            'priority': 'info',
            'suggestion': f'系统有 {cpu_count} 个物理核心，{logical_cpu_count} 个逻辑核心',
            'physical_cores': cpu_count,
            'logical_cores': logical_cpu_count
        })
        
        # 检查可并行化的函数
        summary = self.profiler.get_performance_summary()
        
        parallel_candidates = []
        for func_name, stats in summary.items():
            # 执行时间长且调用次数多的函数适合并行化
            if stats['avg_time'] > 1.0 and stats['call_count'] > 1:
                parallel_candidates.append({
                    'function': func_name,
                    'avg_time': stats['avg_time'],
                    'call_count': stats['call_count'],
                    'total_time': stats['total_time']
                })
        
        # 按总时间排序
        parallel_candidates.sort(key=lambda x: x['total_time'], reverse=True)
        
        for candidate in parallel_candidates[:3]:  # 前3个候选
            suggestions.append({
                'type': 'parallel_optimization',
                'priority': 'medium',
                'function': candidate['function'],
                'suggestion': f'函数 {candidate["function"]} 适合并行化优化 (总时间: {candidate["total_time"]:.2f}s)',
                'potential_speedup': min(cpu_count, candidate['call_count'])
            })
        
        return suggestions
    
    def generate_optimization_report(self) -> str:
        """生成优化建议报告"""
        # 收集所有优化建议
        all_suggestions = []
        all_suggestions.extend(self.optimize_numpy_operations())
        all_suggestions.extend(self.optimize_memory_usage())
        all_suggestions.extend(self.optimize_execution_time())
        all_suggestions.extend(self.suggest_parallel_optimization())
        
        # 按优先级排序
        priority_order = {'high': 0, 'medium': 1, 'low': 2, 'info': 3}
        all_suggestions.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        report = [
            "Phase 1 性能优化建议报告",
            "=" * 50,
            f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"建议总数: {len(all_suggestions)}",
            ""
        ]
        
        # 按优先级分组
        for priority in ['high', 'medium', 'low', 'info']:
            priority_suggestions = [s for s in all_suggestions if s['priority'] == priority]
            if not priority_suggestions:
                continue
            
            priority_names = {
                'high': '高优先级',
                'medium': '中优先级', 
                'low': '低优先级',
                'info': '信息'
            }
            
            report.extend([
                f"{priority_names[priority]} ({len(priority_suggestions)}项):",
                "-" * 30
            ])
            
            for i, suggestion in enumerate(priority_suggestions, 1):
                report.extend([
                    f"{i}. {suggestion['suggestion']}",
                    f"   类型: {suggestion['type']}",
                ])
                
                # 添加额外信息
                if 'function' in suggestion:
                    report.append(f"   函数: {suggestion['function']}")
                if 'current_time' in suggestion:
                    report.append(f"   当前时间: {suggestion['current_time']:.2f}s")
                if 'current_memory' in suggestion:
                    report.append(f"   当前内存: {suggestion['current_memory']:.1f}MB")
                if 'command' in suggestion:
                    report.append(f"   执行命令: {suggestion['command']}")
                
                report.append("")
        
        return "\n".join(report)

def benchmark_phase1_modules():
    """Phase 1模块基准测试"""
    profiler = PerformanceProfiler()
    optimizer = PerformanceOptimizer()
    optimizer.profiler = profiler
    
    # 生成测试数据
    freq = np.logspace(-2, 6, 60)
    omega = 2 * np.pi * freq
    Rs, R1, C1 = 100, 1000, 1e-9
    Z = Rs + R1 / (1 + 1j * omega * R1 * C1)
    zreal, zimag = Z.real, Z.imag
    
    print("开始Phase 1模块基准测试...")
    print("=" * 50)
    
    # 测试模量谱分析
    try:
        from phase1.core.modulus_analysis import ModulusAnalyzer
        modulus_analyzer = ModulusAnalyzer()
        
        with profiler.profile_block("modulus_analysis_total"):
            modulus_result = modulus_analyzer.compute_modulus_spectrum(freq, zreal, zimag)
            peaks = modulus_analyzer.find_modulus_peaks(modulus_result['freq'], modulus_result['M_imag'])
        
        print(f"✓ 模量谱分析完成 - 检测到 {len(peaks)} 个峰")
        
    except Exception as e:
        print(f"✗ 模量谱分析失败: {str(e)}")
    
    # 测试DRT分析
    try:
        from phase1.core.drt_analysis import DRTAnalyzer
        drt_analyzer = DRTAnalyzer()
        
        with profiler.profile_block("drt_analysis_total"):
            drt_result = drt_analyzer.compute_drt_distribution(freq, zreal, zimag)
        
        print(f"✓ DRT分析完成 - R²={drt_result['fit_quality']['r_squared']:.4f}")
        
    except Exception as e:
        print(f"✗ DRT分析失败: {str(e)}")
    
    # 测试K-K验证
    try:
        from phase1.core.kk_validation import KKValidator
        kk_validator = KKValidator()
        
        with profiler.profile_block("kk_validation_total"):
            kk_result = kk_validator.validate_consistency(freq, zreal, zimag)
        
        print(f"✓ K-K验证完成 - {'通过' if kk_result['passed'] else '未通过'}")
        
    except Exception as e:
        print(f"✗ K-K验证失败: {str(e)}")
    
    # 测试等效电路选择
    try:
        from phase1.core.equivalent_circuit_selector import EquivalentCircuitSelector
        circuit_selector = EquivalentCircuitSelector()
        
        with profiler.profile_block("circuit_selection_total"):
            circuit_result = circuit_selector.select_best_circuit(freq, zreal, zimag, max_models=3)
        
        if circuit_result['status'] == 'success':
            print(f"✓ 电路选择完成 - 最佳模型: {circuit_result['best_model']['name']}")
        else:
            print(f"✗ 电路选择失败: {circuit_result.get('message', '未知错误')}")
        
    except Exception as e:
        print(f"✗ 电路选择失败: {str(e)}")
    
    # 生成性能报告
    print("\n" + "=" * 50)
    print("性能分析报告:")
    print("=" * 50)
    print(profiler.generate_performance_report())
    
    print("\n" + "=" * 50)
    print("优化建议报告:")
    print("=" * 50)
    print(optimizer.generate_optimization_report())
    
    return profiler, optimizer

if __name__ == "__main__":
    # 运行基准测试
    profiler, optimizer = benchmark_phase1_modules()
    
    # 保存报告
    with open("phase1_performance_report.txt", "w", encoding="utf-8") as f:
        f.write("Phase 1 性能分析报告\n")
        f.write("=" * 50 + "\n")
        f.write(profiler.generate_performance_report())
        f.write("\n\n")
        f.write("Phase 1 优化建议报告\n")
        f.write("=" * 50 + "\n")
        f.write(optimizer.generate_optimization_report())
    
    print("\n📊 报告已保存到 phase1_performance_report.txt")
