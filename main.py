import os
import json
import argparse
import re
from typing import Dict, Any, List
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from pathlib import Path
from chunking_processor import ChunkingProcessor

# Import agents
from agents.agents import (
    agente_auditorias,
    agente_productos,
    agente_desembolsos,
    agente_experto_auditorias,
    agente_experto_productos,
    agente_experto_desembolsos,
    agente_concatenador
)

# Import tasks
from tasks.task import (
    task_auditorias,
    task_productos,
    task_desembolsos,
    task_experto_auditorias,
    task_experto_productos,
    task_experto_desembolsos,
    task_concatenador
)

from document_intelligence_processor import process_documents as process_documents_di
from chunking_processor import ChunkingProcessor, chunk_document_content
from config.settings import settings as config

# Load environment variables
load_dotenv()

def create_project_folder_structure(project_name: str) -> Dict[str, str]:
    """Creates organized folder structure for project outputs.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Dict with folder paths for docs and agents_output
    """
    base_output_dir = Path("output_docs")
    project_dir = base_output_dir / project_name
    docs_dir = project_dir / "docs"
    agents_output_dir = project_dir / "agents_output"
    
    # Create directories
    project_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    agents_output_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "project_dir": str(project_dir),
        "docs_dir": str(docs_dir),
        "agents_output_dir": str(agents_output_dir)
    }

def process_project_documents(project_name: str = None):
    """Processes project documents using Document Intelligence.
    
    Args:
        project_name: Name of the project to process
    """
    print("Starting document processing with Document Intelligence...")
    print("="*60)
    
    try:
        result = process_documents(project_name)
        
        if project_name is None:
            # Show available projects
            available = result.get("available_projects", [])
            if available:
                print(f"\nAvailable projects ({len(available)}):")
                for i, project in enumerate(available, 1):
                    print(f"   {i}. {project}")
                print("\nUse: process_project_documents('project_name') to process")
            else:
                print("\nNo projects available.")
                print("   Create folders in 'input_docs' with PDF files.")
        else:
            # Show processing result
            metadata = result.get("metadata", {})
            print(f"\nProcessing result:")
            print(f"   Project: {result.get('project_name', 'N/A')}")
            print(f"   Total documents: {metadata.get('total_documents', 0)}")
            print(f"   Successful: {metadata.get('successful_documents', 0)}")
            print(f"   Failed: {metadata.get('failed_documents', 0)}")
            print(f"   Status: {metadata.get('processing_status', 'N/A')}")
            
            if metadata.get('successful_documents', 0) > 0:
                print(f"\nFiles generated in 'output_docs':")
                print(f"   {project_name}_concatenated.md")
                print(f"   {project_name}_metadata.json")
        
        return result
        
    except Exception as e:
        print(f"Processing error: {str(e)}")
        return None


def process_with_chunking_if_needed(processed_documents: str, project_name: str, max_tokens: int = 150000) -> Dict[str, Any]:
    """Procesa documentos con chunking automático si exceden el límite de tokens.
    
    Args:
        processed_documents: Contenido del documento procesado
        project_name: Nombre del proyecto
        max_tokens: Límite máximo de tokens por chunk
    
    Returns:
        dict: Resultado del chunking con información de chunks
    """
    print(f"\nVerificando si se requiere chunking para {project_name}...")
    
    # Crear procesador de chunking
    chunking_processor = ChunkingProcessor(max_tokens=max_tokens)
    
    # Procesar el contenido
    chunking_result = chunking_processor.process_document_content(processed_documents, project_name)
    
    # Guardar chunks si es necesario
    if chunking_result['requires_chunking']:
        print(f"\nDocumento requiere chunking. Creando {len(chunking_result['chunks'])} chunks...")
        saved_files = chunking_processor.save_chunks(chunking_result)
        chunking_result['saved_files'] = saved_files
    else:
        print("\nDocumento dentro del límite de tokens. No se requiere chunking.")
    
    return chunking_result


