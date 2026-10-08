# Grok Bot 的 CPA 接入与 Tailnet 恢复

源码归 `app-configs/grokbot`，NAS 正式部署沿用 `ai` 组的 `cli-proxy-api`，没有新增容器。

## CPA 调用

- 本地地址：`http://192.168.31.201:8317/v1`
- 模型名：`grokbot`
- 使用现有 CPA 客户端密钥。
- 既有渠道 `grokbot-cursor` 已更新为 `http://100.103.12.86:1341/v1`，并显式使用 `proxy-url: direct`。

当前 Grok Gateway 不提供模型列表和模型切换 API。旧版 `agentDefaultModel` 字段已移除，因此没有继续发布原渠道的 13 个 Claude/Grok 模型别名。`grokbot` 指向 Bot 默认模型；模型名称不代表可下载的模型权重。

`proxy.js` 将文本消息交给原有专用 `cursor-proxy-agent`，按 `clientNonce` 和 `requestId` 获取回复。该 Agent 保留对话上下文。这是 Agent 对话适配；工具调用、图片输入和结构化输出会被拒绝。SSE 在 Agent 产生回复后发送，不能提供底层模型的实时 token 流，也不能保证 Agent 不执行自身工具。token 用量为估算值。

适配器只监听 `127.0.0.1:1341`，由 Tailscale Serve 的 TCP 1341 转发。没有启用 Funnel。模型接口额外验证独立密钥；Gateway 原有监听配置未修改。适配器每次请求重新发现 `sand-data/gateway.json`，不会把 Gateway token 写入 Git 或请求日志。

NAS 渠道配置在 `/vol2/1000/Docker/CPA/config.yaml`。桥接密钥保存在 `/vol2/1000/Docker/stacks/ai/env/grokbot-bridge.json` 和 Bot 的私有适配器配置中；这些文件均为 0600，不进入本仓库。

## 恢复

Bot 上的持久文件：

- `/home/box/cli-config/grokbot/recover.py`：幂等恢复命令和后台守护。
- `/home/box/cli-config/grokbot/bin/`：保留的 Tailscale 二进制。
- `/home/box/cli-config/grokbot/tailscaled.state`：已有 Tailnet 身份及配置，0600。
- `/home/box/cursor-proxy/`：适配器、专用 Agent ID 和私有配置。

这些路径属于当前平台开启的 box-store 同步范围。守护每 5 秒检查 Tailscale 和适配器进程，异常退出后重启，并保留原身份。Tailscale 继续使用 userspace networking 和 Tailscale SSH；没有安装 OpenSSH，也没有变更 DNS、Exit Node、系统代理或防火墙。

已部署的首版从持久目录运行 Tailscale。普通环境重启的入口已写入 `/usr/local/bin/start-sand-box`，在 box-store 恢复后启动守护。平台镜像重建可能覆盖该系统入口，`recover.py ensure` 会重新安装启动入口并部署服务。

仓库中的修订版准备将运行二进制部署到 `/usr/local/libexec/grokbot/`（root 所有），运行状态恢复到 `/var/lib/tailscale/`，另保存 SSH host key 的私有备份 `ssh-host-keys.tar`。**该修订版尚未部署**，需要先恢复 SSH 访问。

在 Grok Bot 的 Computer 终端运行：

```bash
python3 /home/box/cli-config/grokbot/recover.py ensure
python3 /home/box/cli-config/grokbot/recover.py status
```

从能连接 Bot 的 Mac 运行：

```bash
ssh box@100.103.12.86 'python3 /home/box/cli-config/grokbot/recover.py ensure'
```

若重建后 Tailscale 尚未启动，应在 Grok Bot 中执行恢复命令，SSH 此时无法提供初次恢复入口。

Grok Bot 主 Bot 上已配置每天 **06:30（Asia/Shanghai）** 的“Tailnet 与 CPA 每日恢复”，规格见 `daily-recovery.json`。每日任务会唤起 Bot，可能计入模型额度；普通后台守护只消耗系统资源。正常且没有恢复动作时保持静默，恢复异常或需要用户操作时通知。重建后的恢复要等到下一次每日任务，或手动执行命令。

恢复依赖平台仍能恢复这些持久文件、启动 Computer 终端和提供原有 sudo 权限。每日任务是模型驱动的恢复入口，不是平台提供的确定性开机钩子；删除持久数据或登录身份失效需要用户重新授权。未执行整台 Computer 的重启或销毁重建测试。

## 验证状态（2026-10-08）

CPA 模型列表、文本回复和 SSE 均已验证；适配器和 Tailscale 进程异常退出后，守护恢复了原有 Tailnet 身份、IP 和 CPA 调用。NAS 容器启动检查通过。

Tailscale 进程重启后，SSH 在 banner exchange 阶段超时，原因尚未确定。Grok 自动安全审查拦截了后续 `sudo tailscale set --ssh`，要求用户在 Grok 内确认。每日任务已创建且启用，尚未验证一次完整的定时执行，因此普通重启和镜像重建恢复仍需验证，不能视为已完成。
