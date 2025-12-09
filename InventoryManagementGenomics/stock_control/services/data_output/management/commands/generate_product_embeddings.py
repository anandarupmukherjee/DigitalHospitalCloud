"""Management command to generate and cache product embeddings.

Usage (example):
  ./manage.py generate_product_embeddings --model /path/to/llm-model --output /tmp/product_embeddings.json

The command will iterate all Products, build a textual representation and
write a JSON file mapping product_id -> embedding list.
"""
from __future__ import annotations

import argparse
import json
import logging
from django.core.management.base import BaseCommand

from services.data_output.management.commands.data_output_listener import (
    LLMProductMatcher,
    SentenceTransformerEmbeddingProvider,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Precompute and cache product embeddings for LLM-based matching."

    def add_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            "--model",
            required=True,
            help="Path or name of the llm model to use for embeddings.",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Output JSON file for embeddings. Defaults to settings.DATA_OUTPUT_EMBEDDING_CACHE_FILE or data_output_product_embeddings.json",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recompute of all embeddings even if cache exists.",
        )

    def handle(self, *args, **options):
        model = options["model"]
        out = options.get("output")
        force = options.get("force", False)
        provider = SentenceTransformerEmbeddingProvider(model_name=model)
        matcher = LLMProductMatcher(provider, embedding_cache_path=out)

        # ensure_embeddings will compute missing embeddings and save cache
        matcher.ensure_embeddings(force=force)

        self.stdout.write(self.style.SUCCESS("Embeddings generation completed."))
