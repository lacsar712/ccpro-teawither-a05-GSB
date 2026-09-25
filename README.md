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
4. **LeafIntake（鲜叶签收）**：归属槽位、`leafKg`、`receivedAt`、`supplierVillage`、`receiver`；冲销字段 `isReversed`、`reversedAt`、`reversedBy`

**业务规则**：将槽位状态设为 `ready`（可下槽）时，若最新批次的 `actualMoisture` 为空或大于 40，抛出中文 `ValidationError`。

**鲜叶签收约定**：

- 仅状态为「装叶中」的槽位可签收；「萎凋中」「可下槽」一律拒绝。
- `leafKg`（鲜叶千克）必须为正数。
- 同一槽位装叶期间，未冲销签收的累计千克不得超过该槽 `loadKg`（装叶量）；超出即拒绝，并在错误信息中回显该槽已累计千克。
- 若该槽已有萎凋批次，单次签收千克还不得超过同槽最新批次 `targetMoisture` 的数值本身（约定：目标含水率 40% 即单次上限 40 kg），违者拒绝。
- 上述校验在模型层强制执行（`LeafIntake.save()` 先 `full_clean()`），任何入口都无法在跳过装叶量校验的情况下签收成功。
- 萎凋工（普通账号）可登记签收；**冲销签收仅主管（超级用户）可操作**。冲销后记录保留在库但不再显示于签收列表，也不计入槽位累计与首页本周合计。
- 首页「本周签收(kg)」= 签收列表中本周（周一 00:00 起）未冲销各行千克之和。

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有茶园则只保证账号存在。亦可在环境变量 `TEAWITHER_AUTO_SEED=1` 时于 `post_migrate` 自动播种。

种子数据中，装叶中槽 `云雾岭一号园-A-02`（装叶量 95 kg，最新批次目标含水率 40%）已签收两笔各 40 kg（累计 80 kg）：再签收 >15 kg 即触发累计超限（回显已累计 80 kg），单次 >40 kg 则触发目标含水联锁上限，可直接演示两类拒绝。

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
