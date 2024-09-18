from enum import IntEnum, Enum


class RobotStatus(IntEnum):
    """robot的状态"""

    DESTROYED = -4
    """robot准备销毁，该状态仅用在judger代码里"""

    EMPTY = -3
    """robot已经创建，但未绑定账号密码"""

    OFFLINE = 0
    """robot离线，一般是judger刚启动时已经保存的robot没能登录"""

    OK = 1
    """robot准备就绪"""

    WORKING = 2
    """robot正在评测"""


class TraceStatus(IntEnum):
    """trace的状态"""

    OK = 0
    """投递成功"""

    ROBOT_NOT_FOUND = 2
    """找不到可以揽收的robot"""


class CheckpointStatus(IntEnum):
    """测试点状态"""

    WAITING = 0
    """正在等待robot揽收"""

    JUDGING = 1
    """已经揽收，正在评测"""

    AC = 2
    """通过"""

    WA = 3
    """答案错误"""

    TLE = 4
    """超出时间限制"""

    MLE = 5
    """超出空间限制"""

    RE = 6
    """运行时程序异常"""

    UKE = 7
    """出现未知错误"""

    PC = 8
    """测试点部分正确"""

    SE = 9
    """出现coj的系统错误"""

    CE = 10
    """编译错误"""


class ResponseCode(IntEnum):
    OK = 200
    SPACE = 100
    MSG = 102
    ERROR = 105
    NEED_VERIFY = 1000


class LogColor(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    BLACK = "black"
    BROWN = "brown"
