# mythril-agent-bgm

[English](./README.md) | 中文

> "AI fatigue is real." - [Siddhant Khare](https://siddhantkhare.com/writing/ai-fatigue-is-real)

`mythril-agent-bgm` 是一个跨平台 CLI 工具，为 AI 协作编程提供声音反馈。
当 AI 进入工作状态时循环播放工作音乐；任务完成时播放结束提示音；会话结束时自动停止。

## 为什么

AI 编程很高效，但长时间使用会带来明显的注意力疲劳。
这个工具把不易感知的状态切换变成简单的声音提示：

- AI 正在工作时，循环播放 `work`
- 任务完成时，播放 `done`
- 会话结束时，自动停止播放

这样可以减少反复确认状态的心智负担，让长时间会话更轻松。

## 安装

```bash
pip install mythril-agent-bgm

# 升级
pip install -U mythril-agent-bgm
```

安装后可使用 `bgm` 命令。

## 快速开始

首次运行任意 `bgm` 命令时，会自动初始化用户配置目录并生成示例文件。

1. `bgm setup` - 为已检测到的 AI 工具安装 hooks/plugin
2. `bgm select` - 选择音乐配置（`default` 或你的自定义配置）
3. `bgm enable` - 开启自动 BGM

可选快速验证：

```bash
bgm play work 0
bgm stop
```

## 已支持集成

- Claude Code
- Cursor Agent
- Gemini CLI
- OpenCode（基于插件）

`bgm setup` 只会配置当前机器上已检测到的工具。

## 配置路径

- macOS/Linux: `~/.config/mythril-agent-bgm/`
- Windows: `%APPDATA%\mythril-agent-bgm\`

关键文件：

- `config.json` - 自定义 BGM 配置
- `selection.json` - 当前选择的配置和启用状态
- `sounds/` - 用户 `.mp3` 文件目录（平铺，不支持子目录）
- `bgm_player.pid` - 后台进程 PID
- `bgm_player.log` - 后台日志

## 自定义音乐

1. 把 `.mp3` 文件复制到用户 `sounds/` 目录。
2. 编辑用户 `config.json`：

```json
{
  "my_collection": {
    "work": ["my_song.mp3", "another.mp3"],
    "done": ["done.mp3"],
    "notification": ["ping.mp3"]
  }
}
```

3. 运行 `bgm select` 并选择 `my_collection`。

说明：

- 配置名称可自定义（`my_collection` 只是示例）
- 若同名，用户音频文件优先于内置文件
- 配置里仅支持文件名，不支持嵌套路径

## 常用命令

```bash
bgm play work 0          # 无限循环播放 work
bgm play work 3          # 播放 work 3 次
bgm play done            # 播放 done 一次
bgm play notification    # 播放 notification
bgm stop                 # 停止后台播放
bgm toggle               # 播放/停止切换
bgm select               # 选择配置
bgm setup                # 配置集成
bgm cleanup              # 清理集成变更
bgm enable               # 开启自动 BGM
bgm disable              # 关闭自动 BGM
```

## 故障排查

```bash
# 确认 pygame 已安装
pip show pygame

# 停止当前播放
bgm stop
```

如果仍有问题，请检查配置目录中的：

- `bgm_player.log`
- `bgm_player.pid`

## 卸载

```bash
pip uninstall mythril-agent-bgm
```

可选：手动删除用户配置目录。

## 开发

参见 [docs/Dev.md](docs/Dev.md)。
