from typing import Dict, Any, List
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
import json

class PerformanceMonitor:
    """性能监控器 - 跟踪TOKEN使用和系统性能"""
    
    def __init__(self):
        self.token_usage = defaultdict(int)  # 按模型统计TOKEN使用
        self.llm_calls = defaultdict(int)    # 按模型统计LLM调用次数
        self.cache_hits = defaultdict(int)   # 缓存命中统计
        self.cache_misses = defaultdict(int) # 缓存未命中统计
        self.response_times = defaultdict(list)  # 响应时间统计
        self.error_counts = defaultdict(int)     # 错误统计
        
        # 时间窗口统计
        self.time_window = 3600  # 1小时窗口
        self.hourly_stats = deque(maxlen=24)  # 保留24小时数据
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 启动统计线程
        self._start_stats_thread()
    
    def _start_stats_thread(self):
        """启动统计线程"""
        def stats_collector():
            while True:
                time.sleep(3600)  # 每小时收集一次统计
                self._collect_hourly_stats()
        
        thread = threading.Thread(target=stats_collector, daemon=True)
        thread.start()
    
    def record_llm_call(self, model: str, tokens_used: int, response_time: float, success: bool = True):
        """记录LLM调用"""
        with self.lock:
            self.token_usage[model] += tokens_used
            self.llm_calls[model] += 1
            self.response_times[model].append(response_time)
            
            if not success:
                self.error_counts[model] += 1
    
    def record_cache_hit(self, cache_type: str):
        """记录缓存命中"""
        with self.lock:
            self.cache_hits[cache_type] += 1
    
    def record_cache_miss(self, cache_type: str):
        """记录缓存未命中"""
        with self.lock:
            self.cache_misses[cache_type] += 1
    
    def get_token_usage_stats(self) -> Dict[str, Any]:
        """获取TOKEN使用统计"""
        with self.lock:
            total_tokens = sum(self.token_usage.values())
            total_calls = sum(self.llm_calls.values())
            total_cache_hits = sum(self.cache_hits.values())
            total_cache_misses = sum(self.cache_misses.values())
            
            cache_hit_rate = total_cache_hits / (total_cache_hits + total_cache_misses) if (total_cache_hits + total_cache_misses) > 0 else 0
            
            # 计算节省的TOKEN
            estimated_tokens_saved = total_cache_hits * 1000  # 假设每次缓存命中节省1000 TOKEN
            
            return {
                "total_tokens_used": total_tokens,
                "total_llm_calls": total_calls,
                "tokens_per_call": total_tokens / total_calls if total_calls > 0 else 0,
                "cache_hits": total_cache_hits,
                "cache_misses": total_cache_misses,
                "cache_hit_rate": f"{cache_hit_rate:.2%}",
                "estimated_tokens_saved": estimated_tokens_saved,
                "tokens_saved_percentage": f"{(estimated_tokens_saved / (total_tokens + estimated_tokens_saved) * 100):.2%}" if (total_tokens + estimated_tokens_saved) > 0 else "0%",
                "by_model": dict(self.token_usage)
            }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        with self.lock:
            stats = {}
            for model, times in self.response_times.items():
                if times:
                    stats[model] = {
                        "avg_response_time": sum(times) / len(times),
                        "min_response_time": min(times),
                        "max_response_time": max(times),
                        "total_calls": self.llm_calls[model],
                        "error_count": self.error_counts[model],
                        "error_rate": f"{self.error_counts[model] / self.llm_calls[model] * 100:.2f}%" if self.llm_calls[model] > 0 else "0%"
                    }
            return stats
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            stats = {}
            for cache_type in set(list(self.cache_hits.keys()) + list(self.cache_misses.keys())):
                hits = self.cache_hits.get(cache_type, 0)
                misses = self.cache_misses.get(cache_type, 0)
                total = hits + misses
                hit_rate = hits / total if total > 0 else 0
                
                stats[cache_type] = {
                    "hits": hits,
                    "misses": misses,
                    "total": total,
                    "hit_rate": f"{hit_rate:.2%}"
                }
            return stats
    
    def _collect_hourly_stats(self):
        """收集小时统计"""
        with self.lock:
            hourly_stat = {
                "timestamp": datetime.now().isoformat(),
                "token_usage": dict(self.token_usage),
                "llm_calls": dict(self.llm_calls),
                "cache_hits": dict(self.cache_hits),
                "cache_misses": dict(self.cache_misses),
                "error_counts": dict(self.error_counts)
            }
            self.hourly_stats.append(hourly_stat)
    
    def get_hourly_stats(self) -> List[Dict[str, Any]]:
        """获取小时统计"""
        with self.lock:
            return list(self.hourly_stats)
    
    def get_realtime_stats(self) -> Dict[str, Any]:
        """获取实时统计"""
        return {
            "token_usage": self.get_token_usage_stats(),
            "performance": self.get_performance_stats(),
            "cache": self.get_cache_stats(),
            "hourly_stats": self.get_hourly_stats()
        }
    
    def reset_stats(self):
        """重置统计"""
        with self.lock:
            self.token_usage.clear()
            self.llm_calls.clear()
            self.cache_hits.clear()
            self.cache_misses.clear()
            self.response_times.clear()
            self.error_counts.clear()
            self.hourly_stats.clear()
    
    def export_stats(self, filepath: str):
        """导出统计到文件"""
        stats = self.get_realtime_stats()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

# 全局性能监控器实例
performance_monitor = PerformanceMonitor()