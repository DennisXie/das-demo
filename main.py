import anyio
import uvicorn
from app import app, md_service

async def main():
    config = uvicorn.Config("main:app", host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(md_service.start)
        await server.serve()
        await md_service.stop()

if __name__ == "__main__":
    anyio.run(main)
