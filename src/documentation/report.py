#!/usr/bin/env python3

import json
import hashlib
import sqlite3
from pathlib import Path
import src.documentation.simple_generator as sg
from src.database.qdrant_writer import QdrantBatchWriter
from src.documentation.simple_generator import EnhancedDocumentationGenerator


def generate_comprehensive_documentation():
    try:
        generator = EnhancedDocumentationGenerator()
        results = generator.generate_documentation_for_all_repos()
        successful = sum(1 for r in results if r.success)
        total = len(results)

        if successful > 0:
            avg_score = sum(r.final_score for r in results if r.success) / successful
            total_chunks = sum(r.total_chunks_analyzed for r in results)

            print(f"Enhanced Documentation Results:")
            print(f"   • Successfully generated: {successful}/{total} repositories")
            print(f"   • Average quality score: {avg_score:.1f}/100")
            print(f"   • Total chunks analyzed: {total_chunks}")

            docs_dir = Path("storage/documentation")
            if docs_dir.exists():
                print(f"\nGenerated Documentation Files:")
                for result in results:
                    if result.success:
                        file_size = result.output_file.stat().st_size / 1024  # KB
                        print(f"   • {result.output_file.name}")
                        print(f"     ├─ Quality Score: {result.final_score}/100")
                        print(f"     ├─ File Size: {file_size:.1f} KB")
                        print(f"     ├─ Chunks Analyzed: {result.total_chunks_analyzed}")
                        metadata_file = result.output_file.with_suffix(".metadata.json")

                        if metadata_file.exists():
                            print(f"     ├─ Metadata: {metadata_file.name}")

                        try:
                            content = result.output_file.read_text(encoding="utf-8")
                            first_lines = "\n".join(content.split("\n")[:3])
                            print(f"     └─ Preview: {first_lines[:100]}...")
                        except:
                            pass
                        print()
        else:
            print("No documentation was generated successfully")
    except ImportError as e:
        print(f"❌ Enhanced generator import failed: {e}")
        print("❌ Let's check what's available in the simple_generator file...")

        try:
            available_classes = [
                name
                for name in dir(sg)
                if not name.startswith("_") and name[0].isupper()
            ]
            print(f"Available classes: {available_classes}")

            if hasattr(sg, "EnhancedDocumentationGenerator"):
                generator = sg.EnhancedDocumentationGenerator()
                results = generator.generate_documentation_for_all_repos()
                successful = sum(1 for r in results if r.success)
                print(f"Generated documentation for {successful}/{len(results)} repositories")
            else:
                print("No suitable generator class found")
        except Exception as inner_e:
            print(f"❌ Could not analyze simple_generator: {inner_e}")
    except Exception as e:
        print(f"❌ Documentation generation failed: {e}")


def analyze_repository_content():
    print("🔍 Analyzing repository content...")

    try:
        batch_writer = QdrantBatchWriter.get_instance()
        stats = batch_writer.get_repository_stats()

        print(f"Repository Database Analysis:")
        print(f"   • Total repositories: {stats['total_repositories']}")
        print(f"   • Total documents: {stats['total_documents']}")
        print(f"   • Total chunks: {stats['total_chunks']}")
        print(f"   • Total vectors: {stats['total_vectors']}")

        if stats["repositories"]:
            print(f"\n📋 Repository Details:")
            for i, repo in enumerate(stats["repositories"][:5], 1):  # Show first 5
                print(f"   {i}. {Path(repo['source']).name}")
                print(f"      ├─ Files: {repo['files']}")
                print(f"      ├─ Chunks: {repo['chunks']}")
                print(f"      └─ Processed: {repo['processed_at']}")

            if len(stats["repositories"]) > 5:
                print(
                    f"      ... and {len(stats['repositories']) - 5} more repositories"
                )

        if stats["repositories"]:
            first_repo_source = stats["repositories"][0]["source"]
            print(f"\nDetailed Analysis for: {Path(first_repo_source).name}")
            repo_id = f"repo_{hashlib.md5(first_repo_source.encode()).hexdigest()[:12]}"

            with batch_writer.sqlite_lock:
                with sqlite3.connect(batch_writer.sqlite_db_path, timeout=30) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM chunks WHERE repo_id = ?", (repo_id,))
                    total_chunks = cursor.fetchone()[0]
                    print(f"   📊 Total chunks for this repository: {total_chunks}")
                    cursor.execute(
                """
                       SELECT metadata, COUNT(*) as chunk_count
                       FROM chunks
                       WHERE repo_id = ?
                       GROUP BY metadata
                       ORDER BY chunk_count DESC LIMIT 10
                    """,(repo_id,),
                    )

                    chunk_distribution = cursor.fetchall()
                    if chunk_distribution:
                        print(f"   📂 Top File Types by Chunk Count:")
                        for metadata, count in chunk_distribution:
                            try:
                                meta_dict = json.loads(metadata) if metadata else {}
                                file_path = meta_dict.get("source_file", "unknown")
                                file_ext = Path(file_path).suffix or "no extension"
                                file_name = Path(file_path).name
                                print(
                                    f"      • {file_name}: {count} chunks ({file_ext})"
                                )
                            except:
                                print(f"      • Unknown file: {count} chunks")

    except Exception as e:
        print(f"❌ Repository analysis failed: {e}")
