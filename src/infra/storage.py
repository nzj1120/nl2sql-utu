"""
Context persistence helper.
"""

import json
import os
from typing import Optional

from src.core.context import QueryContext


class ContextStore:
    """
    Persists QueryContext objects for auditing and evaluation.
    """

    def __init__(self, base_dir: str = "output/contexts"):
        """
        Initialize the store with a base directory.
        """
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, ctx: QueryContext) -> str:
        """
        Write the context to a JSON file and return the path.
        """
        path = os.path.join(self.base_dir, f"{ctx.query_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ctx.to_dict(), f, ensure_ascii=False, indent=2)
        return path