def run_analysis_on_chunk(chunk_content: str, chunk_index: int, project_name: str, agents_output_dir: str = None) -> Dict[str, Any]:
    """Ejecuta el análisis de CrewAI en un chunk específico.
    
    Args:
        chunk_content: Contenido del chunk
        chunk_index: Índice del chunk
        project_name: Nombre del proyecto
        agents_output_dir: Directorio donde guardar los JSONs de agentes
    
    Returns:
        dict: Resultados del análisis del chunk
    """
    print(f"\nAnalizando chunk {chunk_index} del proyecto {project_name}...")
    
    try:
        # Validar configuración
        config.validate_config()
        
        # Phase 1: Basic analysis tasks
        basic_tasks = [task_auditorias, task_productos, task_desembolsos]
        basic_agents = [agente_auditorias, agente_productos, agente_desembolsos]
        
        print(f"\nPhase 1: Análisis básico - Chunk {chunk_index}")
        basic_crew = Crew(
            agents=basic_agents,
            tasks=basic_tasks,
            verbose=True,
            process=Process.sequential
        )
        
        # Usar el archivo JSONL específico del chunk
        chunk_jsonl_file = f"{agents_output_dir}/corpus_chunk_{chunk_index:03d}.jsonl"
        
        basic_result = basic_crew.kickoff(inputs={
            'corpus_jsonl': chunk_jsonl_file,
            'project_name': project_name,
            'sections_validas': ["Opinión", "Opinión sin reserva", "Opinión sin salvedades", "Dictamen", "Conclusión de auditoría"],
            'prefijo_prioritario': ["IXP"],
            'prefijos_prioritarios': ["ROP", "INI", "DEC", "IFS"],
            'timestamp_formato': "YYYY-MM-DD HH:MM:SS"
        })
        
        # Extract results from basic analysis
        audit_results = str(basic_result.tasks_output[0]) if len(basic_result.tasks_output) > 0 else ""
        product_results = str(basic_result.tasks_output[1]) if len(basic_result.tasks_output) > 1 else ""
        disbursement_results = str(basic_result.tasks_output[2]) if len(basic_result.tasks_output) > 2 else ""
        
        # Save individual basic agent results for this chunk
        if agents_output_dir:
            from datetime import datetime
            
            timestamp = datetime.now().isoformat()
            
            basic_agents_results = {
                'agente_auditorias': {
                    'agent_name': 'Agente de Auditorías',
                    'phase': 'basic_analysis',
                    'chunk_index': chunk_index,
                    'output': audit_results,
                    'timestamp': timestamp
                },
                'agente_productos': {
                    'agent_name': 'Agente de Productos',
                    'phase': 'basic_analysis',
                    'chunk_index': chunk_index,
                    'output': product_results,
                    'timestamp': timestamp
                },
                'agente_desembolsos': {
                    'agent_name': 'Agente de Desembolsos',
                    'phase': 'basic_analysis',
                    'chunk_index': chunk_index,
                    'output': disbursement_results,
                    'timestamp': timestamp
                }
            }
            
            # Save each basic agent result to individual JSON files
            for agent_key, agent_data in basic_agents_results.items():
                agent_file = os.path.join(agents_output_dir, f"{agent_key}_chunk_{chunk_index}_output.json")
                with open(agent_file, 'w', encoding='utf-8') as f:
                    json.dump(agent_data, f, indent=2, ensure_ascii=False)
                print(f"Saved {agent_data['agent_name']} chunk {chunk_index} output to: {agent_file}")
                
                # Extract JSONL content from output field and save to individual JSONL files
                extract_and_save_jsonl_from_agent_output(agent_key, agent_data, chunk_index, agents_output_dir)
        
        # Phase 2: Expert analysis tasks
        expert_tasks = [task_experto_auditorias, task_experto_productos, task_experto_desembolsos]
        expert_agents = [agente_experto_auditorias, agente_experto_productos, agente_experto_desembolsos]
        
        print(f"\nPhase 2: Análisis experto - Chunk {chunk_index}")
        expert_crew = Crew(
            agents=expert_agents,
            tasks=expert_tasks,
            verbose=True,
            process=Process.sequential
        )
        
        # Crear archivos JSONL temporales para las tareas expertas
        auditorias_jsonl_file = f"{agents_output_dir}/auditorias_chunk_{chunk_index:03d}.jsonl"
        productos_jsonl_file = f"{agents_output_dir}/productos_chunk_{chunk_index:03d}.jsonl"
        desembolsos_jsonl_file = f"{agents_output_dir}/desembolsos_chunk_{chunk_index:03d}.jsonl"
        
        # Ejecutar cada agente experto individualmente con su archivo específico
        expert_results = []
        
        # Agente Experto de Auditorías
        audit_expert_crew = Crew(
            agents=[agente_experto_auditorias],
            tasks=[task_experto_auditorias],
            verbose=True,
            process=Process.sequential
        )
        audit_expert_result = audit_expert_crew.kickoff(inputs={
            'processed_documents': chunk_content,
            'project_name': project_name,
            'auditorias_jsonl': auditorias_jsonl_file,
            'audit_analysis_results': audit_results,
        })
        expert_results.append(audit_expert_result)
        
        # Agente Experto de Productos
        product_expert_crew = Crew(
            agents=[agente_experto_productos],
            tasks=[task_experto_productos],
            verbose=True,
            process=Process.sequential
        )
        product_expert_result = product_expert_crew.kickoff(inputs={
            'processed_documents': chunk_content,
            'project_name': project_name,
            'productos_jsonl': productos_jsonl_file,
        })
        expert_results.append(product_expert_result)
        
        # Agente Experto de Desembolsos
        disbursement_expert_crew = Crew(
            agents=[agente_experto_desembolsos],
            tasks=[task_experto_desembolsos],
            verbose=True,
            process=Process.sequential
        )
        disbursement_expert_result = disbursement_expert_crew.kickoff(inputs={
            'processed_documents': chunk_content,
            'project_name': project_name,
            'desembolsos_jsonl': desembolsos_jsonl_file,
        })
        expert_results.append(disbursement_expert_result)
        
        # Simular el resultado combinado para compatibilidad
        class CombinedExpertResult:
            def __init__(self, results):
                self.tasks_output = []
                for result in results:
                    if hasattr(result, 'tasks_output') and result.tasks_output:
                        self.tasks_output.extend(result.tasks_output)
        
        expert_result = CombinedExpertResult(expert_results)
        
        # Extract expert results
        expert_audit_results = str(expert_result.tasks_output[0]) if len(expert_result.tasks_output) > 0 else ""
        expert_product_results = str(expert_result.tasks_output[1]) if len(expert_result.tasks_output) > 1 else ""
        expert_disbursement_results = str(expert_result.tasks_output[2]) if len(expert_result.tasks_output) > 2 else ""
        
        # Save individual expert agent results for this chunk
        if agents_output_dir:
            expert_agents_results = {
                'agente_experto_auditorias': {
                    'agent_name': 'Agente Experto en Auditorías',
                    'phase': 'expert_analysis',
                    'chunk_index': chunk_index,
                    'output': expert_audit_results,
                    'timestamp': timestamp
                },
                'agente_experto_productos': {
                    'agent_name': 'Agente Experto en Productos',
                    'phase': 'expert_analysis',
                    'chunk_index': chunk_index,
                    'output': expert_product_results,
                    'timestamp': timestamp
                },
                'agente_experto_desembolsos': {
                    'agent_name': 'Agente Experto en Desembolsos',
                    'phase': 'expert_analysis',
                    'chunk_index': chunk_index,
                    'output': expert_disbursement_results,
                    'timestamp': timestamp
                }
            }
            
            # Save each expert agent result to individual JSON files
            for agent_key, agent_data in expert_agents_results.items():
                agent_file = os.path.join(agents_output_dir, f"{agent_key}_chunk_{chunk_index}_output.json")
                with open(agent_file, 'w', encoding='utf-8') as f:
                    json.dump(agent_data, f, indent=2, ensure_ascii=False)
                print(f"Saved {agent_data['agent_name']} chunk {chunk_index} output to: {agent_file}")
                
                # Extract JSONL content from output field and save to individual JSONL files
                extract_and_save_jsonl_from_agent_output(agent_key, agent_data, chunk_index, agents_output_dir)
        
        return {
            'chunk_index': chunk_index,
            'project_name': project_name,
            'audit_results': audit_results,
            'product_results': product_results,
            'disbursement_results': disbursement_results,
            'expert_audit_results': expert_audit_results,
            'expert_product_results': expert_product_results,
            'expert_disbursement_results': expert_disbursement_results,
            'status': 'success'
        }
        
    except Exception as e:
        print(f"Error analizando chunk {chunk_index}: {str(e)}")
        return {
            'chunk_index': chunk_index,
            'project_name': project_name,
            'error': str(e),
            'status': 'error'
        }


