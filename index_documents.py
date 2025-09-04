#!/usr/bin/env python3
"""Document indexing script for RAG System.

This script provides functionality to:
1. Index individual documents or directories
2. Batch process multiple documents
3. Monitor indexing progress
4. Handle different document types
5. Provide indexing statistics
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from rag.config import RAGConfig
    from rag.rag_pipeline import RAGPipeline
    from rag.observability import RAGObservability
except ImportError:
    print("RAG modules not found. Please run setup_rag.py first.")
    sys.exit(1)


class DocumentIndexer:
    """Document indexing manager for RAG system."""
    
    def __init__(self, config_path: Optional[str] = None, filter_by_prefix: bool = True):
        self.project_root = Path(__file__).parent
        self.config_path = config_path or self.project_root / "rag_config.json"
        self.filter_by_prefix = filter_by_prefix
        
        # Load configuration
        if self.config_path.exists():
            self.config = RAGConfig.load_from_file(str(self.config_path))
        else:
            print(f"Configuration file not found: {self.config_path}")
            print("Please run setup_rag.py first to create the configuration.")
            sys.exit(1)
        
        # Initialize RAG pipeline
        try:
            self.rag_pipeline = RAGPipeline(self.config)
            self.observability = RAGObservability()
        except Exception as e:
            print(f"Failed to initialize RAG pipeline: {str(e)}")
            sys.exit(1)
        
        self.indexing_stats = {
            "total_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "total_chunks": 0,
            "start_time": None,
            "end_time": None,
            "errors": []
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Log indexing messages."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return [
            '.txt', '.md', '.pdf', '.docx', '.doc',
            '.html', '.htm', '.rtf', '.odt'
        ]
    
    def find_documents(self, path: str, recursive: bool = True) -> List[str]:
        """Find all supported documents in a path."""
        path_obj = Path(path)
        documents = []
        supported_extensions = self.get_supported_extensions()
        
        if path_obj.is_file():
            if path_obj.suffix.lower() in supported_extensions:
                documents.append(str(path_obj))
            else:
                self.log(f"Unsupported file type: {path_obj.suffix}", "WARNING")
        
        elif path_obj.is_dir():
            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"
            
            for ext in supported_extensions:
                documents.extend(str(p) for p in path_obj.glob(f"{pattern}{ext}"))
        
        else:
            self.log(f"Path not found: {path}", "ERROR")
        
        # Filter documents by required prefixes if enabled
        if self.filter_by_prefix:
            filtered_documents = self.filter_documents_by_prefix(documents)
        else:
            filtered_documents = documents
            self.log(f"Found {len(documents)} documents (prefix filtering disabled)")
        
        return sorted(filtered_documents)
    
    def filter_documents_by_prefix(self, documents: List[str]) -> List[str]:
        """Filter documents by required filename prefixes."""
        required_prefixes = ['INI', 'IXP', 'DEC', 'ROP', 'IFS']
        filtered_documents = []
        excluded_documents = []
        
        for doc_path in documents:
            filename = Path(doc_path).name.upper()  # Convert to uppercase for comparison
            if any(filename.startswith(prefix) for prefix in required_prefixes):
                filtered_documents.append(doc_path)
            else:
                excluded_documents.append(doc_path)
        
        if excluded_documents:
            self.log(f"Filtered out {len(excluded_documents)} documents without required prefixes (INI, IXP, DEC, ROP, IFS)")
            for excluded_doc in excluded_documents[:3]:  # Show first 3 excluded files
                self.log(f"   - Excluded: {Path(excluded_doc).name}", "INFO")
            if len(excluded_documents) > 3:
                self.log(f"   ... and {len(excluded_documents) - 3} more files excluded", "INFO")
        
        self.log(f"Found {len(filtered_documents)} documents with required prefixes")
        return filtered_documents
    
    def index_single_document(self, file_path: str) -> Dict:
        """Index a single document."""
        self.log(f"Indexing: {file_path}")
        
        try:
            with self.observability.track_operation("document_indexing") as tracker:
                result = self.rag_pipeline.index_documents([file_path])
            
            if result["success"]:
                self.log(f"✓ Successfully indexed {file_path}")
                self.log(f"  Chunks created: {result['chunks_indexed']}")
                self.log(f"  Processing time: {tracker.get_duration():.2f}s")
                
                self.indexing_stats["successful_files"] += 1
                self.indexing_stats["total_chunks"] += result["chunks_indexed"]
            else:
                error_msg = result.get("error", "Unknown error")
                self.log(f"✗ Failed to index {file_path}: {error_msg}", "ERROR")
                self.indexing_stats["failed_files"] += 1
                self.indexing_stats["errors"].append({
                    "file": file_path,
                    "error": error_msg
                })
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.log(f"✗ Exception while indexing {file_path}: {error_msg}", "ERROR")
            self.indexing_stats["failed_files"] += 1
            self.indexing_stats["errors"].append({
                "file": file_path,
                "error": error_msg
            })
            return {"success": False, "error": error_msg}
    
    def index_documents_batch(self, file_paths: List[str], batch_size: int = 5) -> Dict:
        """Index documents in batches."""
        self.log(f"Starting batch indexing of {len(file_paths)} documents")
        self.log(f"Batch size: {batch_size}")
        
        self.indexing_stats["start_time"] = datetime.now()
        self.indexing_stats["total_files"] = len(file_paths)
        
        # Process in batches
        for i in range(0, len(file_paths), batch_size):
            batch = file_paths[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(file_paths) + batch_size - 1) // batch_size
            
            self.log(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
            
            try:
                with self.observability.track_operation("batch_indexing") as tracker:
                    result = self.rag_pipeline.index_documents(batch)
                
                if result["success"]:
                    self.log(f"✓ Batch {batch_num} completed successfully")
                    self.log(f"  Documents processed: {result['documents_processed']}")
                    self.log(f"  Chunks created: {result['chunks_indexed']}")
                    self.log(f"  Batch time: {tracker.get_duration():.2f}s")
                    
                    self.indexing_stats["successful_files"] += result["documents_processed"]
                    self.indexing_stats["total_chunks"] += result["chunks_indexed"]
                else:
                    error_msg = result.get("error", "Unknown error")
                    self.log(f"✗ Batch {batch_num} failed: {error_msg}", "ERROR")
                    self.indexing_stats["failed_files"] += len(batch)
                    self.indexing_stats["errors"].append({
                        "batch": batch_num,
                        "files": batch,
                        "error": error_msg
                    })
                
            except Exception as e:
                error_msg = str(e)
                self.log(f"✗ Exception in batch {batch_num}: {error_msg}", "ERROR")
                self.indexing_stats["failed_files"] += len(batch)
                self.indexing_stats["errors"].append({
                    "batch": batch_num,
                    "files": batch,
                    "error": error_msg
                })
            
            # Small delay between batches to prevent overwhelming the system
            if i + batch_size < len(file_paths):
                time.sleep(1)
        
        self.indexing_stats["end_time"] = datetime.now()
        return self.get_indexing_summary()
    
    def index_documents_individual(self, file_paths: List[str]) -> Dict:
        """Index documents individually."""
        self.log(f"Starting individual indexing of {len(file_paths)} documents")
        
        self.indexing_stats["start_time"] = datetime.now()
        self.indexing_stats["total_files"] = len(file_paths)
        
        for i, file_path in enumerate(file_paths, 1):
            self.log(f"Progress: {i}/{len(file_paths)}")
            self.index_single_document(file_path)
            
            # Small delay between files
            if i < len(file_paths):
                time.sleep(0.5)
        
        self.indexing_stats["end_time"] = datetime.now()
        return self.get_indexing_summary()
    
    def get_indexing_summary(self) -> Dict:
        """Get indexing summary statistics."""
        duration = None
        if self.indexing_stats["start_time"] and self.indexing_stats["end_time"]:
            duration = (self.indexing_stats["end_time"] - self.indexing_stats["start_time"]).total_seconds()
        
        success_rate = 0
        if self.indexing_stats["total_files"] > 0:
            success_rate = (self.indexing_stats["successful_files"] / self.indexing_stats["total_files"]) * 100
        
        return {
            "total_files": self.indexing_stats["total_files"],
            "successful_files": self.indexing_stats["successful_files"],
            "failed_files": self.indexing_stats["failed_files"],
            "total_chunks": self.indexing_stats["total_chunks"],
            "success_rate": success_rate,
            "duration_seconds": duration,
            "errors": self.indexing_stats["errors"]
        }
    
    def print_summary(self, summary: Dict):
        """Print indexing summary."""
        self.log("=" * 60)
        self.log("INDEXING SUMMARY")
        self.log("=" * 60)
        
        self.log(f"Total files processed: {summary['total_files']}")
        self.log(f"Successful: {summary['successful_files']}")
        self.log(f"Failed: {summary['failed_files']}")
        self.log(f"Success rate: {summary['success_rate']:.1f}%")
        self.log(f"Total chunks created: {summary['total_chunks']}")
        
        if summary['duration_seconds']:
            self.log(f"Total time: {summary['duration_seconds']:.2f} seconds")
            if summary['successful_files'] > 0:
                avg_time = summary['duration_seconds'] / summary['successful_files']
                self.log(f"Average time per file: {avg_time:.2f} seconds")
        
        if summary['errors']:
            self.log("\nErrors encountered:")
            for error in summary['errors']:
                if 'batch' in error:
                    self.log(f"  Batch {error['batch']}: {error['error']}")
                else:
                    self.log(f"  {error['file']}: {error['error']}")
        
        # Get current vector store stats
        try:
            pipeline_stats = self.rag_pipeline.get_stats()
            self.log(f"\nVector store statistics:")
            self.log(f"  Total documents in index: {pipeline_stats.get('total_documents', 'Unknown')}")
            self.log(f"  Total chunks in index: {pipeline_stats.get('total_chunks', 'Unknown')}")
        except Exception as e:
            self.log(f"Could not retrieve vector store stats: {str(e)}", "WARNING")
    
    def save_summary(self, summary: Dict, output_file: str = None):
        """Save indexing summary to file."""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.project_root / f"indexing_summary_{timestamp}.json"
        
        # Convert datetime objects to strings for JSON serialization
        summary_copy = summary.copy()
        if self.indexing_stats["start_time"]:
            summary_copy["start_time"] = self.indexing_stats["start_time"].isoformat()
        if self.indexing_stats["end_time"]:
            summary_copy["end_time"] = self.indexing_stats["end_time"].isoformat()
        
        with open(output_file, 'w') as f:
            json.dump(summary_copy, f, indent=2)
        
        self.log(f"Summary saved to: {output_file}")
    
    def clear_index(self, confirm: bool = False) -> bool:
        """Clear the entire vector index."""
        if not confirm:
            response = input("Are you sure you want to clear the entire index? (yes/no): ")
            if response.lower() != 'yes':
                self.log("Index clearing cancelled")
                return False
        
        try:
            result = self.rag_pipeline.clear_index()
            if result:
                self.log("✓ Index cleared successfully")
                return True
            else:
                self.log("✗ Failed to clear index", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ Exception while clearing index: {str(e)}", "ERROR")
            return False


def main():
    """Main indexing function."""
    parser = argparse.ArgumentParser(description="Index documents for RAG System")
    parser.add_argument("paths", nargs="*", help="Paths to documents or directories to index")
    parser.add_argument("--config", help="Path to RAG configuration file")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size for processing (default: 5)")
    parser.add_argument("--individual", action="store_true", help="Process files individually instead of batches")
    parser.add_argument("--recursive", action="store_true", default=True, help="Recursively search directories")
    parser.add_argument("--no-recursive", action="store_true", help="Don't recursively search directories")
    parser.add_argument("--clear-index", action="store_true", help="Clear the entire index before indexing")
    parser.add_argument("--save-summary", help="Save summary to specified file")
    parser.add_argument("--sample-docs", action="store_true", help="Index sample documents created by setup")
    parser.add_argument("--no-prefix-filter", action="store_true", help="Disable filtering by filename prefixes (INI, IXP, DEC, ROP, IFS)")
    
    args = parser.parse_args()
    
    # Handle recursive flag
    recursive = args.recursive and not args.no_recursive
    
    # Initialize indexer with prefix filtering option
    filter_by_prefix = not args.no_prefix_filter
    indexer = DocumentIndexer(config_path=args.config, filter_by_prefix=filter_by_prefix)
    
    # Clear index if requested
    if args.clear_index:
        if not indexer.clear_index():
            sys.exit(1)
    
    # Determine paths to index
    paths_to_index = args.paths
    
    if args.sample_docs:
        sample_docs_dir = indexer.project_root / "sample_documents"
        if sample_docs_dir.exists():
            paths_to_index.append(str(sample_docs_dir))
        else:
            indexer.log("Sample documents directory not found. Run setup_rag.py first.", "ERROR")
            sys.exit(1)
    
    if not paths_to_index:
        indexer.log("No paths specified for indexing. Use --sample-docs or provide paths.", "ERROR")
        parser.print_help()
        sys.exit(1)
    
    # Find all documents
    all_documents = []
    for path in paths_to_index:
        documents = indexer.find_documents(path, recursive=recursive)
        all_documents.extend(documents)
    
    if not all_documents:
        indexer.log("No supported documents found in specified paths", "ERROR")
        sys.exit(1)
    
    indexer.log(f"Found {len(all_documents)} documents to index")
    
    # Show supported extensions
    indexer.log(f"Supported extensions: {', '.join(indexer.get_supported_extensions())}")
    
    # Index documents
    if args.individual:
        summary = indexer.index_documents_individual(all_documents)
    else:
        summary = indexer.index_documents_batch(all_documents, batch_size=args.batch_size)
    
    # Print and save summary
    indexer.print_summary(summary)
    
    if args.save_summary:
        indexer.save_summary(summary, args.save_summary)
    
    # Exit with appropriate code
    if summary["failed_files"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()