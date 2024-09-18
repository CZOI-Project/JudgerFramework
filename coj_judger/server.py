from __future__ import annotations
import json
from dataclasses import asdict
from typing import List

from aiohttp import web
from aiohttp.web_response import Response

from . import judger, utils, constants, entity


class Controller:
    _judger: judger.Judger

    def __init__(self, target: judger.Judger):
        self._judger = target

    # /info
    async def info(self, request) -> Response:
        res = []
        for i in self._judger.robots.values():
            res.append(entity.RobotDTO(i.status, i.username, i.uuid))
        return utils.response_ok([asdict(item) for item in res])

    # /submit
    async def submit(self, request) -> Response:
        data = await request.post()
        checkpoints: List[entity.CheckpointToProblem] = [entity.CheckpointToProblem(**item) for item in json.loads(data["checkpoints"])]
        rid: int = data["rid"]
        code: str = data["code"]
        res: List[entity.Trace] = await self._judger.submit(checkpoints, code, rid)
        return utils.response_ok([asdict(item) for item in res])

    # /robot/create
    async def robot_create(self, request) -> Response:
        robot = await judger.create_robot()
        await self._judger.register_robot(robot)
        uuid: str = robot.uuid
        return utils.response_ok(uuid)

    # /robot/verify
    async def robot_verify(self, request) -> Response:
        uuid: str = request.query["uuid"]
        if uuid not in self._judger.robots:
            raise entity.COJException("robot不存在")
        res: str = await self._judger.event.robot_verify(self._judger.robots[uuid])
        return utils.response_ok(res)

    # /robot/login
    async def robot_login(self, request) -> Response:
        uuid: str = request.query["uuid"]
        if uuid not in self._judger.robots:
            raise entity.COJException("目标robot不存在")
        robot: entity.Robot = self._judger.robots[uuid]
        robot.username = request.query["username"]
        robot.password = request.query["password"]
        if "code" in request.query:
            code: str = request.query["code"]
            await self._judger.event.robot_login(robot, code)
        else:
            flag = await self._judger.event.robot_login(robot)
            if not flag:
                return utils.response_code(constants.ResponseCode.NEED_VERIFY)
        return utils.response_ok()

    # /link
    async def link(self, request) -> Response:
        option: int = request.query["option"]
        pid: str = request.query["pid"]
        if option == 0:
            await self._judger.data_source.link_all(pid)
        if option == 1:
            robot: str = request.query["robot"]
            if self._judger.data_source.link_exist(pid, robot):
                raise entity.COJException("已经设置目标题目能被该robot揽收")
            await self._judger.data_source.link_add(pid, robot)
        if option == 2:
            robot: str = request.query["robot"]
            if not self._judger.data_source.link_exist(pid, robot):
                raise entity.COJException("未设置目标题目能被该robot揽收")
            await self._judger.data_source.link_del(pid, robot)
        if option == 3:
            data = await self._judger.data_source.link_list(pid)
            return utils.response_ok(data)
        return utils.response_ok()

    # /robot/delete
    async def robot_delete(self, request) -> Response:
        uuid = request.query["uuid"]
        if uuid not in self._judger.robots:
            raise entity.COJException("Robot不存在")
        await self._judger.delete_robot(self._judger.robots[uuid])
        return utils.response_ok()


class HttpServer:
    _judger: judger.Judger
    _controller: Controller

    def __init__(self, target: judger.Judger):
        self._judger = target
        self._controller = Controller(target)

    @web.middleware
    async def _error_middleware(self, request, handler):
        try:
            response = await handler(request)
            if response.status == 404:
                return utils.response_code(constants.ResponseCode.SPACE)
            return response
        except entity.COJException as e:
            return utils.response_message(str(e))
        except Exception as e:
            self._judger.logger.error(utils.get_exception_details(e, self._judger))
            return utils.response_message(utils.get_exception_details(e, self._judger))

    async def start(self):
        app = web.Application(middlewares=[self._error_middleware])
        app.router.add_routes([
            web.get('/info', self._controller.info),
            web.post('/submit', self._controller.submit),
            web.get('/robot/create', self._controller.robot_create),
            web.get('/robot/verify', self._controller.robot_verify),
            web.get('/robot/login', self._controller.robot_login),
            web.get('/robot/delete', self._controller.robot_delete),
            web.get('/link', self._controller.link),
        ])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self._judger.host, self._judger.port)
        await site.start()
