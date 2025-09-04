"""Evaluation System for RAG Pipeline.

Provides comprehensive evaluation metrics for RAG system quality:
- Retrieval metrics (precision, recall, MRR, NDCG)
- Generation quality (faithfulness, relevance, coherence)
- End-to-end evaluation
- A/B testing framework
- Automated quality assessment
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics
import re

# For advanced evaluation metrics
try:
    import numpy as np
except ImportError:
    np = None

try:
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    cosine_similarity = None


@dataclass
class RetrievalEvaluation:
    """Evaluation results for retrieval performance."""
    query_id: str
    query_text: str
    retrieved_docs: List[str]
    relevant_docs: List[str]
    precision_at_k: Dict[int, float]
    recall_at_k: Dict[int, float]
    f1_at_k: Dict[int, float]
    mrr: float
    ndcg_at_k: Dict[int, float]
    map_score: float
    timestamp: datetime


@dataclass
class GenerationEvaluation:
    """Evaluation results for generation quality."""
    query_id: str
    query_text: str
    generated_response: str
    reference_response: Optional[str]
    retrieved_context: List[str]
    faithfulness_score: float
    relevance_score: float
    coherence_score: float
    groundedness_score: float
    context_utilization: float
    response_length: int
    timestamp: datetime


@dataclass
class EndToEndEvaluation:
    """End-to-end evaluation combining retrieval and generation."""
    query_id: str
    retrieval_eval: RetrievalEvaluation
    generation_eval: GenerationEvaluation
    overall_score: float
    user_satisfaction: Optional[float]
    task_completion: bool
    timestamp: datetime


class RetrievalEvaluator:
    """Evaluates retrieval performance using standard IR metrics."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def evaluate_retrieval(self, 
                          query_id: str,
                          query_text: str,
                          retrieved_docs: List[str],
                          relevant_docs: List[str],
                          k_values: List[int] = None) -> RetrievalEvaluation:
        """Evaluate retrieval performance for a single query."""
        k_values = k_values or [1, 3, 5, 10]
        
        # Calculate precision, recall, F1 at different k values
        precision_at_k = {}
        recall_at_k = {}
        f1_at_k = {}
        
        for k in k_values:
            retrieved_k = retrieved_docs[:k]
            relevant_retrieved = len(set(retrieved_k) & set(relevant_docs))
            
            precision = relevant_retrieved / len(retrieved_k) if retrieved_k else 0
            recall = relevant_retrieved / len(relevant_docs) if relevant_docs else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            precision_at_k[k] = precision
            recall_at_k[k] = recall
            f1_at_k[k] = f1
        
        # Calculate MRR (Mean Reciprocal Rank)
        mrr = self._calculate_mrr(retrieved_docs, relevant_docs)
        
        # Calculate NDCG at different k values
        ndcg_at_k = {}
        for k in k_values:
            ndcg_at_k[k] = self._calculate_ndcg(retrieved_docs[:k], relevant_docs)
        
        # Calculate MAP (Mean Average Precision)
        map_score = self._calculate_map(retrieved_docs, relevant_docs)
        
        return RetrievalEvaluation(
            query_id=query_id,
            query_text=query_text,
            retrieved_docs=retrieved_docs,
            relevant_docs=relevant_docs,
            precision_at_k=precision_at_k,
            recall_at_k=recall_at_k,
            f1_at_k=f1_at_k,
            mrr=mrr,
            ndcg_at_k=ndcg_at_k,
            map_score=map_score,
            timestamp=datetime.now()
        )
    
    def _calculate_mrr(self, retrieved_docs: List[str], relevant_docs: List[str]) -> float:
        """Calculate Mean Reciprocal Rank."""
        for i, doc in enumerate(retrieved_docs):
            if doc in relevant_docs:
                return 1.0 / (i + 1)
        return 0.0
    
    def _calculate_ndcg(self, retrieved_docs: List[str], relevant_docs: List[str]) -> float:
        """Calculate Normalized Discounted Cumulative Gain."""
        if not retrieved_docs or not relevant_docs:
            return 0.0
        
        # Simple binary relevance (1 if relevant, 0 if not)
        relevance_scores = [1 if doc in relevant_docs else 0 for doc in retrieved_docs]
        
        # Calculate DCG
        dcg = relevance_scores[0]
        for i in range(1, len(relevance_scores)):
            dcg += relevance_scores[i] / (np.log2(i + 1) if np else (i + 1))
        
        # Calculate IDCG (ideal DCG)
        ideal_relevance = sorted([1] * min(len(relevant_docs), len(retrieved_docs)), reverse=True)
        idcg = ideal_relevance[0] if ideal_relevance else 0
        for i in range(1, len(ideal_relevance)):
            idcg += ideal_relevance[i] / (np.log2(i + 1) if np else (i + 1))
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def _calculate_map(self, retrieved_docs: List[str], relevant_docs: List[str]) -> float:
        """Calculate Mean Average Precision."""
        if not relevant_docs:
            return 0.0
        
        precision_sum = 0.0
        relevant_count = 0
        
        for i, doc in enumerate(retrieved_docs):
            if doc in relevant_docs:
                relevant_count += 1
                precision_at_i = relevant_count / (i + 1)
                precision_sum += precision_at_i
        
        return precision_sum / len(relevant_docs) if relevant_docs else 0.0
    
    def evaluate_batch(self, 
                      queries_data: List[Dict[str, Any]],
                      k_values: List[int] = None) -> Dict[str, Any]:
        """Evaluate retrieval performance for multiple queries."""
        evaluations = []
        
        for query_data in queries_data:
            eval_result = self.evaluate_retrieval(
                query_id=query_data["query_id"],
                query_text=query_data["query_text"],
                retrieved_docs=query_data["retrieved_docs"],
                relevant_docs=query_data["relevant_docs"],
                k_values=k_values
            )
            evaluations.append(eval_result)
        
        # Aggregate results
        return self._aggregate_retrieval_results(evaluations, k_values or [1, 3, 5, 10])
    
    def _aggregate_retrieval_results(self, 
                                   evaluations: List[RetrievalEvaluation],
                                   k_values: List[int]) -> Dict[str, Any]:
        """Aggregate retrieval evaluation results."""
        if not evaluations:
            return {"total_queries": 0}
        
        # Aggregate metrics
        aggregated = {
            "total_queries": len(evaluations),
            "precision_at_k": {},
            "recall_at_k": {},
            "f1_at_k": {},
            "ndcg_at_k": {},
            "mrr": statistics.mean([e.mrr for e in evaluations]),
            "map": statistics.mean([e.map_score for e in evaluations]),
        }
        
        for k in k_values:
            aggregated["precision_at_k"][k] = statistics.mean(
                [e.precision_at_k.get(k, 0) for e in evaluations]
            )
            aggregated["recall_at_k"][k] = statistics.mean(
                [e.recall_at_k.get(k, 0) for e in evaluations]
            )
            aggregated["f1_at_k"][k] = statistics.mean(
                [e.f1_at_k.get(k, 0) for e in evaluations]
            )
            aggregated["ndcg_at_k"][k] = statistics.mean(
                [e.ndcg_at_k.get(k, 0) for e in evaluations]
            )
        
        return aggregated


