"""Observability and Metrics for RAG System.

Provides comprehensive monitoring, logging, and metrics collection
for the RAG pipeline including:
- Performance metrics (latency, throughput)
- Quality metrics (relevance, groundedness)
- System health monitoring
- Distributed tracing
- Custom dashboards
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
from contextlib import contextmanager


@dataclass
class QueryMetrics:
    """Metrics for a single query."""
    query_id: str
    query_text: str
    timestamp: datetime
    retrieval_time: float
    reranking_time: float
    total_time: float
    results_count: int
    k_requested: int
    retrieval_method: str
    fusion_method: Optional[str]
    avg_score: float
    top_score: float
    metadata_filter: Optional[Dict[str, Any]]
    success: bool
    error: Optional[str] = None


@dataclass
class IndexingMetrics:
    """Metrics for document indexing."""
    indexing_id: str
    timestamp: datetime
    documents_count: int
    chunks_count: int
    processing_time: float
    embedding_time: float
    indexing_time: float
    total_time: float
    avg_chunk_size: float
    success: bool
    errors: List[str]


@dataclass
class SystemMetrics:
    """System-level metrics."""
    timestamp: datetime
    memory_usage_mb: float
    cpu_usage_percent: float
    disk_usage_mb: float
    active_connections: int
    cache_hit_rate: float
    vector_store_size: int
    indexed_documents: int


class MetricsCollector:
    """Collects and aggregates RAG system metrics."""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.logger = logging.getLogger(__name__)
        
        # Metrics storage
        self.query_metrics: deque = deque(maxlen=max_history)
        self.indexing_metrics: deque = deque(maxlen=max_history)
        self.system_metrics: deque = deque(maxlen=max_history)
        
        # Real-time counters
        self.counters = defaultdict(int)
        self.timers = defaultdict(list)
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Performance thresholds
        self.thresholds = {
            "query_time_warning": 5.0,  # seconds
            "query_time_critical": 10.0,
            "indexing_time_warning": 60.0,
            "indexing_time_critical": 300.0,
            "memory_usage_warning": 1024,  # MB
            "memory_usage_critical": 2048,
            "error_rate_warning": 0.05,  # 5%
            "error_rate_critical": 0.10,  # 10%
        }
    
    def record_query_metrics(self, metrics: QueryMetrics):
        """Record metrics for a query."""
        with self._lock:
            self.query_metrics.append(metrics)
            
            # Update counters
            self.counters["total_queries"] += 1
            if metrics.success:
                self.counters["successful_queries"] += 1
            else:
                self.counters["failed_queries"] += 1
            
            # Update timers
            self.timers["query_times"].append(metrics.total_time)
            if len(self.timers["query_times"]) > 1000:
                self.timers["query_times"] = self.timers["query_times"][-1000:]
            
            # Check thresholds
            self._check_query_thresholds(metrics)
    
    def record_indexing_metrics(self, metrics: IndexingMetrics):
        """Record metrics for document indexing."""
        with self._lock:
            self.indexing_metrics.append(metrics)
            
            # Update counters
            self.counters["total_indexing_operations"] += 1
            self.counters["total_documents_indexed"] += metrics.documents_count
            self.counters["total_chunks_indexed"] += metrics.chunks_count
            
            if metrics.success:
                self.counters["successful_indexing_operations"] += 1
            else:
                self.counters["failed_indexing_operations"] += 1
            
            # Update timers
            self.timers["indexing_times"].append(metrics.total_time)
            if len(self.timers["indexing_times"]) > 100:
                self.timers["indexing_times"] = self.timers["indexing_times"][-100:]
            
            # Check thresholds
            self._check_indexing_thresholds(metrics)
    
    def record_system_metrics(self, metrics: SystemMetrics):
        """Record system-level metrics."""
        with self._lock:
            self.system_metrics.append(metrics)
            
            # Check system thresholds
            self._check_system_thresholds(metrics)
    
    def _check_query_thresholds(self, metrics: QueryMetrics):
        """Check query metrics against thresholds."""
        if metrics.total_time > self.thresholds["query_time_critical"]:
            self.logger.critical(
                f"Query {metrics.query_id} exceeded critical time threshold: "
                f"{metrics.total_time:.2f}s > {self.thresholds['query_time_critical']}s"
            )
        elif metrics.total_time > self.thresholds["query_time_warning"]:
            self.logger.warning(
                f"Query {metrics.query_id} exceeded warning time threshold: "
                f"{metrics.total_time:.2f}s > {self.thresholds['query_time_warning']}s"
            )
    
    def _check_indexing_thresholds(self, metrics: IndexingMetrics):
        """Check indexing metrics against thresholds."""
        if metrics.total_time > self.thresholds["indexing_time_critical"]:
            self.logger.critical(
                f"Indexing {metrics.indexing_id} exceeded critical time threshold: "
                f"{metrics.total_time:.2f}s > {self.thresholds['indexing_time_critical']}s"
            )
        elif metrics.total_time > self.thresholds["indexing_time_warning"]:
            self.logger.warning(
                f"Indexing {metrics.indexing_id} exceeded warning time threshold: "
                f"{metrics.total_time:.2f}s > {self.thresholds['indexing_time_warning']}s"
            )
    
    def _check_system_thresholds(self, metrics: SystemMetrics):
        """Check system metrics against thresholds."""
        if metrics.memory_usage_mb > self.thresholds["memory_usage_critical"]:
            self.logger.critical(
                f"Memory usage exceeded critical threshold: "
                f"{metrics.memory_usage_mb:.1f}MB > {self.thresholds['memory_usage_critical']}MB"
            )
        elif metrics.memory_usage_mb > self.thresholds["memory_usage_warning"]:
            self.logger.warning(
                f"Memory usage exceeded warning threshold: "
                f"{metrics.memory_usage_mb:.1f}MB > {self.thresholds['memory_usage_warning']}MB"
            )
    
    def get_query_statistics(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get query performance statistics."""
        with self._lock:
            metrics_list = list(self.query_metrics)
        
        if time_window:
            cutoff_time = datetime.now() - time_window
            metrics_list = [m for m in metrics_list if m.timestamp >= cutoff_time]
        
        if not metrics_list:
            return {"total_queries": 0}
        
        # Calculate statistics
        total_queries = len(metrics_list)
        successful_queries = sum(1 for m in metrics_list if m.success)
        failed_queries = total_queries - successful_queries
        
        query_times = [m.total_time for m in metrics_list if m.success]
        retrieval_times = [m.retrieval_time for m in metrics_list if m.success]
        reranking_times = [m.reranking_time for m in metrics_list if m.success and m.reranking_time]
        
        # Results statistics
        results_counts = [m.results_count for m in metrics_list if m.success]
        avg_scores = [m.avg_score for m in metrics_list if m.success and m.avg_score > 0]
        top_scores = [m.top_score for m in metrics_list if m.success and m.top_score > 0]
        
        return {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "success_rate": successful_queries / total_queries if total_queries > 0 else 0,
            "query_times": {
                "avg": sum(query_times) / len(query_times) if query_times else 0,
                "min": min(query_times) if query_times else 0,
                "max": max(query_times) if query_times else 0,
                "p50": self._percentile(query_times, 50) if query_times else 0,
                "p95": self._percentile(query_times, 95) if query_times else 0,
                "p99": self._percentile(query_times, 99) if query_times else 0,
            },
            "retrieval_times": {
                "avg": sum(retrieval_times) / len(retrieval_times) if retrieval_times else 0,
                "min": min(retrieval_times) if retrieval_times else 0,
                "max": max(retrieval_times) if retrieval_times else 0,
            },
            "reranking_times": {
                "avg": sum(reranking_times) / len(reranking_times) if reranking_times else 0,
                "min": min(reranking_times) if reranking_times else 0,
                "max": max(reranking_times) if reranking_times else 0,
            },
            "results_statistics": {
                "avg_results_count": sum(results_counts) / len(results_counts) if results_counts else 0,
                "avg_score": sum(avg_scores) / len(avg_scores) if avg_scores else 0,
                "avg_top_score": sum(top_scores) / len(top_scores) if top_scores else 0,
            },
            "retrieval_methods": self._count_by_field(metrics_list, "retrieval_method"),
            "fusion_methods": self._count_by_field(metrics_list, "fusion_method"),
        }
    
    def get_indexing_statistics(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get indexing performance statistics."""
        with self._lock:
            metrics_list = list(self.indexing_metrics)
        
        if time_window:
            cutoff_time = datetime.now() - time_window
            metrics_list = [m for m in metrics_list if m.timestamp >= cutoff_time]
        
        if not metrics_list:
            return {"total_operations": 0}
        
        # Calculate statistics
        total_operations = len(metrics_list)
        successful_operations = sum(1 for m in metrics_list if m.success)
        failed_operations = total_operations - successful_operations
        
        total_documents = sum(m.documents_count for m in metrics_list)
        total_chunks = sum(m.chunks_count for m in metrics_list)
        
        processing_times = [m.processing_time for m in metrics_list if m.success]
        embedding_times = [m.embedding_time for m in metrics_list if m.success]
        indexing_times = [m.indexing_time for m in metrics_list if m.success]
        total_times = [m.total_time for m in metrics_list if m.success]
        
        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "success_rate": successful_operations / total_operations if total_operations > 0 else 0,
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "avg_documents_per_operation": total_documents / total_operations if total_operations > 0 else 0,
            "avg_chunks_per_operation": total_chunks / total_operations if total_operations > 0 else 0,
            "processing_times": {
                "avg": sum(processing_times) / len(processing_times) if processing_times else 0,
                "min": min(processing_times) if processing_times else 0,
                "max": max(processing_times) if processing_times else 0,
            },
            "embedding_times": {
                "avg": sum(embedding_times) / len(embedding_times) if embedding_times else 0,
                "min": min(embedding_times) if embedding_times else 0,
                "max": max(embedding_times) if embedding_times else 0,
            },
            "indexing_times": {
                "avg": sum(indexing_times) / len(indexing_times) if indexing_times else 0,
                "min": min(indexing_times) if indexing_times else 0,
                "max": max(indexing_times) if indexing_times else 0,
            },
            "total_times": {
                "avg": sum(total_times) / len(total_times) if total_times else 0,
                "min": min(total_times) if total_times else 0,
                "max": max(total_times) if total_times else 0,
                "p95": self._percentile(total_times, 95) if total_times else 0,
            },
        }
    
    def get_system_statistics(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get system performance statistics."""
        with self._lock:
            metrics_list = list(self.system_metrics)
        
        if time_window:
            cutoff_time = datetime.now() - time_window
            metrics_list = [m for m in metrics_list if m.timestamp >= cutoff_time]
        
        if not metrics_list:
            return {"total_measurements": 0}
        
        # Calculate statistics
        memory_usage = [m.memory_usage_mb for m in metrics_list]
        cpu_usage = [m.cpu_usage_percent for m in metrics_list]
        disk_usage = [m.disk_usage_mb for m in metrics_list]
        cache_hit_rates = [m.cache_hit_rate for m in metrics_list]
        
        return {
            "total_measurements": len(metrics_list),
            "memory_usage_mb": {
                "avg": sum(memory_usage) / len(memory_usage) if memory_usage else 0,
                "min": min(memory_usage) if memory_usage else 0,
                "max": max(memory_usage) if memory_usage else 0,
                "current": memory_usage[-1] if memory_usage else 0,
            },
            "cpu_usage_percent": {
                "avg": sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0,
                "min": min(cpu_usage) if cpu_usage else 0,
                "max": max(cpu_usage) if cpu_usage else 0,
                "current": cpu_usage[-1] if cpu_usage else 0,
            },
            "disk_usage_mb": {
                "avg": sum(disk_usage) / len(disk_usage) if disk_usage else 0,
                "min": min(disk_usage) if disk_usage else 0,
                "max": max(disk_usage) if disk_usage else 0,
                "current": disk_usage[-1] if disk_usage else 0,
            },
            "cache_hit_rate": {
                "avg": sum(cache_hit_rates) / len(cache_hit_rates) if cache_hit_rates else 0,
                "min": min(cache_hit_rates) if cache_hit_rates else 0,
                "max": max(cache_hit_rates) if cache_hit_rates else 0,
                "current": cache_hit_rates[-1] if cache_hit_rates else 0,
            },
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a list of numbers."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower_index = int(index)
            upper_index = lower_index + 1
            weight = index - lower_index
            return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
    
    def _count_by_field(self, metrics_list: List[Any], field: str) -> Dict[str, int]:
        """Count occurrences of values in a field."""
        counts = defaultdict(int)
        for metric in metrics_list:
            value = getattr(metric, field, None)
            if value is not None:
                counts[str(value)] += 1
        return dict(counts)
    
    def export_metrics(self, file_path: str, time_window: Optional[timedelta] = None):
        """Export metrics to JSON file."""
        try:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "time_window": str(time_window) if time_window else "all_time",
                "query_statistics": self.get_query_statistics(time_window),
                "indexing_statistics": self.get_indexing_statistics(time_window),
                "system_statistics": self.get_system_statistics(time_window),
                "counters": dict(self.counters),
                "thresholds": self.thresholds,
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Metrics exported to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error exporting metrics: {str(e)}")
            raise
    
    def clear_metrics(self, older_than: Optional[timedelta] = None):
        """Clear metrics older than specified time."""
        with self._lock:
            if older_than:
                cutoff_time = datetime.now() - older_than
                
                # Filter metrics
                self.query_metrics = deque(
                    [m for m in self.query_metrics if m.timestamp >= cutoff_time],
                    maxlen=self.max_history
                )
                self.indexing_metrics = deque(
                    [m for m in self.indexing_metrics if m.timestamp >= cutoff_time],
                    maxlen=self.max_history
                )
                self.system_metrics = deque(
                    [m for m in self.system_metrics if m.timestamp >= cutoff_time],
                    maxlen=self.max_history
                )
                
                self.logger.info(f"Cleared metrics older than {older_than}")
            else:
                # Clear all metrics
                self.query_metrics.clear()
                self.indexing_metrics.clear()
                self.system_metrics.clear()
                self.counters.clear()
                self.timers.clear()
                
                self.logger.info("Cleared all metrics")


class PerformanceTracker:
    """Context manager for tracking operation performance."""
    
    def __init__(self, metrics_collector: MetricsCollector, operation_name: str):
        self.metrics_collector = metrics_collector
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.logger = logging.getLogger(__name__)
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"Started tracking: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        success = exc_type is None
        error_msg = str(exc_val) if exc_val else None
        
        self.logger.debug(
            f"Finished tracking: {self.operation_name} - "
            f"Duration: {duration:.3f}s, Success: {success}"
        )
        
        # Record in metrics collector
        self.metrics_collector.timers[f"{self.operation_name}_times"].append(duration)
        self.metrics_collector.counters[f"{self.operation_name}_total"] += 1
        
        if success:
            self.metrics_collector.counters[f"{self.operation_name}_success"] += 1
        else:
            self.metrics_collector.counters[f"{self.operation_name}_errors"] += 1
    
    def get_duration(self) -> Optional[float]:
        """Get operation duration if completed."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class RAGObservability:
    """Main observability system for RAG pipeline."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize metrics collector
        max_history = self.config.get("max_metrics_history", 10000)
        self.metrics_collector = MetricsCollector(max_history)
        
        # Setup logging
        self._setup_logging()
        
        # Performance tracking
        self.active_trackers = {}
        
        self.logger.info("RAG Observability system initialized")
    
    def _setup_logging(self):
        """Setup structured logging for RAG system."""
        log_level = self.config.get("log_level", "INFO")
        log_format = self.config.get(
            "log_format",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Configure root logger for RAG components
        rag_logger = logging.getLogger("rag")
        rag_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Add file handler if specified
        if "log_file" in self.config:
            file_handler = logging.FileHandler(self.config["log_file"], encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format))
            rag_logger.addHandler(file_handler)
    
    @contextmanager
    def track_operation(self, operation_name: str):
        """Context manager for tracking operation performance."""
        tracker = PerformanceTracker(self.metrics_collector, operation_name)
        try:
            with tracker:
                yield tracker
        finally:
            pass
    
    def record_query_metrics(self, **kwargs):
        """Record query metrics."""
        metrics = QueryMetrics(**kwargs)
        self.metrics_collector.record_query_metrics(metrics)
    
    def record_indexing_metrics(self, **kwargs):
        """Record indexing metrics."""
        metrics = IndexingMetrics(**kwargs)
        self.metrics_collector.record_indexing_metrics(metrics)
    
    def record_system_metrics(self, **kwargs):
        """Record system metrics."""
        metrics = SystemMetrics(**kwargs)
        self.metrics_collector.record_system_metrics(metrics)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        return {
            "timestamp": datetime.now().isoformat(),
            "query_stats": self.metrics_collector.get_query_statistics(),
            "indexing_stats": self.metrics_collector.get_indexing_statistics(),
            "system_stats": self.metrics_collector.get_system_statistics(),
            "recent_query_stats": self.metrics_collector.get_query_statistics(
                timedelta(hours=1)
            ),
            "recent_indexing_stats": self.metrics_collector.get_indexing_statistics(
                timedelta(hours=1)
            ),
            "counters": dict(self.metrics_collector.counters),
            "thresholds": self.metrics_collector.thresholds,
        }
    
    def export_dashboard(self, file_path: str):
        """Export dashboard data to file."""
        try:
            dashboard_data = self.get_dashboard_data()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Dashboard data exported to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error exporting dashboard: {str(e)}")
            raise
    
    def generate_performance_report(self, time_window: Optional[timedelta] = None) -> str:
        """Generate a human-readable performance report."""
        query_stats = self.metrics_collector.get_query_statistics(time_window)
        indexing_stats = self.metrics_collector.get_indexing_statistics(time_window)
        system_stats = self.metrics_collector.get_system_statistics(time_window)
        
        window_str = f"Last {time_window}" if time_window else "All time"
        
        report = f"""RAG System Performance Report - {window_str}
{'=' * 50}

Query Performance:
- Total queries: {query_stats.get('total_queries', 0)}
- Success rate: {query_stats.get('success_rate', 0):.2%}
- Average query time: {query_stats.get('query_times', {}).get('avg', 0):.3f}s
- 95th percentile: {query_stats.get('query_times', {}).get('p95', 0):.3f}s
- Average results: {query_stats.get('results_statistics', {}).get('avg_results_count', 0):.1f}

Indexing Performance:
- Total operations: {indexing_stats.get('total_operations', 0)}
- Success rate: {indexing_stats.get('success_rate', 0):.2%}
- Documents indexed: {indexing_stats.get('total_documents', 0)}
- Chunks indexed: {indexing_stats.get('total_chunks', 0)}
- Average indexing time: {indexing_stats.get('total_times', {}).get('avg', 0):.1f}s

System Performance:
- Memory usage: {system_stats.get('memory_usage_mb', {}).get('current', 0):.1f}MB
- CPU usage: {system_stats.get('cpu_usage_percent', {}).get('current', 0):.1f}%
- Cache hit rate: {system_stats.get('cache_hit_rate', {}).get('current', 0):.2%}

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report
    
    def cleanup(self):
        """Cleanup observability resources."""
        try:
            self.logger.info("Cleaning up RAG observability system")
            # Any cleanup operations would go here
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")