def consolidate_chunk_results(chunk_results: List[Dict[str, Any]], project_name: str, agents_output_dir: str = None) -> str:
    """Consolida los resultados de múltiples chunks en un análisis final.
    
    Args:
        chunk_results: Lista de resultados de análisis de chunks
        project_name: Nombre del proyecto
    
    Returns:
        str: Análisis consolidado final
    """
    print(f"\nConsolidando resultados de {len(chunk_results)} chunks...")
    
    # Preparar contenido consolidado para el agente concatenador
    consolidated_content = f"""# ANÁLISIS CONSOLIDADO - PROYECTO {project_name.upper()}

## RESUMEN DE CHUNKS PROCESADOS
Total de chunks analizados: {len(chunk_results)}

"""
    
    # Agregar resultados de cada chunk
    all_audit_results = []
    all_product_results = []
    all_disbursement_results = []
    all_expert_audit_results = []
    all_expert_product_results = []
    all_expert_disbursement_results = []
    
    for i, result in enumerate(chunk_results):
        if result['status'] == 'success':
            consolidated_content += f"\n### CHUNK {result['chunk_index']}\n"
            consolidated_content += f"**Auditorías:** {result['audit_results'][:200]}...\n"
            consolidated_content += f"**Productos:** {result['product_results'][:200]}...\n"
            consolidated_content += f"**Desembolsos:** {result['disbursement_results'][:200]}...\n\n"
            
            all_audit_results.append(result['audit_results'])
            all_product_results.append(result['product_results'])
            all_disbursement_results.append(result['disbursement_results'])
            all_expert_audit_results.append(result['expert_audit_results'])
            all_expert_product_results.append(result['expert_product_results'])
            all_expert_disbursement_results.append(result['expert_disbursement_results'])
        else:
            consolidated_content += f"\n### CHUNK {result['chunk_index']} - ERROR\n"
            consolidated_content += f"Error: {result['error']}\n\n"
    
    try:
        # Usar el agente concatenador para consolidar todo
        concat_crew = Crew(
            agents=[agente_concatenador],
            tasks=[task_concatenador],
            verbose=True,
            process=Process.sequential
        )
        
        # Consolidar resultados de expertos para el concatenador
        audit_consolidated = "\n\n".join(all_expert_audit_results)
        product_consolidated = "\n\n".join(all_expert_product_results)
        disbursement_consolidated = "\n\n".join(all_expert_disbursement_results)
        
        expert_assessments = f"""
        EVALUACIONES DE EXPERTOS CONSOLIDADAS:
        
        AUDITORÍAS:
        {audit_consolidated}
        
        PRODUCTOS:
        {product_consolidated}
        
        DESEMBOLSOS:
        {disbursement_consolidated}
        """
        
        # Para chunks consolidados, crear archivos JSONL temporales
        auditorias_expert_jsonl = f"{agents_output_dir}/auditorias_expert_consolidated.jsonl"
        productos_expert_jsonl = f"{agents_output_dir}/productos_expert_consolidated.jsonl"
        desembolsos_expert_jsonl = f"{agents_output_dir}/desembolsos_expert_consolidated.jsonl"
        
        # Nueva lógica: Consolidar archivos JSONL de chunks al final del procesamiento CrewAI
        from utils.jsonl_handler import JSONLHandler
        import glob
        jsonl_handler = JSONLHandler()
        
        print("\n=== CONSOLIDANDO ARCHIVOS JSONL DE CHUNKS ===")
        
        # Buscar todos los archivos *_chunk_X.jsonl en el directorio de salida
        auditorias_pattern = f"{agents_output_dir}/auditorias_chunk_*.jsonl"
        productos_pattern = f"{agents_output_dir}/productos_chunk_*.jsonl"
        desembolsos_pattern = f"{agents_output_dir}/desembolsos_chunk_*.jsonl"
        
        auditorias_chunk_files = sorted(glob.glob(auditorias_pattern))
        productos_chunk_files = sorted(glob.glob(productos_pattern))
        desembolsos_chunk_files = sorted(glob.glob(desembolsos_pattern))
        
        print(f"Archivos encontrados:")
        print(f"  - Auditorías: {len(auditorias_chunk_files)} archivos")
        print(f"  - Productos: {len(productos_chunk_files)} archivos")
        print(f"  - Desembolsos: {len(desembolsos_chunk_files)} archivos")
        
        # Consolidar archivos JSONL de chunks en archivos finales
        auditorias_final_jsonl = f"{agents_output_dir}/auditorias.jsonl"
        productos_final_jsonl = f"{agents_output_dir}/productos.jsonl"
        desembolsos_final_jsonl = f"{agents_output_dir}/desembolsos.jsonl"
        
        auditorias_count = 0
        productos_count = 0
        desembolsos_count = 0
        
        if auditorias_chunk_files:
            auditorias_count = jsonl_handler.merge_jsonl_files(auditorias_chunk_files, auditorias_final_jsonl)
            print(f"✓ Consolidado auditorias.jsonl con {auditorias_count} registros")
        
        if productos_chunk_files:
            productos_count = jsonl_handler.merge_jsonl_files(productos_chunk_files, productos_final_jsonl)
            print(f"✓ Consolidado productos.jsonl con {productos_count} registros")
        
        if desembolsos_chunk_files:
            desembolsos_count = jsonl_handler.merge_jsonl_files(desembolsos_chunk_files, desembolsos_final_jsonl)
            print(f"✓ Consolidado desembolsos.jsonl con {desembolsos_count} registros")
        
        # Mantener archivos temporales para compatibilidad con el concatenador
        auditorias_expert_jsonl = auditorias_final_jsonl
        productos_expert_jsonl = productos_final_jsonl
        desembolsos_expert_jsonl = desembolsos_final_jsonl
        
        print(f"Consolidados: {auditorias_count} auditorías, {productos_count} productos, {desembolsos_count} desembolsos")
        
        # Crear archivos JSON de salida
        auditorias_json = f"{agents_output_dir}/auditorias.json"
        productos_json = f"{agents_output_dir}/productos.json"
        desembolsos_json = f"{agents_output_dir}/desembolsos.json"
        
        final_result = concat_crew.kickoff(inputs={
            'processed_documents': consolidated_content,
            'project_name': project_name,
            'audit_analysis_results': "\n\n".join(all_audit_results),
            'product_analysis_results': "\n\n".join(all_product_results),
            'disbursement_analysis_results': "\n\n".join(all_disbursement_results),
            'expert_audit_results': "\n\n".join(all_expert_audit_results),
            'expert_product_results': "\n\n".join(all_expert_product_results),
            'expert_disbursement_results': "\n\n".join(all_expert_disbursement_results),
            'expert_assessments': expert_assessments,
            # Archivos JSONL de entrada para el concatenador
            'auditorias_expert_jsonl': auditorias_expert_jsonl,
            'productos_expert_jsonl': productos_expert_jsonl,
            'desembolsos_expert_jsonl': desembolsos_expert_jsonl,
            # Archivos JSON de salida
            'auditorias_json': auditorias_json,
            'productos_json': productos_json,
            'desembolsos_json': desembolsos_json
        })
        
        # Save concatenator agent result when processing chunks
        if agents_output_dir:
            import json
            import os
            from datetime import datetime
            
            concatenator_result = {
                'agent_name': 'Agente Concatenador',
                'phase': 'final_concatenation',
                'output': str(final_result),
                'timestamp': datetime.now().isoformat(),
                'chunks_processed': len(chunk_results)
            }
            
            concatenator_file = os.path.join(agents_output_dir, "agente_concatenador_output.json")
            with open(concatenator_file, 'w', encoding='utf-8') as f:
                json.dump(concatenator_result, f, indent=2, ensure_ascii=False)
            print(f"Saved Agente Concatenador consolidated output to: {concatenator_file}")
            
            # Los archivos JSONL finales ya fueron creados en la consolidación anterior
            print(f"\n=== ARCHIVOS JSONL FINALES CREADOS ===")
            print(f"✓ {auditorias_final_jsonl} - {auditorias_count} registros")
            print(f"✓ {productos_final_jsonl} - {productos_count} registros")
            print(f"✓ {desembolsos_final_jsonl} - {desembolsos_count} registros")
        
        return str(final_result)
        
    except Exception as e:
        print(f"Error en consolidación final: {str(e)}")
        return consolidated_content


