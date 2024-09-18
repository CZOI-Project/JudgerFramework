from __future__ import annotations
import asyncio
import json
import logging
import uuid
from typing import Dict, List

import aiohttp
from aiohttp import TCPConnector

from . import api, utils, interface, entity, constants
from . import server as service


async def create_robot() -> entity.Robot:
    """
    创建空白的robot实体
    :return: 空白robot实体
    """
    robot = entity.Robot()
    robot.uuid = str(uuid.uuid4())
    robot.queue = asyncio.Queue()
    robot.jar = aiohttp.CookieJar(unsafe=True)
    robot.session = aiohttp.ClientSession(
        connector=TCPConnector(ssl=False),
        json_serialize=json.dumps,
        cookie_jar=robot.jar
    )
    return robot


class Judger:
    jid: str
    name: str
    remote: str
    port: int
    host: str
    key: str
    server: str
    keepalive_time: int
    ping_time: int
    robots: Dict[str, entity.Robot] = {}
    data_source: interface.DataInterface
    http_client: api.HttpClient
    logger: logging.Logger
    event: interface.EventInterface
    http_server: service.HttpServer

    def __init__(
            self,
            jid: str, name: str, server: str, key: str, remote: str, event: interface.EventInterface,
            port: int = -1,
            host: str = "0.0.0.0",
            keepalive_time: int = 3600,
            ping_time: int = 30,
            logger: logging.Logger = None,
            datasource: interface.DataInterface = None,
    ):
        """
        新建一个Judger示例

        :param jid: judger的id
        :param name: judger的name
        :param server: coj服务端请求地址，带http头，末尾不带斜杠，如http://localhost:8080/judger
        :param key: 用于与coj服务端通信的密钥
        :param remote: 访问该judger需要使用的地址，带http头，末尾不带斜杠
        :param event: 事件

        :param port: 可选。监听端口。为空时自动分配端口，此时remote参数可以添加{port}占位符，会将自动分配到的端口填入占位符中
        :param host: 可选。本地监听地址。为空时默认为0.0.0.0
        :param keepalive_time: 可选。保活任务执行间隔，单位s。为空时默认为 60 * 60 即一个小时
        :param ping_time: 可选。向服务器发送ping保活的时间间隔，单位s。为空时默认为30
        :param logger: 可选。为空时使用自动生成一个默认的logger
        :param datasource: 可选。可持久化数据源。为空时使用默认本地数据源
        """
        self.jid = jid
        self.name = name
        self.server = server
        self.key = key
        self.remote = remote
        self.event = event
        if port != -1:
            self.port = port
        else:
            self.port = utils.get_free_port()
            self.remote = self.remote.replace("{port}", str(self.port))
        self.host = host
        self.keepalive_time = int(keepalive_time)
        self.ping_time = int(ping_time)
        if logger is None:
            self.logger = utils.get_logger()
        else:
            self.logger = logger
        if datasource is None:
            self.data_source = interface.DefaultDataSource()
        else:
            self.data_source = datasource

    async def register_robot(self, robot: entity.Robot):
        """
        将一个robot注册到judger中
        注册前请自行设置robot的状态
        :param robot: 要注册的robot
        """
        self.robots[robot.uuid] = robot
        asyncio.gather(self._robot_loop(robot))

    async def delete_robot(self, robot: entity.Robot):
        """
        删除一个robot，如果这个robot已经被注册到judger中的话也会注销
        :param robot: 要删除的robot
        """
        if robot.status != constants.RobotStatus.EMPTY:
            await self.data_source.delete_robot(robot)
        robot.status = constants.RobotStatus.DESTROYED
        await robot.session.close()
        if robot.uuid in self.robots:
            self.robots.pop(robot.uuid)

    async def _robot_loop(self, robot: entity.Robot):
        # robot的事件循环，循环监听队列中的评测请求
        while robot.status != constants.RobotStatus.DESTROYED:  # 当前状态不为准备销毁
            pack: entity.CheckpointsPackage = await robot.queue.get()
            robot.status = constants.RobotStatus.WORKING  # 置robot状态为正在评测
            try:
                await self.event.handle(robot, pack)
            except Exception as e:
                await pack.reject(constants.CheckpointStatus.SE, utils.get_exception_details(e, self))
            await asyncio.sleep(2)  # 评测完毕后最好robot有个冷却时间防止频繁请求
            robot.status = constants.RobotStatus.OK  # 置robot状态为准备就绪
            self.logger.info(f"{pack.rid} 评测结束")

    async def _keepalive_loop(self):
        await asyncio.sleep(self.keepalive_time)
        for robot in self.robots.values():
            if robot.status in [constants.RobotStatus.OK, constants.RobotStatus.WORKING]:
                try:
                    await self.event.keepalive(robot)
                except Exception as e:
                    self.logger.error(f"保活robot：{robot.username} 时发生错误：\n{utils.get_exception_details(e, self)}")

    async def submit_select_robot(self, wait_list=None) -> str | None:
        # 分配一个robot
        # wait_list为在指定名单里选择，wait_list为None则为任意选择
        # 返回uuid，或者None，此时为没有满足要求的

        # 准备ok_list
        ok_list = []
        if wait_list is None:
            # 可以随便选
            for robot in self.robots.values():
                if robot.status in [constants.RobotStatus.OK, constants.RobotStatus.WORKING]:
                    ok_list.append(robot)
        else:
            for robot in self.robots.values():
                if robot.status not in [constants.RobotStatus.OK, constants.RobotStatus.WORKING]:
                    continue
                if robot.username not in wait_list:
                    continue
                ok_list.append(robot)
        # 现在ok_list里的robot理论上都是满足要求的
        # 我们选择最优的那个
        minn = 999999999
        _uuid = None
        for robot in ok_list:
            if robot.queue.qsize() < minn:
                _uuid = robot.uuid
            # 这里将来可能再加个优化什么的
        return _uuid

    async def register(self):
        self.logger.info("COJ Judger Powered by Python")
        self.logger.info("连接数据库...")
        await self.data_source.init()
        self.logger.info("初始化robots...")
        # 先获取所有robot
        robots = await self.data_source.select_all_robot()
        for robot in robots:
            self.logger.info("初始化 {} - {}".format(robot.uuid, robot.username))
            await self.event.robot_init(robot)
        self.logger.info("启动judger服务...")
        self.http_server = service.HttpServer(self)
        await self.http_server.start()
        self.logger.info(f"监听在：{self.port}")
        self.http_client = api.HttpClient()
        flag = await self.http_client.register(self)
        if not flag:
            self.logger.error("注册judger服务失败，可能是jid已经被占用")
        asyncio.gather(self._keepalive_loop())
        self.logger.info("judger服务启动完毕")
        while True:
            await asyncio.sleep(1)

    async def submit(self, checkpoints: List[entity.CheckpointToProblem], code: str, rid: int) -> List[entity.Trace]:
        """
        让judger处理一个评测请求
        :param checkpoints: 要处理的测试点
        :param code: 评测代码
        :param rid: 评测记录id
        :return: 包含trace的list
        """
        # 将要返回的数据
        data: List[entity.Trace] = []
        # 先把checkpoint按pid分组
        index: Dict[str, List[entity.CheckpointToProblem]] = {}
        for checkpoint in checkpoints:
            if checkpoint.target in index:
                index[checkpoint.target].append(checkpoint)
            else:
                index[checkpoint.target] = [checkpoint]
        # 按分组投递
        # 一个分组就会引发一个评测请求
        for target in index.keys():
            ids: List[int] = []
            for checkpoint in index[target]:
                ids.append(checkpoint.id)
            # 先按照target找wait_list
            wait_list: List[str] = await self.data_source.link_list(target)
            # 匹配合适的robot
            target_uuid = await self.submit_select_robot(wait_list if len(wait_list) > 0 else None)
            # 没有合适的就寄了
            if target_uuid is None:
                data.append(entity.Trace(ids, constants.TraceStatus.ROBOT_NOT_FOUND))
                continue
            # 投递，把一个评测包投递过去
            await self.robots[target_uuid].queue.put(entity.CheckpointsPackage(
                rid,
                code,
                index[target],
                self,
                self.robots[target_uuid]
            ))
            data.append(entity.Trace(ids, constants.TraceStatus.OK, uuid=target_uuid, username=self.robots[target_uuid].username))
        return data
