-- 初始化数据库的脚本，每次app.py启动时都会执行这个文件里的代码
-- 存放robot信息的表
create table if not exists tb_user(
    username varchar(255) not null,
    password varchar(255) not null
);

-- 设置pid可被哪一个robot揽收
create table if not exists tb_link(
    pid varchar(255) not null,
    username varchar(255) not null
);