def run_full_analysis(project_name: str, skip_processing: bool = False, max_tokens: int = 150000):
    """Run complete analysis pipeline: Document Processing + CrewAI agents with automatic chunking.
    
    Args:
        project_name: Name of the project to process
        skip_processing: If True, skip document processing and use existing concatenated file
        max_tokens: Maximum tokens per chunk (default: 200000)
    
    Returns:
        dict: Complete analysis results
    """
    print(f"\nStarting full analysis for project: {project_name}")
    print("="*60)
    
    # Create organized folder structure
    folder_structure = create_project_folder_structure(project_name)
    print(f"\nCreated project folder structure:")
    print(f"   Project dir: {folder_structure['project_dir']}")
    print(f"   Docs dir: {folder_structure['docs_dir']}")
    print(f"   Agents output dir: {folder_structure['agents_output_dir']}")
    
    # Define agents_output_dir for use throughout the function
    agents_output_dir = folder_structure['agents_output_dir']
    
    try:
        if skip_processing:
            print("\nSTEP 1: Using existing processed documents")
            print("-" * 50)
            
            # Load processed content from new structure
            output_file = f"output_docs/{project_name}/docs/{project_name}_concatenated.md"
            if not os.path.exists(output_file):
                print(f"Processed file not found: {output_file}")
                return None
                
            with open(output_file, 'r', encoding='utf-8') as f:
                processed_documents = f.read()
            
            print(f"Loaded existing processed content: {len(processed_documents)} characters")
            
            # Create mock processing_result for compatibility
            processing_result = {
                'project_name': project_name,
                'metadata': {
                    'processing_status': 'completed',
                    'successful_documents': 1,
                    'processing_timestamp': 'existing_file'
                }
            }
        else:
            # Step 1: Process documents with Document Intelligence
            print("\nSTEP 1: Document Processing with Azure Document Intelligence")
            print("-" * 50)
            
            # Create Document Intelligence processor with automatic chunking enabled
            from document_intelligence_processor import DocumentIntelligenceProcessor
            endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
            api_key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
            processor = DocumentIntelligenceProcessor(endpoint=endpoint, api_key=api_key, auto_chunk=True, max_tokens=max_tokens)
            processing_result = processor.process_project_documents(project_name)
            
            if not processing_result or processing_result.get('metadata', {}).get('successful_documents', 0) == 0:
                print("No documents were successfully processed. Cannot continue with analysis.")
                return None
            
            # Load processed content from new structure
            output_file = f"output_docs/{project_name}/docs/{project_name}_concatenated.md"
            if not os.path.exists(output_file):
                print(f"Processed file not found: {output_file}")
                return None
                
            with open(output_file, 'r', encoding='utf-8') as f:
                processed_documents = f.read()
            
            print(f"Loaded processed content: {len(processed_documents)} characters")
        
        # Step 2: Use chunking results from DocumentIntelligenceProcessor (if auto_chunk was enabled)
        print("\nSTEP 2: Chunking Analysis")
        print("-" * 50)
        
        # Check if chunking was already performed by DocumentIntelligenceProcessor
        if not skip_processing and 'chunking_result' in processing_result:
            chunking_result = processing_result['chunking_result']
            print("Using chunking results from DocumentIntelligenceProcessor...")
        else:
            # When skip_processing, check if chunking metadata already exists
            if skip_processing:
                chunking_metadata_file = f"output_docs/{project_name}/docs/{project_name}_chunking_metadata.json"
                if os.path.exists(chunking_metadata_file):
                    print("Loading existing chunking metadata...")
                    with open(chunking_metadata_file, 'r', encoding='utf-8') as f:
                        chunking_result = json.load(f)
                    
                    # Generate JSONL input files for chunks if they don't exist
                    if chunking_result['requires_chunking']:
                        print("Generating JSONL input files for existing chunks...")
                        chunking_processor = ChunkingProcessor(max_tokens=max_tokens, generate_jsonl=True)
                        saved_files = chunking_processor.save_chunks(chunking_result)
                        chunking_result['saved_files'] = saved_files
                        print(f"Generated {len(saved_files)} JSONL input files for chunks")
                else:
                    # Fallback to manual chunking analysis
                    print("No existing chunking metadata found. Performing chunking analysis...")
                    chunking_result = process_with_chunking_if_needed(processed_documents, project_name, max_tokens)
            else:
                # Normal processing without skip_processing
                print("Performing chunking analysis...")
                chunking_result = process_with_chunking_if_needed(processed_documents, project_name, max_tokens)
        
        # Step 3: CrewAI Multi-Agent Analysis
        print("\nSTEP 3: CrewAI Multi-Agent Analysis")
        print("-" * 50)
        
        if chunking_result['requires_chunking']:
            # Process each chunk separately
            print(f"\nProcesando {len(chunking_result['chunks'])} chunks secuencialmente...")
            
            chunk_results = []
            for chunk in chunking_result['chunks']:
                chunk_result = run_analysis_on_chunk(
                    chunk['content'], 
                    chunk['index'], 
                    project_name,
                    agents_output_dir
                )
                chunk_results.append(chunk_result)
                
                # Pausa entre chunks para evitar rate limits
                if chunk['index'] < len(chunking_result['chunks']) - 1:
                    print("\nPausa de 2 segundos entre chunks...")
                    import time
                    time.sleep(2)
            
            # Consolidate results from all chunks
            print("\nConsolidando resultados de todos los chunks...")
            crew_result = consolidate_chunk_results(chunk_results, project_name, agents_output_dir)
            
        else:
            # Process the entire document as before (no chunking needed)
            print("\nProcesando documento completo (sin chunking)...")
            
            # Validate configuration
            config.validate_config()
            
            # Execute tasks in phases to handle dependencies
            print("\nExecuting CrewAI analysis in phases...")
            
            # Corpus JSONL is now generated automatically by chunking_processor when auto_chunk=True
            corpus_file_name = "corpus_document_intelligence.jsonl"
            
            # Phase 1: Basic analysis tasks
            basic_tasks = [task_auditorias, task_productos, task_desembolsos]
            basic_agents = [agente_auditorias, agente_productos, agente_desembolsos]
            
            print("\nPhase 1: Basic analysis tasks")
            basic_crew = Crew(
                agents=basic_agents,
                tasks=basic_tasks,
                verbose=True,
                process=Process.sequential
            )
            
            basic_result = basic_crew.kickoff(inputs={
                'corpus_jsonl': f"{agents_output_dir}/{corpus_file_name}",
                'project_name': project_name,
                'sections_validas': ["Opinión", "Opinión sin reserva", "Opinión sin salvedades", "Dictamen", "Conclusión de auditoría"],
                'prefijo_prioritario': ["IXP"],
                'prefijos_prioritarios': ["ROP", "INI", "DEC", "IFS"],
                'timestamp_formato': "YYYY-MM-DD HH:MM:SS"
            })
            
            # Extract results from basic analysis
            audit_results = str(basic_result.tasks_output[0]) if len(basic_result.tasks_output) > 0 else ""
            product_results = str(basic_result.tasks_output[1]) if len(basic_result.tasks_output) > 1 else ""
            disbursement_results = str(basic_result.tasks_output[2]) if len(basic_result.tasks_output) > 2 else ""
            
            # Save individual agent results
            
            # Save basic agents results
            basic_agents_results = {
                'agente_auditorias': {
                    'agent_name': 'Agente de Auditorías',
                    'phase': 'basic_analysis',
                    'output': audit_results,
                    'timestamp': processing_result.get('metadata', {}).get('processing_timestamp')
                },
                'agente_productos': {
                    'agent_name': 'Agente de Productos',
                    'phase': 'basic_analysis',
                    'output': product_results,
                    'timestamp': processing_result.get('metadata', {}).get('processing_timestamp')
                },
                'agente_desembolsos': {
                    'agent_name': 'Agente de Desembolsos',
                    'phase': 'basic_analysis',
                    'output': disbursement_results,
                    'timestamp': processing_result.get('metadata', {}).get('processing_timestamp')
                }
            }
            
            # Save each basic agent result to individual JSON files
            for agent_key, agent_data in basic_agents_results.items():
                agent_file = os.path.join(agents_output_dir, f"{agent_key}_output.json")
                with open(agent_file, 'w', encoding='utf-8') as f:
                    json.dump(agent_data, f, indent=2, ensure_ascii=False)
                print(f"Saved {agent_data['agent_name']} output to: {agent_file}")
                
                # Extract JSONL content from output field and save to individual JSONL files
                extract_and_save_jsonl_from_agent_output(agent_key, agent_data, 0, agents_output_dir)
            
            # Phase 2: Expert analysis tasks
            print("\nPhase 2: Expert analysis tasks")
            
            # Ejecutar cada agente experto individualmente con su archivo específico
            expert_results = []
            
            # Agente Experto de Auditorías
            audit_expert_crew = Crew(
                agents=[agente_experto_auditorias],
                tasks=[task_experto_auditorias],
                verbose=True,
                process=Process.sequential
            )
            audit_expert_result = audit_expert_crew.kickoff(inputs={
                'auditorias_jsonl': f"{agents_output_dir}/auditorias.jsonl",
                'project_name': project_name
            })
            expert_results.append(audit_expert_result)
            
            # Agente Experto de Productos
            product_expert_crew = Crew(
                agents=[agente_experto_productos],
                tasks=[task_experto_productos],
                verbose=True,
                process=Process.sequential
            )
            product_expert_result = product_expert_crew.kickoff(inputs={
                'productos_jsonl': f"{agents_output_dir}/productos.jsonl",
                'project_name': project_name
            })
            expert_results.append(product_expert_result)
            
            # Agente Experto de Desembolsos
            disbursement_expert_crew = Crew(
                agents=[agente_experto_desembolsos],
                tasks=[task_experto_desembolsos],
                verbose=True,
                process=Process.sequential
            )
            disbursement_expert_result = disbursement_expert_crew.kickoff(inputs={
                'desembolsos_jsonl': f"{agents_output_dir}/desembolsos.jsonl",
                'project_name': project_name
            })
            expert_results.append(disbursement_expert_result)
            
            # Simular el resultado combinado para compatibilidad
            class CombinedExpertResult:
                def __init__(self, results):
                    self.tasks_output = []
                    for result in results:
                        if hasattr(result, 'tasks_output') and result.tasks_output:
                            self.tasks_output.extend(result.tasks_output)
            
            expert_result = CombinedExpertResult(expert_results)
            
            # Extract expert results
            expert_audit_results = str(expert_result.tasks_output[0]) if len(expert_result.tasks_output) > 0 else ""
            expert_product_results = str(expert_result.tasks_output[1]) if len(expert_result.tasks_output) > 1 else ""
            expert_disbursement_results = str(expert_result.tasks_output[2]) if len(expert_result.tasks_output) > 2 else ""
            
            # Save expert agents results
            expert_agents_results = {
                'agente_experto_auditorias': {
                    'agent_name': 'Agente Experto en Auditorías',
                    'phase': 'expert_analysis',
                    'output': expert_audit_results,
                    'timestamp': processing_result.get('metadata', {}).get('processing_timestamp')
                },
                'agente_experto_productos': {
                    'agent_name': 'Agente Experto en Productos',
                    'phase': 'expert_analysis',
                    'output': expert_product_results,
                    'timestamp': processing_result.get('metadata', {}).get('processing_timestamp')
                },
                'agente_experto_desembolsos': {
                    'agent_name': 'Agente Experto en Desembolsos',
                    'phase': 'expert_analysis',
                    'output': expert_disbursement_results,
                    'timestamp': processing_result.get('metadata', {}).get('processing_timestamp')
                }
            }
            
            # Save each expert agent result to individual JSON files
            for agent_key, agent_data in expert_agents_results.items():
                agent_file = os.path.join(agents_output_dir, f"{agent_key}_output.json")
                with open(agent_file, 'w', encoding='utf-8') as f:
                    json.dump(agent_data, f, indent=2, ensure_ascii=False)
                print(f"Saved {agent_data['agent_name']} output to: {agent_file}")
                
                # Extract JSONL content from output field and save to individual JSONL files
                extract_and_save_jsonl_from_agent_output(agent_key, agent_data, 0, agents_output_dir)
            
            # Phase 3: Concatenation task
            concat_tasks = [task_concatenador]
            concat_agents = [agente_concatenador]
            
            print("\nPhase 3: Final concatenation task")
            concat_crew = Crew(
                agents=concat_agents,
                tasks=concat_tasks,
                verbose=True,
                process=Process.sequential
            )
            
            # Consolidar resultados de expertos para el concatenador
            expert_assessments = f"""
            EVALUACIONES DE EXPERTOS:
            
            AUDITORÍAS:
            {expert_audit_results}
            
            PRODUCTOS:
            {expert_product_results}
            
            DESEMBOLSOS:
            {expert_disbursement_results}
            """
            
            crew_result = concat_crew.kickoff(inputs={
                'auditorias_expert_jsonl': f"{agents_output_dir}/auditorias_expert.jsonl",
                'productos_expert_jsonl': f"{agents_output_dir}/productos_expert.jsonl",
                'desembolsos_expert_jsonl': f"{agents_output_dir}/desembolsos_expert.jsonl",
                'project_name': project_name,
                'auditorias_json': f"{agents_output_dir}/auditorias.json",
                'productos_json': f"{agents_output_dir}/productos.json",
                'desembolsos_json': f"{agents_output_dir}/desembolsos.json"
            })
        
        print("\nAnalysis completed successfully!")
        
        # Step 3: Save results
        print("\nSTEP 3: Saving Analysis Results")
        print("-" * 50)
        
        # Save concatenator agent result
        concatenator_result = {
            'agent_name': 'Agente Concatenador',
            'phase': 'final_concatenation',
            'output': str(crew_result),
            'timestamp': processing_result.get('metadata', {}).get('processing_timestamp')
        }
        
        concatenator_file = os.path.join(agents_output_dir, "agente_concatenador_output.json")
        with open(concatenator_file, 'w', encoding='utf-8') as f:
            json.dump(concatenator_result, f, indent=2, ensure_ascii=False)
        print(f"Saved Agente Concatenador output to: {concatenator_file}")
        
        # Save complete results in project folder
        results = {
            'project_name': project_name,
            'docling_processing': processing_result,
            'crewai_analysis': str(crew_result),
            'timestamp': processing_result.get('metadata', {}).get('processing_timestamp'),
            'folder_structure': folder_structure
        }
        
        # Save complete results in the project directory
        results_file = os.path.join(folder_structure['project_dir'], f"{project_name}_analysis_results.json")
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Complete results saved to: {results_file}")
        
        # CSV conversion step removed - JSONL files contain all necessary data
        
        return results
        
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def extract_and_save_jsonl_from_agent_output(agent_key: str, agent_data: Dict[str, Any], chunk_index: int, agents_output_dir: str):
    """Extrae el contenido JSONL del campo 'output' del agente y lo guarda en archivos individuales.
    
    Args:
        agent_key: Clave del agente (ej: 'agente_auditorias')
        agent_data: Datos del agente con el campo 'output'
        chunk_index: Índice del chunk
        agents_output_dir: Directorio donde guardar los archivos JSONL
    """
    try:
        output_content = agent_data.get('output', '')
        
        # Determinar el tipo de archivo basado en el agent_key
        if 'auditorias' in agent_key:
            file_type = 'auditorias'
        elif 'productos' in agent_key:
            file_type = 'productos'
        elif 'desembolsos' in agent_key:
            file_type = 'desembolsos'
        else:
            file_type = 'unknown'
        
        # Determinar si es agente experto
        is_expert = 'experto' in agent_key
        
        # Crear archivo JSONL para este chunk
        if chunk_index == 0:
            # Para documento completo (sin chunking), usar nombre simple
            if is_expert:
                jsonl_filename = f"{file_type}_expert.jsonl"
            else:
                jsonl_filename = f"{file_type}.jsonl"
        else:
            # Para chunks, usar nombre con índice (formato 03d para consistencia)
            if is_expert:
                jsonl_filename = f"{file_type}_expert_chunk_{chunk_index:03d}.jsonl"
            else:
                jsonl_filename = f"{file_type}_chunk_{chunk_index:03d}.jsonl"
        jsonl_filepath = os.path.join(agents_output_dir, jsonl_filename)
        
        # Buscar contenido JSONL en el output usando regex (formato con ```jsonl)
        jsonl_pattern = r'```jsonl\n([\s\S]*?)\n```'
        jsonl_matches = re.findall(jsonl_pattern, output_content, re.MULTILINE)
        
        if jsonl_matches:
            # Formato con bloque de código markdown
            with open(jsonl_filepath, 'w', encoding='utf-8') as f:
                for jsonl_content in jsonl_matches:
                    # Escribir cada línea del contenido JSONL
                    for line in jsonl_content.strip().split('\n'):
                        if line.strip():  # Solo escribir líneas no vacías
                            f.write(line.strip() + '\n')
            print(f"Extracted JSONL content (markdown format) to: {jsonl_filepath}")
        elif output_content.strip() and (output_content.startswith('{') or '\n{' in output_content):
            # Formato directo JSONL sin bloque de código
            with open(jsonl_filepath, 'w', encoding='utf-8') as f:
                # Escribir cada línea del contenido JSONL
                for line in output_content.strip().split('\n'):
                    if line.strip():  # Solo escribir líneas no vacías
                        f.write(line.strip() + '\n')
            print(f"Extracted JSONL content (direct format) to: {jsonl_filepath}")
        else:
            print(f"No JSONL content found in {agent_key} chunk {chunk_index} output")
            
    except Exception as e:
        print(f"Error extracting JSONL from {agent_key} chunk {chunk_index}: {str(e)}")


