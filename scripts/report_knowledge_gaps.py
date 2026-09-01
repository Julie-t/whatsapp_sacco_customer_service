#!/usr/bin/env python
"""Print a compact knowledge-gap summary for a SACCO."""

import argparse

from app.services.knowledge_gap_repository import get_knowledge_gap_repository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sacco-id", default="demo_sacco")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    repository = get_knowledge_gap_repository()
    import asyncio

    async def report():
        summary = await repository.count_gaps_by_fallback(args.sacco_id)
        events = await repository.query_gaps_by_sacco(args.sacco_id, limit=args.limit)
        print(f"Knowledge gaps for SACCO: {args.sacco_id}")
        print("By fallback reason:")
        for reason, count in sorted(summary.items(), key=lambda item: item[1], reverse=True):
            print(f"  {reason}: {count}")
        print("Recent queries:")
        for event in events:
            print(f"  [{event.language}] {event.query}")

    asyncio.run(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
