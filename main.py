import anyio
import uvicorn
import json
from app import app, md_service, td_service
from tdclient import UserConfig

async def main():
    config = uvicorn.Config("main:app", host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    userConfigDict = None
    with open("config.json") as f:
        userConfigDict = json.load(f)

    userConfig: UserConfig = UserConfig(
        brokerId=userConfigDict["brokerId"],
        userId=userConfigDict["userId"],
        password=userConfigDict["password"],
        appId=userConfigDict["appId"],
        authCode=userConfigDict["authCode"]
    )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(md_service.start)
        task_group.start_soon(td_service.start, userConfig)
        await server.serve()
        await td_service.stop()
        await md_service.stop()

if __name__ == "__main__":
    anyio.run(main)