class GenerationEvaluator:
    """Evaluates generation quality using various metrics."""
    
    def __init__(self, embedding_manager=None):
        self.logger = logging.getLogger(__name__)
        self.embedding_manager = embedding_manager
    
    def evaluate_generation(self,
                          query_id: str,
                          query_text: str,
                          generated_response: str,
                          retrieved_context: List[str],
                          reference_response: Optional[str] = None) -> GenerationEvaluation:
        """Evaluate generation quality for a single query."""
        
        # Calculate faithfulness (how well the response is grounded in context)
        faithfulness_score = self._calculate_faithfulness(generated_response, retrieved_context)
        
        # Calculate relevance (how well the response answers the query)
        relevance_score = self._calculate_relevance(query_text, generated_response)
        
        # Calculate coherence (internal consistency of the response)
        coherence_score = self._calculate_coherence(generated_response)
        
        # Calculate groundedness (how much the response relies on provided context)
        groundedness_score = self._calculate_groundedness(generated_response, retrieved_context)
        
        # Calculate context utilization (how well the context is used)
        context_utilization = self._calculate_context_utilization(generated_response, retrieved_context)
        
        return GenerationEvaluation(
            query_id=query_id,
            query_text=query_text,
            generated_response=generated_response,
            reference_response=reference_response,
            retrieved_context=retrieved_context,
            faithfulness_score=faithfulness_score,
            relevance_score=relevance_score,
            coherence_score=coherence_score,
            groundedness_score=groundedness_score,
            context_utilization=context_utilization,
            response_length=len(generated_response.split()),
            timestamp=datetime.now()
        )
    
    def _calculate_faithfulness(self, response: str, context: List[str]) -> float:
        """Calculate how faithful the response is to the provided context."""
        if not context or not response:
            return 0.0
        
        # Simple approach: check for factual consistency
        # In a real implementation, you might use more sophisticated NLI models
        
        context_text = " ".join(context).lower()
        response_lower = response.lower()
        
        # Extract key claims from response (simplified)
        sentences = re.split(r'[.!?]+', response)
        faithful_sentences = 0
        
        for sentence in sentences:
            sentence = sentence.strip().lower()
            if len(sentence) < 10:  # Skip very short sentences
                continue
            
            # Check if key terms from sentence appear in context
            words = sentence.split()
            key_words = [w for w in words if len(w) > 4]  # Focus on longer words
            
            if key_words:
                overlap = sum(1 for word in key_words if word in context_text)
                if overlap / len(key_words) > 0.3:  # At least 30% overlap
                    faithful_sentences += 1
        
        total_sentences = len([s for s in sentences if len(s.strip()) > 10])
        return faithful_sentences / total_sentences if total_sentences > 0 else 0.0
    
    def _calculate_relevance(self, query: str, response: str) -> float:
        """Calculate how relevant the response is to the query."""
        if not query or not response:
            return 0.0
        
        # Simple keyword-based relevance
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common stop words (simplified)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
        query_words = query_words - stop_words
        response_words = response_words - stop_words
        
        if not query_words:
            return 0.0
        
        # Calculate overlap
        overlap = len(query_words & response_words)
        return overlap / len(query_words)
    
    def _calculate_coherence(self, response: str) -> float:
        """Calculate internal coherence of the response."""
        if not response:
            return 0.0
        
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if len(sentences) < 2:
            return 1.0  # Single sentence is coherent by definition
        
        # Simple coherence metrics
        coherence_score = 0.0
        
        # Check for consistent terminology
        all_words = []
        for sentence in sentences:
            all_words.extend(sentence.lower().split())
        
        word_freq = defaultdict(int)
        for word in all_words:
            if len(word) > 4:  # Focus on content words
                word_freq[word] += 1
        
        # Reward repeated key terms (indicates consistency)
        repeated_terms = sum(1 for freq in word_freq.values() if freq > 1)
        coherence_score += min(repeated_terms / len(sentences), 0.5)
        
        # Check for logical flow (simplified)
        transition_words = ['however', 'therefore', 'furthermore', 'additionally', 'moreover', 'consequently']
        transition_count = sum(1 for sentence in sentences 
                             for word in transition_words 
                             if word in sentence.lower())
        coherence_score += min(transition_count / len(sentences), 0.3)
        
        # Penalize very short or very long sentences (indicates poor structure)
        avg_sentence_length = statistics.mean([len(s.split()) for s in sentences])
        if 10 <= avg_sentence_length <= 25:
            coherence_score += 0.2
        
        return min(coherence_score, 1.0)
    
    def _calculate_groundedness(self, response: str, context: List[str]) -> float:
        """Calculate how well the response is grounded in the provided context."""
        if not context or not response:
            return 0.0
        
        context_text = " ".join(context).lower()
        response_lower = response.lower()
        
        # Extract entities and key phrases from response
        response_words = response_lower.split()
        content_words = [w for w in response_words if len(w) > 3]
        
        if not content_words:
            return 0.0
        
        # Check how many content words appear in context
        grounded_words = sum(1 for word in content_words if word in context_text)
        
        return grounded_words / len(content_words)
    
    def _calculate_context_utilization(self, response: str, context: List[str]) -> float:
        """Calculate how well the available context is utilized."""
        if not context or not response:
            return 0.0
        
        response_lower = response.lower()
        utilized_contexts = 0
        
        for ctx in context:
            ctx_words = [w for w in ctx.lower().split() if len(w) > 4]
            if ctx_words:
                overlap = sum(1 for word in ctx_words if word in response_lower)
                if overlap / len(ctx_words) > 0.1:  # At least 10% of context words used
                    utilized_contexts += 1
        
        return utilized_contexts / len(context)
    
    def evaluate_batch(self, generation_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate generation quality for multiple queries."""
        evaluations = []
        
        for data in generation_data:
            eval_result = self.evaluate_generation(
                query_id=data["query_id"],
                query_text=data["query_text"],
                generated_response=data["generated_response"],
                retrieved_context=data["retrieved_context"],
                reference_response=data.get("reference_response")
            )
            evaluations.append(eval_result)
        
        return self._aggregate_generation_results(evaluations)
    
    def _aggregate_generation_results(self, evaluations: List[GenerationEvaluation]) -> Dict[str, Any]:
        """Aggregate generation evaluation results."""
        if not evaluations:
            return {"total_queries": 0}
        
        return {
            "total_queries": len(evaluations),
            "avg_faithfulness": statistics.mean([e.faithfulness_score for e in evaluations]),
            "avg_relevance": statistics.mean([e.relevance_score for e in evaluations]),
            "avg_coherence": statistics.mean([e.coherence_score for e in evaluations]),
            "avg_groundedness": statistics.mean([e.groundedness_score for e in evaluations]),
            "avg_context_utilization": statistics.mean([e.context_utilization for e in evaluations]),
            "avg_response_length": statistics.mean([e.response_length for e in evaluations]),
            "faithfulness_distribution": self._calculate_distribution([e.faithfulness_score for e in evaluations]),
            "relevance_distribution": self._calculate_distribution([e.relevance_score for e in evaluations]),
        }
    
    def _calculate_distribution(self, scores: List[float]) -> Dict[str, float]:
        """Calculate score distribution statistics."""
        if not scores:
            return {}
        
        return {
            "min": min(scores),
            "max": max(scores),
            "median": statistics.median(scores),
            "std": statistics.stdev(scores) if len(scores) > 1 else 0.0,
            "q25": statistics.quantiles(scores, n=4)[0] if len(scores) >= 4 else min(scores),
            "q75": statistics.quantiles(scores, n=4)[2] if len(scores) >= 4 else max(scores),
        }


class RAGEvaluator:
    """Main evaluation system for RAG pipeline."""
    
    def __init__(self, embedding_manager=None):
        self.logger = logging.getLogger(__name__)
        self.retrieval_evaluator = RetrievalEvaluator()
        self.generation_evaluator = GenerationEvaluator(embedding_manager)
        
        # Evaluation history
        self.evaluation_history = []
    
    def evaluate_end_to_end(self,
                           query_id: str,
                           query_text: str,
                           retrieved_docs: List[str],
                           relevant_docs: List[str],
                           generated_response: str,
                           retrieved_context: List[str],
                           reference_response: Optional[str] = None,
                           user_satisfaction: Optional[float] = None,
                           task_completion: Optional[bool] = None) -> EndToEndEvaluation:
        """Perform end-to-end evaluation of RAG system."""
        
        # Evaluate retrieval
        retrieval_eval = self.retrieval_evaluator.evaluate_retrieval(
            query_id=query_id,
            query_text=query_text,
            retrieved_docs=retrieved_docs,
            relevant_docs=relevant_docs
        )
        
        # Evaluate generation
        generation_eval = self.generation_evaluator.evaluate_generation(
            query_id=query_id,
            query_text=query_text,
            generated_response=generated_response,
            retrieved_context=retrieved_context,
            reference_response=reference_response
        )
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(retrieval_eval, generation_eval)
        
        end_to_end_eval = EndToEndEvaluation(
            query_id=query_id,
            retrieval_eval=retrieval_eval,
            generation_eval=generation_eval,
            overall_score=overall_score,
            user_satisfaction=user_satisfaction,
            task_completion=task_completion or False,
            timestamp=datetime.now()
        )
        
        # Store in history
        self.evaluation_history.append(end_to_end_eval)
        
        return end_to_end_eval
    
    def _calculate_overall_score(self, 
                               retrieval_eval: RetrievalEvaluation,
                               generation_eval: GenerationEvaluation) -> float:
        """Calculate overall RAG system score."""
        # Weighted combination of retrieval and generation metrics
        retrieval_score = (
            retrieval_eval.precision_at_k.get(5, 0) * 0.3 +
            retrieval_eval.recall_at_k.get(5, 0) * 0.2 +
            retrieval_eval.mrr * 0.3 +
            retrieval_eval.ndcg_at_k.get(5, 0) * 0.2
        )
        
        generation_score = (
            generation_eval.faithfulness_score * 0.3 +
            generation_eval.relevance_score * 0.3 +
            generation_eval.coherence_score * 0.2 +
            generation_eval.groundedness_score * 0.2
        )
        
        # Combine retrieval and generation (60% generation, 40% retrieval)
        overall_score = generation_score * 0.6 + retrieval_score * 0.4
        
        return min(max(overall_score, 0.0), 1.0)
    
    def run_evaluation_suite(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run comprehensive evaluation on test dataset."""
        start_time = time.time()
        
        self.logger.info(f"Starting evaluation suite with {len(test_data)} test cases")
        
        end_to_end_evaluations = []
        
        for i, test_case in enumerate(test_data):
            try:
                eval_result = self.evaluate_end_to_end(**test_case)
                end_to_end_evaluations.append(eval_result)
                
                if (i + 1) % 10 == 0:
                    self.logger.info(f"Completed {i + 1}/{len(test_data)} evaluations")
                    
            except Exception as e:
                self.logger.error(f"Error evaluating test case {i}: {str(e)}")
                continue
        
        evaluation_time = time.time() - start_time
        
        # Aggregate results
        results = self._aggregate_end_to_end_results(end_to_end_evaluations)
        results["evaluation_metadata"] = {
            "total_test_cases": len(test_data),
            "successful_evaluations": len(end_to_end_evaluations),
            "evaluation_time": evaluation_time,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(
            f"Evaluation suite completed: {len(end_to_end_evaluations)}/{len(test_data)} "
            f"successful evaluations in {evaluation_time:.2f} seconds"
        )
        
        return results
    
    def _aggregate_end_to_end_results(self, evaluations: List[EndToEndEvaluation]) -> Dict[str, Any]:
        """Aggregate end-to-end evaluation results."""
        if not evaluations:
            return {"total_evaluations": 0}
        
        # Extract retrieval and generation evaluations
        retrieval_evals = [e.retrieval_eval for e in evaluations]
        generation_evals = [e.generation_eval for e in evaluations]
        
        # Aggregate retrieval results
        retrieval_results = self.retrieval_evaluator._aggregate_retrieval_results(
            retrieval_evals, [1, 3, 5, 10]
        )
        
        # Aggregate generation results
        generation_results = self.generation_evaluator._aggregate_generation_results(
            generation_evals
        )
        
        # Overall statistics
        overall_scores = [e.overall_score for e in evaluations]
        user_satisfactions = [e.user_satisfaction for e in evaluations if e.user_satisfaction is not None]
        task_completions = [e.task_completion for e in evaluations]
        
        return {
            "total_evaluations": len(evaluations),
            "retrieval_performance": retrieval_results,
            "generation_performance": generation_results,
            "overall_performance": {
                "avg_score": statistics.mean(overall_scores),
                "min_score": min(overall_scores),
                "max_score": max(overall_scores),
                "median_score": statistics.median(overall_scores),
                "score_distribution": self.generation_evaluator._calculate_distribution(overall_scores)
            },
            "user_satisfaction": {
                "avg_satisfaction": statistics.mean(user_satisfactions) if user_satisfactions else None,
                "satisfaction_count": len(user_satisfactions)
            },
            "task_completion": {
                "completion_rate": sum(task_completions) / len(task_completions),
                "completed_tasks": sum(task_completions),
                "total_tasks": len(task_completions)
            }
        }
    
    def export_evaluation_results(self, file_path: str, include_history: bool = True):
        """Export evaluation results to file."""
        try:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_evaluations": len(self.evaluation_history)
            }
            
            if include_history and self.evaluation_history:
                # Convert evaluations to serializable format
                export_data["evaluation_history"] = [
                    {
                        "query_id": eval.query_id,
                        "overall_score": eval.overall_score,
                        "user_satisfaction": eval.user_satisfaction,
                        "task_completion": eval.task_completion,
                        "timestamp": eval.timestamp.isoformat(),
                        "retrieval_metrics": {
                            "precision_at_5": eval.retrieval_eval.precision_at_k.get(5, 0),
                            "recall_at_5": eval.retrieval_eval.recall_at_k.get(5, 0),
                            "mrr": eval.retrieval_eval.mrr,
                            "ndcg_at_5": eval.retrieval_eval.ndcg_at_k.get(5, 0)
                        },
                        "generation_metrics": {
                            "faithfulness": eval.generation_eval.faithfulness_score,
                            "relevance": eval.generation_eval.relevance_score,
                            "coherence": eval.generation_eval.coherence_score,
                            "groundedness": eval.generation_eval.groundedness_score
                        }
                    }
                    for eval in self.evaluation_history
                ]
                
                # Add aggregated statistics
                export_data["aggregated_results"] = self._aggregate_end_to_end_results(
                    self.evaluation_history
                )
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Evaluation results exported to {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error exporting evaluation results: {str(e)}")
            raise
    
    def generate_evaluation_report(self) -> str:
        """Generate human-readable evaluation report."""
        if not self.evaluation_history:
            return "No evaluation data available."
        
        results = self._aggregate_end_to_end_results(self.evaluation_history)
        
        report = f"""RAG System Evaluation Report
{'=' * 40}

Overall Performance:
- Total Evaluations: {results['total_evaluations']}
- Average Score: {results['overall_performance']['avg_score']:.3f}
- Score Range: {results['overall_performance']['min_score']:.3f} - {results['overall_performance']['max_score']:.3f}
- Median Score: {results['overall_performance']['median_score']:.3f}

Retrieval Performance:
- Precision@5: {results['retrieval_performance'].get('precision_at_k', {}).get(5, 0):.3f}
- Recall@5: {results['retrieval_performance'].get('recall_at_k', {}).get(5, 0):.3f}
- MRR: {results['retrieval_performance'].get('mrr', 0):.3f}
- NDCG@5: {results['retrieval_performance'].get('ndcg_at_k', {}).get(5, 0):.3f}

Generation Performance:
- Faithfulness: {results['generation_performance'].get('avg_faithfulness', 0):.3f}
- Relevance: {results['generation_performance'].get('avg_relevance', 0):.3f}
- Coherence: {results['generation_performance'].get('avg_coherence', 0):.3f}
- Groundedness: {results['generation_performance'].get('avg_groundedness', 0):.3f}

Task Completion:
- Completion Rate: {results['task_completion']['completion_rate']:.2%}
- Completed Tasks: {results['task_completion']['completed_tasks']}/{results['task_completion']['total_tasks']}

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report
    
    def clear_evaluation_history(self):
        """Clear evaluation history."""
        self.evaluation_history.clear()
        self.logger.info("Evaluation history cleared")