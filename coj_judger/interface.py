from __future__ import annotations
import abc
import os
from typing import List, Optional
import aiosqlite

from . import entity, judger


class DataInterface(metaclass=abc.ABCMeta):
    """持久化数据操作的接口"""

    @abc.abstractmethod
    async def init(self):
        """初始化数据源"""
        pass

    @abc.abstractmethod
    async def select_all_robot(self) -> List[entity.Robot]:
        """
        获取数据库中所有的robot
        :return: 所有的robot列表，只需要初始化username和password等信息即可
        """
        pass

    @abc.abstractmethod
    async def delete_robot(self, robot: entity.Robot):
        """从数据库中删除某个robot"""
        pass

    @abc.abstractmethod
    async def link_all(self, pid: str):
        """
        允许一个题目能被所有robot揽收
        :param pid: 目标题目编号
        """
        pass

    @abc.abstractmethod
    async def link_add(self, pid: str, robot: str):
        """
        让一个题目可以被某个robot揽收
        :param pid: 目标题目编号
        :param robot: 目标robot用户名
        """
        pass

    @abc.abstractmethod
    async def link_del(self, pid: str, robot: str):
        """
        让一个题目不能被某个robot揽收
        :param pid: 目标题目编号
        :param robot: 目标robot用户名
        """
        pass

    @abc.abstractmethod
    async def link_list(self, pid: str) -> List[str]:
        """
        获取一个题目能被哪些robot揽收，返回这些robot的用户名的list
        :param pid: 目标题目编号
        """
        pass

    @abc.abstractmethod
    async def link_exist(self, pid: str, robot: str) -> bool:
        """
        判断一个题目是否可被某个robot揽收
        :param pid: 目标题目编号
        :param robot: 目标robot用户名
        """
        pass


class DefaultDataSource(DataInterface):
    """
    默认的数据接口实现，关于该默认数据接口的更多信息见参考文档
    """

    _conn: aiosqlite.Connection

    async def init(self):
        self._conn = await aiosqlite.connect('database.db')
        if os.path.exists("init.sql"):
            with open('init.sql', 'r', encoding='utf-8') as f:
                sql = f.read()
                await self._conn.executescript(sql)
                await self._conn.commit()  # 提交更改

    async def select_all_robot(self) -> List[entity.Robot]:
        res: List[entity.Robot] = []
        async with self._conn.execute("select * from tb_user") as cursor:
            async for i in cursor:
                # 创建robot实体
                robot = await judger.create_robot()
                robot.username = i[0]
                robot.password = i[1]
                res.append(robot)
        return res

    async def link_all(self, pid: str) -> None:
        # 全部删除就相当于都可以揽收
        await self._conn.execute("delete from tb_link where pid = '{}'".format(pid))
        await self._conn.commit()

    async def link_add(self, pid: str, robot: str) -> None:
        await self._conn.execute("insert into tb_link(pid, username) values ({}, {})".format(pid, robot))
        await self._conn.commit()

    async def link_del(self, pid: str, robot: str) -> None:
        await self._conn.execute(
            "delete from tb_link where pid = '{}' and username = '{}'".format(pid, robot)
        )
        await self._conn.commit()

    async def link_list(self, pid: str) -> List:
        _list = []
        async with self._conn.execute("select * from tb_link where pid = '{}'".format(pid)) as cursor:
            async for item in cursor:
                _list.append(item[1])
        return _list

    async def link_exist(self, pid: str, robot: str) -> bool:
        async with self._conn.execute("select count(*) from tb_link where pid = '{}'".format(pid)) as cursor:
            row = await cursor.fetchone()
            return row[0] != 0

    async def delete_robot(self, robot: entity.Robot):
        await self._conn.execute("delete from tb_user where username = '{}'".format(robot.username))
        await self._conn.commit()

    async def insert_robot(self, robot: entity.Robot):
        await self._conn.execute(
            "replace into "
            "tb_user (username,password) "
            "values ('{}','{}')".format(
                robot.username,
                robot.password
            )
        )
        await self._conn.commit()


class EventInterface(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def robot_init(self, robot: entity.Robot) -> None:
        """
        judger注册时会调用该方法，该方法应预先初始化目标robot，并自行决定是否要注册到judger中
        :param robot: 要初始化的robot，基本信息已经获取完毕了
        """
        pass

    @abc.abstractmethod
    async def robot_verify(self, robot: entity.Robot) -> str:
        """
        对指定robot进行登陆验证
        :param robot: 要进行验证的robot
        :return: 图像验证码的url
        """
        pass

    @abc.abstractmethod
    async def robot_login(self, robot: entity.Robot, code: Optional[str] = None) -> bool:
        """
        对指定robot进行登录，如果登录中间发生意外则抛出COJException
        :param robot: 要登录的robot
        :param code: 可选，用于登录的验证码
        :return: true为登录成功，false为需要验证
        """
        pass

    @abc.abstractmethod
    async def keepalive(self, robot: entity.Robot) -> None:
        """
        保活任务
        :param robot: 要保活的robot
        """
        pass

    @abc.abstractmethod
    async def handle(self, robot: entity.Robot, pack: entity.CheckpointsPackage) -> None:
        """
        处理评测请求
        :param robot: 负责该评测请求的robot
        :param pack: 该评测请求的评测包
        """
