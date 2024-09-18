from __future__ import annotations
from typing import Dict
import aiohttp

from . import utils, judger


class HttpClient:
    _session: aiohttp.ClientSession
    _target: judger.Judger

    def __init__(self):
        pass

    async def get(self, url: str, params: Dict) -> None:
        try:
            async with self._session.get(f"{self._target.server}{url}", params=params) as r:
                if r.status == 200:
                    data = await r.json()
                    if data["code"] == 200:
                        return
                    else:
                        self._target.logger.error(
                            f"请求COJ服务端时发生错误：响应代码异常\nGET {self._target.server}{url}\n{data}"
                        )
                else:
                    self._target.logger.error(
                        f"请求COJ服务端时发生错误：HTTP响应代码异常\nGET {self._target.server}{url}\nHTTP响应代码：{r.status}"
                    )
        except Exception as e:
            self._target.logger.error(
                f"请求COJ服务端时发生错误：请求异常\nGET {self._target.server}{url}\n{utils.get_exception_details(e, self._target)}"
            )

    async def post(self, url: str, data: Dict) -> None:
        try:
            async with self._session.post(f"{self._target.server}{url}", data=data) as r:
                if r.status == 200:
                    data = await r.json()
                    if data["code"] == 200:
                        return
                    else:
                        self._target.logger.error(f"请求COJ服务端时发生错误：响应代码异常\nPOST {self._target.server}{url}\n{data}")
                else:
                    self._target.logger.error(
                        f"请求COJ服务端时发生错误：HTTP响应代码异常\nPOST {self._target.server}{url}\nHTTP响应代码：{r.status}"
                    )
        except Exception as e:
            self._target.logger.error(
                f"请求COJ服务端时发生错误：请求异常\nPOST {self._target.server}{url}\n{utils.get_exception_details(e, self._target)}"
            )

    async def register(self, target: judger.Judger) -> bool:
        self._target = target
        self._session = aiohttp.ClientSession(headers={"Authorization": target.key})
        async with self._session.post(
                "{server}/register".format(server=target.server),
                data={"jid": target.jid, "remote": target.remote, "name": target.name}
        ) as r:
            if r.status == 200:
                data = await r.json()
                if data["code"] == 200:
                    return True
                target.logger.error(data)
            return False