def main():
    """Main function of the CrewAI system with Document Intelligence."""
    print("CrewAI + Document Intelligence Analysis System")
    print("="*50)
    
    # Validate configuration first
    try:
        config.validate_config()
        print("Configuration validated successfully")
    except Exception as e:
        print(f"Configuration error: {e}")
        return None
    
    # Check for available projects
    print("\nAvailable Projects:")
    print("-" * 30)
    
    processing_result = process_documents_di(None)
    
    if processing_result and processing_result.get("available_projects"):
        available_projects = processing_result["available_projects"]
        print(f"\nFound {len(available_projects)} project(s):")
        for i, project in enumerate(available_projects, 1):
            print(f"   {i}. {project}")
        
        print("\nTo run complete analysis on a project:")
        print("   from main import run_full_analysis")
        print("   run_full_analysis('project_name')")
        
        print("\nSystem Components:")
        print(f"   - 7 CrewAI agents configured")
        print(f"   - 7 specialized tasks defined")
        print(f"   - Document Intelligence processing ready")
        print(f"   - Sequential workflow pipeline")
        
    else:
        print("\nNo projects found.")
        print("\nSetup Instructions:")
        print("   1. Create folders in 'input_docs/' (e.g., 'input_docs/my_project/')")
        print("   2. Place PDF files in the project folder")
        print("   3. Run: run_full_analysis('my_project')")
    
    return processing_result




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='CrewAI + Document Processing Analysis System')
    parser.add_argument('--full-analysis', type=str, help='Run full analysis on specified project')
    parser.add_argument('--skip-processing', action='store_true', help='Skip document processing and use existing concatenated file')

    
    args = parser.parse_args()
    
    if args.full_analysis:
        # Run full analysis on the specified project
        result = run_full_analysis(args.full_analysis, skip_processing=args.skip_processing)
        if result:
            print(f"\nFull analysis completed for project: {args.full_analysis}")
        else:
            print(f"\nFull analysis failed for project: {args.full_analysis}")
    else:
        main()