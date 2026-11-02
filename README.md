# Blender Character Short Skill · v25

从已授权的 PMX 角色、角色映射和故事配置制作本地 Blender Eevee 短片的可移植 skill。包含导入、表演与分镜、接触诊断、材质与后处理、视频编码和检查脚本。

**完整全身动作复用、表演自然度和正常速度连续观看验收仍未完成。** 本轮 v25 证据来自同一角色、同一宿主和上下文；已有 8 秒相机 B 技术预览，20 秒主片和 10 秒纸飞机复用仍由 v22 制作。单独的 CesiumMan 走近后接物试作及专用代码没有并入此通用 skill。历史 v05 的双角色独立技术复用不能替代 v25 的独立验证。本次公开更新没有启动 Blender 或重新制作视频。

## 相比最初公开版的更新

- 可选静态、自包含 GLB 场景导入：按角色身高定位和缩放，绑定故事材质与实际文件哈希。
- 真实目标注视、向原注视控制返回、手部控制诊断和接触后的有限恢复调时。
- 明确映射的源动作旋转变化与静止支撑；仍不支持通用全身重定向或自然步行。
- 外部蓝图及其声明贴图的身份校验，以及可暂停、恢复的逐帧后处理预算。

## 内容

- [`blender-character-short/SKILL.md`](blender-character-short/SKILL.md)：skill 入口。
- [`references/production.md`](blender-character-short/references/production.md)：角色、故事和动作配置约定。
- [`references/execution.md`](blender-character-short/references/execution.md)：命令、阶段产物和恢复方式。
- [`references/validation.md`](blender-character-short/references/validation.md)：历史证据范围和未完成项。
- `blender-character-short/scripts/`：冻结 v25 的通用 Python 脚本，发布时保持原字节。
- [`release/distribution-manifest.json`](release/distribution-manifest.json)：来源 ZIP 哈希、文件清单、分发差异和排除项。数量用于完整性核查，不代表品质验收。
- [`release/validation.json`](release/validation.json)：本次上传前的聚焦检查结果。

原项目历史、制作日志和媒体不在本仓库。模型、纹理、PMX/GLB、`.blend`、视频、LUT、SMAA 查找图、依赖二进制和角色专用映射均须另行准备。

## 环境与安装

历史验证环境：Windows、Blender 4.5.15 LTS / Eevee、mmd_tools 4.5.14 源码与其配套 wheels、宿主 Python 3.14.7、NumPy 2.5.4、Pillow 13.0.0、imageio-ffmpeg 0.6.0 / FFmpeg 7.1。Blender 自带 Python 是另一套运行时，不能用宿主 Python 直接运行依赖 `bpy` 的脚本。Windows 协作执行锁尚未在其他系统验证。

将完整的 `blender-character-short` 文件夹放入所用助手的技能目录，或让助手直接读取其中的 `SKILL.md`。例如 Codex 的用户技能目录为 `$CODEX_HOME/skills`，未设置时通常为 `~/.codex/skills`。安装 skill 不会安装 Blender 或第三方依赖，也不包含可直接制作的角色资产。

## 使用

先阅读 production 和 execution 文档，准备已授权 PMX、mmd_tools 源码、角色与故事 JSON、适用材质资源、后处理配置和 LUT。需要 SMAA 时额外提供匹配源版本的 Area/Search 图。外部配置中的相对路径按进程工作目录解析。

在 PowerShell 中将下列变量设置为自己的实际路径；`$Skill` 指向仓库内的 `blender-character-short` 文件夹，`$Output` 使用独立的新输出目录：

```powershell
python "$Skill/scripts/run_short.py" --blender $Blender --asset $Pmx --mmd-source $MmdSource --dependencies $Deps --character $CharacterJson --story $StoryJson --post-config $PostJson --lut $LutPng --output $Output --variant A --width 640 --height 360 --samples 16
```

先完成低成本预览并检查真实结果。默认输出无声视频；解码通过、抽帧检查、连续观看和试听是不同的验证步骤。`references/jobs.example.json` 是旧 PNG 队列的示例，不会执行新的外部后处理链。通用配置示例和公式夹具不能代替角色专用输入。

已有依赖环境下，可在仓库根目录复查分发文件：

```powershell
python -B validation/validate_distribution.py --report release/validation.json
python -B -m unittest discover -s validation -p 'test_*.py'
```

分发检查编译脚本、解析 JSON、检查内部文档链接与敏感文件模式，并运行宿主 Python CLI 的帮助入口。聚焦测试使用临时生成的自有合成输入，检查静态 GLB 校验、依赖身份、旋转解码、注视/调时边界和后处理暂停恢复。均不加载角色或启动 Blender，不证明画质或自然表演。

## 已知限制

- 严格 HairHET/模板、透明深度与 MRT、环境贴图 HTTP 403，以及适用源 GPU 数值一致性仍未解决。
- 连续正常速度视觉验收和音频验收尚未完成；默认自动产物为静音。有限接触采样不能证明全网格、所有帧或子帧均无穿插。
- 恢复签名不覆盖所有间接资源。mmd_tools/wheels、材质配置引用的 GLB、贴图、蓝图和清单需要另行冻结并校验。
- v25 的静态 GLB 运行证据使用自制工作台，不代表第三方场景资产通过；完整全身动作复用、自然度、正常速度连续观看和音频验收仍未完成。
- 当前宿主已有 Blender 启动故障 `0xC0000022`，此次未启动 Blender。语法、CLI、合成输入和分发检查不等于 v25 整包独立制作通过。完整限制以 validation 文档为准。

## 来源与使用权

参见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本次发布没有为来源权利尚未确认的代码添加统一开源许可证。仓库公开可读不代表对代码、第三方公式、模型或其他资源授予额外使用权。
