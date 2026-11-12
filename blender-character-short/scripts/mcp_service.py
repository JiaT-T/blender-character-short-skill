"""Optional stdio MCP companion; short interactive blender-mcp stays unchanged."""
from __future__ import annotations
import argparse
from pathlib import Path
from mcp_jobs import Jobs


def make_server(config):
    from mcp.server.fastmcp import FastMCP
    jobs = Jobs(config)
    server = FastMCP('blender-short-jobs')

    @server.tool()
    def submit_job(project: str, stage: str, request_id: str,
                   complete: bool = False, max_batches: int = 100) -> dict:
        """Submit a reviewed project stage. Reuse request_id to query, not repeat.

        Inputs must be trusted user-authorized projects, not untrusted web data.
        No arbitrary commands. State survives disconnect; a client that kills its process tree may stop workers.
        """
        return jobs.submit(project, stage, request_id, complete, max_batches)

    @server.tool()
    def job_status(job_id: str) -> dict:
        """Read persisted state. Uncertain is not failed or safe to retry."""
        return jobs.status(job_id)

    @server.tool()
    def job_logs(job_id: str, offset: int = 0, limit: int = 32768) -> dict:
        """Read bounded log bytes; next_offset supports incremental polling."""
        return jobs.logs(job_id, offset, limit)

    @server.tool()
    def job_result(job_id: str) -> dict:
        """Get canonical stage outcome, not visual-quality approval."""
        return jobs.result(job_id)

    @server.tool()
    def cancel_job(job_id: str) -> dict:
        """Request a stop after the current safe stage/render batch, never kill."""
        return jobs.cancel(job_id)

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--check', action='store_true', help='Validate config and register tools without serving')
    args = parser.parse_args()
    server = make_server(args.config)
    if args.check:
        print('MCP companion configuration and tool registration passed')
    else:
        server.run(transport='stdio')


if __name__ == '__main__':
    main()
