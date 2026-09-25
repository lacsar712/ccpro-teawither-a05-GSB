# TeaWither-01 · 茶萎凋台账

Django 5 + PostgreSQL 服务端渲染应用：Templates + HTMX + 自定义 CSS，无 Vue/React SPA。

## 技术栈

- Django 5、PostgreSQL
- Session 登录
- HTMX（CDN）局部刷新列表
- Docker Compose：`web` + `db`

## 端口与数据库

| 服务 | 端口 |
|------|------|
| Web  | **4100** |
| Postgres | **5440**（容器内 5432） |

数据库账号：`teawither` / `teawither` / 库名 `teawither`

## 快速启动

```bash
cd TeaWither/TeaWither-01
docker compose up --build -d
```

浏览器打开：http://localhost:4100

演示账号：

- `admin` / `123456`（超级用户）
- `witherer` / `123456`（普通用户）

容器启动时会自动：`migrate` → `seed_data` → `collectstatic` → `gunicorn`

## 本地开发（可选）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 确保本机 Postgres 监听 5440，或先 docker compose up -d db
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5440
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:4100
```

## 业务模型

1. **Garden（茶园）**：`name`、`altitudeBand`、`notes`
2. **Trough（萎凋槽）**：归属茶园、`troughCode`、`cultivar`、`loadKg`、状态 `loading|withering|ready`；同一茶园内槽位编号唯一
3. **WitherBatch（萎凋批次）**：归属槽位、`startedAt`、`targetMoisture`、`actualMoisture`（可空）、`rollGrade`
4. **LeafReceipt（鲜叶签收）**：所属槽位、`kg`（鲜叶千克，必须为正）、`receivedAt`（签收时刻，默认当前时间）、`village`（供货村名）、`receiver`（签收人）

**业务规则**：

- 将槽位状态设为 `ready`（可下槽）时，若最新批次的 `actualMoisture` 为空或大于 40，抛出中文 `ValidationError`。

### 鲜叶签收规则

- **槽位状态**：仅「装叶中」（`loading`）槽可签收；「萎凋中」与「可下槽」槽位一律拒绝。签收表单的槽位下拉也只列出装叶中槽。
- **正数约束**：鲜叶千克必须为正（`> 0`），否则拒绝。
- **装叶量约束（累计）**：同一槽装叶中期间，累计签收千克不得超过该槽装叶量 `loadKg`；超出则整笔拒绝，错误信息回显该槽已累计签收千克与本次剩余可签容量。校验在模型 `clean()/save()` 中强制执行，不可能出现签收成功却未校验装叶量的情况。
- **目标含水联锁（单次）**：该槽若已存在萎凋批次，单次签收千克不得超过**同槽最新批次目标含水率百分数的数值本身**作为千克上限的约定——例如最新批次 `targetMoisture = 40.00`（%），则单次签收上限为 40kg（40.00 含等于放行，>40 拒绝）；该槽尚无批次时不启用此约定。
- **权限**：任何登录用户（含萎凋工 `witherer`）均可签收；**冲销签收仅主管**（`is_staff`，如 `admin`）可操作，普通萎凋工访问冲销页返回 403。
- **本周签收千克**：首页「本周签收(kg)」与鲜叶签收列表表尾合计同源，均以当前时区**周一 00:00** 为起点，列表中各行（标注「本周」）千克逐行相加必须等于首页数字。

> 种子数据中 `A-03` 槽装叶量 100kg、已累计签收 96kg，再签任意 >4kg 的一笔即触发超限拒绝；`A-02` 槽已有目标含水 40% 的批次且已签收 40kg，单笔超过 40kg 将触发联锁拒绝。

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有茶园则只保证账号存在。亦可在环境变量 `TEAWITHER_AUTO_SEED=1` 时于 `post_migrate` 自动播种。

## 目录结构

```
TeaWither-01/
  manage.py
  requirements.txt
  Dockerfile
  entrypoint.sh
  docker-compose.yml
  config/           # 项目配置
  apps/gardens/     # 模型、视图、种子命令
  templates/        # Django 模板
  static/css/       # 自定义样式（茶绿色顶栏）
```
