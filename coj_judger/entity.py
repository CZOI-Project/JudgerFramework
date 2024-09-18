from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict
import aiohttp

from . import constants, utils, judger


@dataclass
class Robot:
    """Robot实体"""

    uuid: str = ""
    """标识符"""

    password: str = ""
    """robot密码"""

    username: str = ""
    """robot账号"""

    status: constants.RobotStatus = constants.RobotStatus.EMPTY
    """robot状态"""

    session: Optional[aiohttp.ClientSession] = None
    """robot的session"""

    queue: Optional[asyncio.Queue] = None
    """评测队列"""


# 抛出的信息将会返回给coj服务端
class COJException(Exception):
    pass


@dataclass
class RobotDTO:
    """RobotDTO"""

    status: int
    """当前状态"""

    username: str
    """robot账号"""

    uuid: str
    """唯一标识符"""


@dataclass
class Trace:
    """Trace"""

    ids: List[int]
    """涉及到的测试点编号"""

    status: constants.TraceStatus
    """状态"""

    username: Optional[str] = None
    """揽收的robot的用户名，status为0时可用"""

    uuid: Optional[str] = None
    """揽收的robot的uuid，status为0时可用"""


@dataclass
class CheckpointToProblem:
    """CheckpointToProblem"""

    extra: str
    """提交给judger时附带信息，一般包含编译器参数等信息"""

    id: int
    """测试点序号"""

    jid: str
    """该测试点所用到的judger的id"""

    memLimit: int
    """内存限制，单位kb，注意，内存和时间限制需要与远程题目对应的一致，否则无法达到效果"""

    nth: int
    """远程题目测试点编号"""

    score: int
    """该测试点分数"""

    target: str
    """远程题目特征"""

    timeLimit: int
    """时间限制，单位ms"""


class CheckpointsPackage:
    rid: int
    """对应的rid"""

    code: str
    """评测代码"""

    checkpoints: Dict[int, CheckpointToProblem]
    """包含的测试点，key为测试点的本地编号"""

    still: List[int]
    """远程测试点中仍然没有完成的抓取的测试点编号"""

    _map: Dict[int, int]

    _judger: judger.Judger

    _robot: Robot

    def __init__(self, rid: int, code: str, checkpoints: List[CheckpointToProblem], _judger: judger.Judger, _robot: Robot):
        self.rid = rid
        self.checkpoints = {}
        self.code = code
        self._map = {}
        self.still = []
        for i in checkpoints:
            self.still.append(i.nth)
            self.checkpoints[i.id] = i
            self._map[i.nth] = i.id
        self._robot = _robot
        self._judger = _judger

    async def reject(self, status: constants.CheckpointStatus, log: str = None,
                     color: constants.LogColor = constants.LogColor.RED):
        """
        将剩余测试点的状态置为某个状态，并添加日志，这个通常位于评测过程中judger发生了内部错误
        :param status: 要设置的测试点状态
        :param log: 要附带的log，可选
        :param color: log的颜色，可选，默认为红色
        """
        if log is not None:
            log = f"[{self._judger.jid} - {self._robot.username}] 评测测试点时发生错误：\n{log}\n如下测试点受到影响：{utils.array_to_text(self.still)}"
            self._judger.logger.info(log)
            await self.log(log, color)
        await self.update(self.still, status)

    async def accept(self):
        await self.update(self.still, constants.CheckpointStatus.JUDGING)
        self._judger.logger.info(f"[{self._judger.jid} - {self._robot.username}] 开始评测：{self.rid}")

    async def log(self, message: str, color: constants.LogColor = constants.LogColor.RED):
        """
        给评测记录发送log
        :param message: log内容
        :param color: log颜色，默认为红色
        """
        await self._judger.http_client.post("/log", data={"rid": self.rid,
                                                          "message": f'<div class="mdui-text-color-{color}">{message}</div>'})

    async def update(
            self,
            ids: List[int],
            status: constants.CheckpointStatus = None,
            message: str = None,
            score: int = None,
            runTime: int = None,
            runMem: int = None,
            done: bool = False
    ):
        """
        更新测试点信息
        :param ids: 要更新的测试点编号
        :param status: 设置测试点为某状态，可选，不填就不设置
        :param message: 设置测试点的信息，可选，不填就不设置
        :param score: 设置测试点的分数，可选，不填就不设置
        :param runTime: 设置测试点的运行时间，单位ms，可选，不填就不设置
        :param runMem: 设置测试点的运行内存，单位mb，可选，不填就不设置
        :param done: 是否在更新完之后从still中删除该测试点
        """
        data = {"rid": self.rid, "ids": utils.array_to_text(ids)}
        if status is not None:
            data["status"] = status
        if message is not None:
            data["message"] = message
        if score is not None:
            data["score"] = score
        if runTime is not None:
            data["runTime"] = runTime
        if runMem is not None:
            data["runMem"] = runMem
        await self._judger.http_client.post("/update", data=data)
        if done:
            for i in ids:
                self.still.remove(self.checkpoints[i].nth)

    def r2l(self, remote_id: int) -> int:
        """
        远程测试点编号转本地测试点编号
        :param remote_id: 远程测试点编号
        :return: 本地测试点编号
        """
        return self._map[remote_id]

    def l2r(self, local_id: int) -> int:
        """
        本地测试点编号转远程测试点编号
        :param local_id: 本地测试点编号
        :return: 远程测试点编号
        """
        return self.checkpoints[local_id].nth
