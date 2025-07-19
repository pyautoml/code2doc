#!/usr/bin/env python3

import os
import re
import json
import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass
from langchain_ollama import OllamaLLM
from typing import List, Dict, Any, Optional
from src.core.configuration import ConfigLoader
from src.database.qdrant_writer import QdrantBatchWriter


logger = logging.getLogger(os.getenv("LOGGER", "Code2Doc"))


@dataclass
class DocGenerationResult:
    repo_id: str
    repo_name: str
    success: bool
    output_file: Optional[Path] = None
    error: Optional[str] = None
    total_chunks_analyzed: int = 0
    final_score: int = 0

def load_template(path: Path | str):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


class EnhancedDocumentationGenerator:

    def __init__(self):
        self.config = ConfigLoader()
        self.batch_writer = QdrantBatchWriter.get_instance()
        base_path = Path(".").resolve()

        try:
            self.writer_prompt = load_template(str(base_path / Path(self.config.get("template.writer"))))
            self.reviewer_prompt = load_template(str(base_path / Path(self.config.get("template.reviewer"))))
            self.doc_template = load_template(str(base_path / Path(self.config.get("template.documentation"))))
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            raise

        self.writer_model = self.config.get("llm.writer_model", "llama3.1:8b")
        self.reviewer_model = self.config.get("llm.reviewer_model", "qwen2.5:7b")

        try:
            self.writer_llm = OllamaLLM(
                model=self.writer_model,
                temperature=self.config.get("llm.writer_temperature", 0.1),
                top_p=0.1,
                repeat_penalty=1.1,
                top_k=10
            )
            self.reviewer_llm = OllamaLLM(
                model=self.reviewer_model,
                temperature=self.config.get("llm.reviewer_temperature", 0.0),
                top_p=0.05,
                repeat_penalty=1.1,
                top_k=5
            )
            logger.info(f"Initialized LLMs: Writer={self.writer_model}, Reviewer={self.reviewer_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLMs: {e}")
            raise

        self.output_dir = Path(self.config.get("storage.documentation", "storage/documentation"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.php', '.rb'}
        self.config_extensions = {'.toml', '.yaml', '.yml', '.json', '.ini', '.cfg', '.conf'}
        self.doc_extensions = {'.md', '.rst', '.txt', '.adoc'}


    def generate_documentation_for_all_repos(self) -> List[DocGenerationResult]:
        logger.info("Starting enhanced documentation generation for all repositories")
        repo_ids = self._get_all_repository_ids()
        if not repo_ids:
            logger.warning("No repositories found in database")
            return []

        logger.info(f"Found {len(repo_ids)} repositories to process")

        results = []
        for i, repo_id in enumerate(repo_ids, 1):
            logger.info(f"Processing {i}/{len(repo_ids)}: {repo_id}")
            result = self.generate_documentation_for_repo(repo_id)
            results.append(result)
            if result.success:
                logger.info(
                    f"Generated documentation: {result.output_file} "
                    f"(Score: {result.final_score}/100, Chunks: {result.total_chunks_analyzed})"
                )
            else:
                logger.error(f"Failed: {result.error}")
        return results

    def generate_documentation_for_repo(self, repo_id: str) -> DocGenerationResult:
        try:
            repo_info = self._get_repository_info(repo_id)
            all_chunks = self._get_all_repository_chunks(repo_id)
            documents = self._get_repository_documents(repo_id)

            if not all_chunks:
                logger.warning(f"No chunks found for repository: {repo_id}")
                return DocGenerationResult(
                    repo_id=repo_id,
                    repo_name=repo_info.get("name", repo_id),
                    success=False,
                    error="No data found",
                )
            logger.debug(f"Processing {len(all_chunks)} chunks for {repo_info['name']}")
            context = self._prepare_comprehensive_context(
                repo_info, all_chunks, documents
            )
            output_file = self._create_output_path(repo_info["name"])
            final_documentation, final_score = self._run_enhanced_agent_loop(context, max_iterations=3)
            output_file.write_text(final_documentation, encoding="utf-8")
            self._save_generation_metadata(
                output_file, context, final_score, len(all_chunks)
            )
            logger.info(f"Generated comprehensive documentation: {output_file}")
            return DocGenerationResult(
                repo_id=repo_id,
                repo_name=repo_info["name"],
                success=True,
                output_file=output_file,
                total_chunks_analyzed=len(all_chunks),
                final_score=final_score,
            )
        except Exception as e:
            logger.error(f"Error generating documentation for {repo_id}: {e}")
            return DocGenerationResult(
                repo_id=repo_id, repo_name=repo_id, success=False, error=str(e)
            )

    def _get_all_repository_chunks(self, repo_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.batch_writer.sqlite_db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                           SELECT content, metadata
                           FROM chunks
                           WHERE repo_id = ?
                           ORDER BY id
                           """,
                (repo_id,),
            )
            chunks = [{"content": row[0], "metadata": row[1]} for row in cursor.fetchall()]
            logger.debug(f"Retrieved {len(chunks)} chunks for repository {repo_id}")
            return chunks

    def _prepare_comprehensive_context(
        self,
        repo_info: Dict[str, Any],
        all_chunks: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        logger.debug(f"Preparing comprehensive context from {len(all_chunks)} chunks")
        categorized_chunks = self._categorize_chunks_by_type(all_chunks)
        project_analysis = self._perform_comprehensive_analysis(all_chunks, documents)
        structured_samples = self._create_structured_samples(categorized_chunks)

        return {
            "repo_id": repo_info["id"],
            "repo_name": repo_info["name"],
            "repo_source": repo_info["source"],
            "total_chunks": len(all_chunks),
            "total_documents": len(documents),
            "project_analysis": project_analysis,
            "categorized_chunks": categorized_chunks,
            "structured_samples": structured_samples,
            "languages": project_analysis["languages"],
            "frameworks": project_analysis["frameworks"],
            "architecture_type": project_analysis["architecture_type"],
            "main_modules": project_analysis["main_modules"],
            "dependencies": project_analysis["dependencies"],
            "configuration_files": project_analysis["configuration_files"],
            "entry_points": project_analysis["entry_points"],
            "test_files": project_analysis["test_files"],
        }

    def _categorize_chunks_by_type(
        self, chunks: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        categorized = {
            "code": [],
            "config": [],
            "docs": [],
            "tests": [],
            "requirements": [],
            "other": [],
        }

        for chunk in chunks:
            file_path = self._extract_file_path_from_metadata(chunk.get("metadata", ""))
            if not file_path:
                categorized["other"].append(chunk)
                continue

            path_obj = Path(file_path)
            file_name = path_obj.name.lower()
            extension = path_obj.suffix.lower()

            if "test" in file_name or "spec" in file_name:
                categorized["tests"].append(chunk)
            elif file_name in [
                "requirements.txt",
                "setup.py",
                "pyproject.toml",
                "package.json",
            ]:
                categorized["requirements"].append(chunk)
            elif extension in self.doc_extensions or "readme" in file_name:
                categorized["docs"].append(chunk)
            elif extension in self.config_extensions:
                categorized["config"].append(chunk)
            elif extension in self.code_extensions:
                categorized["code"].append(chunk)
            else:
                categorized["other"].append(chunk)

        for category, chunks_list in categorized.items():
            if chunks_list:
                logger.debug(f"Category '{category}': {len(chunks_list)} chunks")
        return categorized

    @staticmethod
    def _fix_common_placeholders(text: str, context: Dict[str, Any]) -> str:
        replacements = {
            r"\{\{Project Name\}\}": context.get("repo_name", "Project"),
            r"\{\{Programming language and version\}\}": ", ".join(
                context.get("languages", ["Python"])
            ),
            r"\{\{Framework used\}\}": ", ".join(
                context.get("frameworks", ["Not specified"])
            ),
            r"\{\{repository-url\}\}": context.get("repo_source", "Local project"),
            r"\{\{project-directory\}\}": context.get("repo_name", "project")
            .lower()
            .replace(" ", "-"),
        }

        for pattern, replacement in replacements.items():
            text = text.replace(pattern, replacement)
            text = re.sub(re.escape(pattern), replacement, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _fallback_documentation(context: Dict[str, Any]) -> str:
        repo_name = context.get("repo_name", "Project")
        languages = ", ".join(context.get("languages", ["Unknown"]))
        return f"""# {repo_name}

    ## Project Description
    This is a {languages} project with the following characteristics:
    - **Languages:** {languages}
    - **Frameworks:** {', '.join(context.get('frameworks', ['Not specified']))}
    - **Status:** In Development

    ## Quick Start
    ```bash
    # Basic setup
    git clone [repository]
    cd {repo_name.lower().replace(' ', '-')}
    # Install dependencies and run
    ```

    ## Overview
    This project contains {context.get('total_chunks', 'multiple')} code 
    components across {context.get('total_documents', 'several')} files.

    *This is a fallback documentation generated due to agent processing errors.*
    """

    def _perform_comprehensive_analysis(
            self, all_chunks: List[Dict[str, Any]], documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        analysis = {
            "languages": set(),
            "frameworks": set(),
            "dependencies": set(),
            "main_modules": [],
            "entry_points": [],
            "configuration_files": [],
            "test_files": [],
            "architecture_type": "unknown",
            "key_classes": [],
            "key_functions": [],
            "imports": set(),
            "api_endpoints": [],
            "database_models": [],
        }

        all_content = " ".join(chunk.get("content", "") for chunk in all_chunks)
        for doc in documents:
            file_path = Path(doc.get("file_path", ""))
            ext = file_path.suffix.lower()
            lang_map = {
                ".py": "Python",
                ".js": "JavaScript",
                ".ts": "TypeScript",
                ".java": "Java",
                ".cpp": "C++",
                ".c": "C",
                ".go": "Go",
                ".rs": "Rust",
                ".php": "PHP",
                ".rb": "Ruby",
                ".cs": "C#",
            }
            if ext in lang_map:
                analysis["languages"].add(lang_map[ext])

        framework_patterns = {
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
            "react": "React",
            "vue": "Vue.js",
            "angular": "Angular",
            "spring": "Spring",
            "express": "Express.js",
            "langchain": "LangChain",
            "ollama": "Ollama",
            "tensorflow": "TensorFlow",
            "pytorch": "PyTorch",
            "pandas": "Pandas",
            "numpy": "NumPy",
            "sklearn": "Scikit-learn",
        }

        content_lower = all_content.lower()
        for pattern, framework in framework_patterns.items():
            if pattern in content_lower:
                analysis["frameworks"].add(framework)

        for chunk in all_chunks:
            content = chunk.get("content", "")
            self._analyze_code_patterns(content, analysis)

        analysis["architecture_type"] = self._determine_architecture_type(analysis, all_content)
        analysis["languages"] = sorted(list(analysis["languages"])) or ["Unknown"]
        analysis["frameworks"] = sorted(list(analysis["frameworks"])) or ["Unknown"]
        analysis["dependencies"] = sorted(list(analysis["dependencies"]))
        analysis["imports"] = sorted(list(analysis["imports"]))
        return analysis

    @staticmethod
    def _analyze_code_patterns(content: str, analysis: Dict[str, Any]):
        func_matches = re.findall(r"def\s+(\w+)\s*\([^)]*\):", content)
        analysis["key_functions"].extend(func_matches)

        class_matches = re.findall(r"class\s+(\w+).*?:", content)
        analysis["key_classes"].extend(class_matches)

        import_matches = re.findall(r"(?:from\s+(\S+)\s+)?import\s+([^\n]+)", content)
        for match in import_matches:
            if match[0]:
                analysis["imports"].add(match[0])
            analysis["imports"].add(match[1].split(",")[0].strip())

        api_patterns = [
            r'@app\.route\(["\']([^"\']+)["\']',
            r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']',
            r'app\.(get|post|put|delete)\(["\']([^"\']+)["\']',
        ]
        for pattern in api_patterns:
            matches = re.findall(pattern, content)
            analysis["api_endpoints"].extend(matches)

    @staticmethod
    def _determine_architecture_type(analysis: Dict[str, Any], content: str) -> str:
        content_lower = content.lower()

        if any(fw in analysis["frameworks"] for fw in ["Django", "Flask", "FastAPI"]):
            return "Web API/Service"
        elif any(fw in analysis["frameworks"] for fw in ["React", "Vue.js", "Angular"]):
            return "Frontend Application"
        elif "langchain" in content_lower and "ollama" in content_lower:
            return "AI/LLM Application"
        elif any(fw in analysis["frameworks"] for fw in ["TensorFlow", "PyTorch"]):
            return "Machine Learning"
        elif "cli" in content_lower or "command" in content_lower:
            return "Command Line Tool"
        elif len(analysis["key_classes"]) > 10:
            return "Object-Oriented Library"
        elif "main" in analysis["key_functions"]:
            return "Application/Script"
        else:
            return "Library/Package"

    @staticmethod
    def _create_structured_samples(
            categorized_chunks: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        samples = {}
        priorities = {
            "code": 15,
            "config": 5,
            "docs": 8,
            "requirements": 3,
            "tests": 5,
            "other": 2,
        }

        for category, chunks in categorized_chunks.items():
            if chunks:
                limit = priorities.get(category, 2)
                sorted_chunks = sorted(
                    chunks, key=lambda x: len(x.get("content", "")), reverse=True
                )
                samples[category] = sorted_chunks[:limit]
            else:
                samples[category] = []
        return samples

    def _run_enhanced_agent_loop(
        self, context: Dict[str, Any], max_iterations: int = 3
    ) -> tuple[str, int]:
        logger.debug(f"Starting enhanced agent loop for {context['repo_name']}")
        current_doc = self._call_enhanced_writer(context, is_revision=False)
        final_score = 70

        for iteration in range(1, max_iterations + 1):
            logger.debug(
                f"Iteration {iteration}: Reviewing comprehensive documentation..."
            )

            review_result = self._call_enhanced_reviewer(current_doc, context)
            final_score = self._extract_score_from_review(review_result)
            logger.info(f"Review score: {final_score}/100 (Iteration {iteration})")

            if final_score >= 85:
                logger.info(f"Target score reached! Final score: {final_score}/100")
                break

            if iteration < max_iterations:
                logger.debug(
                    f"Revising documentation based on comprehensive review..."
                )
                current_doc = self._call_enhanced_writer(
                    context,
                    is_revision=True,
                    previous_doc=current_doc,
                    review=review_result,
                )

        return current_doc, final_score

    @staticmethod
    def _contains_placeholders(text: str) -> bool:
        if re.search(r"\{\{.*?\}\}", text):
            return True

        template_phrases = [
            "{{",
            "}}",
            "Describe the",
            "Explain the",
            "List the",
            "repository-url",
            "project-directory",
            "Programming language and version",
            "Framework used",
            "Database system",
        ]
        return any(phrase in text for phrase in template_phrases)

    @staticmethod
    def _check_for_placeholders(documentation: str) -> str:
        issues = []

        placeholders = re.findall(r"\{\{(.*?)\}\}", documentation)
        if placeholders:
            issues.append(
                f"Found {len(placeholders)} template placeholders: {placeholders[:5]}"
            )

        template_phrases = [
            ("{{", "Template placeholder syntax found"),
            ("Describe the", "Template instruction text found"),
            ("Explain the", "Template instruction text found"),
            ("repository-url", "Generic URL placeholder found"),
            ("Programming language and version", "Generic language placeholder found"),
        ]
        for phrase, description in template_phrases:
            if phrase in documentation:
                issues.append(description)
        if issues:
            return "PLACEHOLDER ISSUES DETECTED:\n" + "\n".join(
                f"- {issue}" for issue in issues
            )
        else:
            return "NO PLACEHOLDER ISSUES DETECTED - Documentation appears to use actual project content"

    def _call_enhanced_writer(
        self,
        context: Dict[str, Any],
        is_revision: bool = False,
        previous_doc: str = "",
        review: str = "",
    ) -> str:
        repo_name = context.get("repo_name", "Unknown Project")
        languages = ", ".join(context.get("languages", ["Unknown"]))
        frameworks = ", ".join(context.get("frameworks", ["None specified"]))
        total_chunks = context.get("total_chunks", 0)
        base_instructions = f"""
    CRITICAL INSTRUCTION: You are creating REAL documentation, NOT a template.
    If information is missing, skip it rather than filling up that section.
    YOUR TASK: {self.writer_prompt}

    NEVER OUTPUT PLACEHOLDER TEXT. Replace ALL {{}} placeholders with actual information.

    PROJECT CONTEXT:
    - Project Name: {repo_name}
    - Languages: {languages}
    - Frameworks: {frameworks}
    - Total Code Chunks Analyzed: {total_chunks}

    MANDATORY REPLACEMENTS:
    - {{{{Project Name}}}} → {repo_name}
    - {{{{Programming language}}}} → {languages}
    - {{{{Framework}}}} → {frameworks}
    - {{{{repository-url}}}} → {context.get('repo_source', 'Local project')}
    - ALL other {{{{placeholders}}}} → Real information from project analysis

    VERIFICATION CHECKLIST before submitting:
    ✓ No {{}} placeholder syntax remains
    ✓ All examples use actual project imports and classes
    ✓ All file paths are real project paths
    ✓ All configuration variables are from actual config files
    ✓ Installation commands are project-specific
    ✓ API endpoints are from actual code analysis
    """

        if is_revision:
            prompt = f"""
    {self.writer_prompt}

    {base_instructions}

    TASK: REVISE the documentation based on reviewer feedback. Fix ALL placeholder issues.

    REVIEWER FEEDBACK (MUST ADDRESS ALL POINTS):
    {review}

    PREVIOUS DOCUMENTATION (FIX ALL PLACEHOLDERS):
    {previous_doc}

    COMPREHENSIVE PROJECT ANALYSIS:
    {self._format_comprehensive_context(context)}

    TEMPLATE STRUCTURE TO FOLLOW (REPLACE ALL PLACEHOLDERS):
    {self.doc_template}

    FINAL CHECK: Ensure NO {{}} syntax remains and ALL content is project-specific.
    """
        else:
            prompt = f"""
    {self.writer_prompt}

    {base_instructions}

    TASK: Create comprehensive documentation with ZERO placeholder text.

    COMPREHENSIVE PROJECT ANALYSIS:
    {self._format_comprehensive_context(context)}

    TEMPLATE STRUCTURE TO FOLLOW (REPLACE ALL PLACEHOLDERS):
    {self.doc_template}

    EXAMPLES OF PROPER REPLACEMENT:
    Instead of: "{{{{Project Name}}}}" 
    Write: "{repo_name}"

    Instead of: "{{{{Programming language and version}}}}"
    Write: "{languages}"

    Instead of: "{{{{Framework used}}}}"
    Write: "{frameworks}"

    Generate comprehensive documentation with ALL placeholders replaced:
    """

        try:
            response = self.writer_llm.invoke(prompt)
            cleaned_response = self._clean_response(response)
            if self._contains_placeholders(cleaned_response):
                logger.warning(
                    "Writer output contains placeholders, attempting correction..."
                )
                cleaned_response = self._fix_common_placeholders(
                    cleaned_response, context
                )

            return cleaned_response
        except Exception as e:
            logger.error(f"Enhanced writer agent error: {e}")
            return self._fallback_documentation(context)

    def _call_enhanced_reviewer(
        self, documentation: str, context: Dict[str, Any]
    ) -> str:
        placeholder_check = self._check_for_placeholders(documentation)
        prompt = f"""
    {self.reviewer_prompt}

    CRITICAL FIRST CHECK: Does this documentation contain ANY template placeholders?
    YOUR TASK: {self.reviewer_prompt}

    PLACEHOLDER DETECTION RESULTS:
    {placeholder_check}

    DOCUMENTATION TO REVIEW:
    {documentation}

    COMPREHENSIVE PROJECT ANALYSIS:
    {self._format_comprehensive_context(context)}

    MANDATORY FAILURE CONDITIONS (Score 0-30 if ANY found):
    - ANY {{{{placeholder}}}} syntax remaining
    - Generic "Project Name" instead of actual project name
    - Template phrases like "Describe the..." or "Explain the..."
    - Generic examples not using actual project code
    - Placeholder URLs like "repository-url"

    ENHANCED REVIEW CRITERIA:
    1. PLACEHOLDER ELIMINATION (30 points) - MOST CRITICAL
    2. Technical Accuracy (25 points)
    3. Completeness & Coverage (20 points) 
    4. Developer Usability (15 points)
    5. Formatting & Presentation (10 points)

    SPECIFIC PROJECT CONTEXT TO VERIFY:
    - Project: {context.get('repo_name', 'Unknown')}
    - Languages: {', '.join(context.get('languages', []))}
    - Frameworks: {', '.join(context.get('frameworks', []))}
    - Architecture: {context['project_analysis'].get('architecture_type', 'Unknown')}

    Provide detailed review with score breakdown:
    """

        try:
            response = self.reviewer_llm.invoke(prompt)
            return response
        except Exception as e:
            logger.error(f"Enhanced reviewer agent error: {e}")
            return "SCORE: 0\nReview failed due to technical error. Documentation likely contains template placeholders."

    def _format_comprehensive_context(self, context: Dict[str, Any]) -> str:
        project_analysis = context["project_analysis"]
        structured_samples = context["structured_samples"]

        sections = [
            f"REPOSITORY INFORMATION:",
            f"- Name: {context['repo_name']}",
            f"- Source: {context['repo_source']}",
            f"- Architecture Type: {project_analysis['architecture_type']}",
            f"- Total Files Analyzed: {context['total_documents']}",
            f"- Total Code Chunks: {context['total_chunks']}",
            "",
            f"TECHNOLOGY STACK:",
            f"- Languages: {', '.join(context['languages'])}",
            f"- Frameworks: {', '.join(context['frameworks'])}",
            f"- Key Dependencies: {', '.join(list(project_analysis['dependencies'])[:10])}",
            "",
            f"CODE STRUCTURE ANALYSIS:",
            f"- Key Classes: {', '.join(project_analysis['key_classes'][:10])}",
            f"- Key Functions: {', '.join(project_analysis['key_functions'][:15])}",
            f"- API Endpoints: {len(project_analysis['api_endpoints'])} found",
            f"- Configuration Files: {len(project_analysis['configuration_files'])} found",
            "",
        ]

        for category, samples in structured_samples.items():
            if samples:
                sections.append(f"{category.upper()} EXAMPLES:")
                for i, sample in enumerate(
                    samples[:3], 1
                ):
                    content = sample.get("content", "")[:400]
                    file_path = self._extract_file_path_from_metadata(
                        sample.get("metadata", "")
                    )
                    sections.append(
                        f"  {i}. File: {Path(file_path).name if file_path else 'unknown'}"
                    )
                    sections.append(f"     Content: {content}...")
                    sections.append("")

        return "\n".join(sections)

    @staticmethod
    def _extract_file_path_from_metadata(metadata: str) -> str:
        try:
            if isinstance(metadata, str) and metadata:
                meta_dict = json.loads(metadata)
                return meta_dict.get("source_file", "")
        except:
            pass
        return ""

    @staticmethod
    def _save_generation_metadata(
        output_file: Path,
        context: Dict[str, Any],
        final_score: int,
        total_chunks: int,
    ):
        metadata = {
            "generation_info": {
                "total_chunks_analyzed": total_chunks,
                "total_documents": context["total_documents"],
                "final_quality_score": final_score,
                "architecture_type": context["project_analysis"]["architecture_type"],
            },
            "repository": {
                "id": context["repo_id"],
                "name": context["repo_name"],
                "source": context["repo_source"],
                "languages": context["languages"],
                "frameworks": context["frameworks"],
            },
            "analysis_summary": {
                "key_classes_count": len(context["project_analysis"]["key_classes"]),
                "key_functions_count": len(
                    context["project_analysis"]["key_functions"]
                ),
                "api_endpoints_count": len(
                    context["project_analysis"]["api_endpoints"]
                ),
                "dependencies_count": len(context["project_analysis"]["dependencies"]),
            },
        }
        metadata_path = output_file.with_suffix(".metadata.json")
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    @staticmethod
    def _extract_score_from_review(review: str) -> int:
        try:
            score_patterns = [
                r"SCORE:\s*(\d+)",
                r"Score:\s*(\d+)",
                r"score:\s*(\d+)",
                r"(\d+)/100",
                r"(\d+)%",
            ]
            for pattern in score_patterns:
                match = re.search(pattern, review)
                if match:
                    score = int(match.group(1))
                    return min(100, max(0, score))
            return 70
        except Exception as e:
            logger.warning(f"Could not extract score from review: {e}")
            return 70

    def _get_all_repository_ids(self) -> List[str]:
        with sqlite3.connect(self.batch_writer.sqlite_db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM repositories ORDER BY processed_at DESC")
            return [row[0] for row in cursor.fetchall()]

    def _get_repository_info(self, repo_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.batch_writer.sqlite_db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, source FROM repositories WHERE id = ?", (repo_id,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Repository {repo_id} not found")
            source = result[1]
            name = Path(source).name.replace(".git", "") if source else repo_id
            return {"id": result[0], "source": source, "name": name}

    def _get_repository_documents(self, repo_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.batch_writer.sqlite_db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute(
        """
               SELECT file_path, content_preview
               FROM documents
               WHERE repo_id = ?
               ORDER BY file_path
            """,(repo_id,),
            )
            return [
                {"file_path": row[0], "content_preview": row[1]}
                for row in cursor.fetchall()
            ]

    def _create_output_path(self, repo_name: str) -> Path:
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", repo_name)[:50]
        return self.output_dir / f"{safe_name}_comprehensive_docs.md"

    @staticmethod
    def _clean_response(response: str) -> str:
        response = response.strip()
        if response.startswith(("Here", "I'll", "Based on")):
            lines = response.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("#") or line.startswith("```"):
                    response = "\n".join(lines[i:])
                    break
        return response