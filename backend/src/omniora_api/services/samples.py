"""SAMPLE DATA served by GET /projects/samples. Mirrors `src/services/demo/sample-projects.ts`.
Illustrative fixtures only: never stored, never generated, always read-only."""

from __future__ import annotations

from typing import Any

SAMPLE_PROJECTS: list[dict[str, Any]] = [
    {
        "id": "sample_fashion-store",
        "source": "sample",
        "status": "configured",
        "createdAt": "2026-09-02T10:00:00.000Z",
        "updatedAt": "2026-09-02T10:00:00.000Z",
        "configuration": {
            "name": "Atelier Commerce",
            "description": "Premium fashion e-commerce storefront with curated collections, cart, and checkout.",
            "platform": "website",
            "referenceUrl": "",
            "stack": {"mode": "custom", "technologies": ["nextjs", "postgresql"]},
            "requirements": {"features": ["authentication", "database", "payments", "admin-dashboard"], "custom": ""},
        },
    },
    {
        "id": "sample_fitness-tracker",
        "source": "sample",
        "status": "configured",
        "createdAt": "2026-09-14T15:30:00.000Z",
        "updatedAt": "2026-09-14T15:30:00.000Z",
        "configuration": {
            "name": "Stride Fitness",
            "description": "Cross-platform fitness tracking app with workout logging and progress charts.",
            "platform": "mobile",
            "referenceUrl": "",
            "stack": {"mode": "custom", "technologies": ["flutter", "fastapi", "postgresql"]},
            "requirements": {"features": ["authentication", "database", "notifications"], "custom": ""},
        },
    },
    {
        "id": "sample_support-desk",
        "source": "sample",
        "status": "configured",
        "createdAt": "2026-10-01T09:15:00.000Z",
        "updatedAt": "2026-10-01T09:15:00.000Z",
        "configuration": {
            "name": "Relay Support",
            "description": "Customer support platform with ticket routing and an AI-assisted reply composer.",
            "platform": "both",
            "referenceUrl": "",
            "stack": {"mode": "recommend"},
            "requirements": {
                "features": ["authentication", "database", "notifications", "automated-tests"],
                "custom": "Role-based access for agents and supervisors.",
            },
        },
    },
]

SAMPLE_IDS = frozenset(sample["id"] for sample in SAMPLE_PROJECTS)
