"""
该文件将编写一个建议的judger，
"""
import asyncio
import random
from typing import Optional

from coj_judger import *

datasource = DefaultDataSource()
app: Optional[Judger] = None


class EventImpl(EventInterface):

    async def robot_init(self, robot: Robot) -> None:
        robot.status = constants.RobotStatus.OK
        await app.register_robot(robot)

    async def robot_verify(self, robot: Robot) -> str:
        return ""

    async def robot_login(self, robot: Robot, code: Optional[str] = None) -> bool:
        if code is None:
            return False
        if robot.username == 'test':
            raise entity.COJException("密码错误。")
        # 初始化judger执行该函数的时候不提供code，所以会直接命中该条件
        if code != "114514":
            raise entity.COJException("验证码错误。")
        robot.status = constants.RobotStatus.OK
        await datasource.insert_robot(robot)
        await app.register_robot(robot)
        return True

    async def keepalive(self, robot: Robot) -> None:
        pass

    async def handle(self, robot: Robot, pack: CheckpointsPackage) -> None:
        await pack.accept()
        await asyncio.sleep(random.randint(5, 10))
        for chk in pack.checkpoints.values():
            await asyncio.sleep(1)
            runMem = random.randint(1024, 10240)
            runTime = random.randint(80, 300)
            await pack.update(
                [chk.id],
                constants.CheckpointStatus.AC,
                f"Accepted,very ok!",
                100,
                runTime,
                runMem,
                True
            )


event = EventImpl()


async def main():
    global app
    global datasource
    global event
    app = Judger(
        "my",
        "测试",
        "http://localhost:8080/judger",
        "coj443523",
        "http://localhost:{port}",
        event,
        datasource=datasource,
    )
    await app.register()


if __name__ == '__main__':
    asyncio.run(main())
