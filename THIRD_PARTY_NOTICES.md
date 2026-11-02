# 来源与第三方权利

本仓库整理既有 `blender-character-short` v25 通用 skill。冻结包中的脚本未作功能修改，源 ZIP SHA-256 和文件级差异见 `release/distribution-manifest.json`。版本和历史验证记录保留在 skill 文档中。本次更新保留最初公开版的许可处理方式，没有更换或扩大项目许可。

部分材质、轮廓与后处理实现根据 Huaxu 模型查看器的源公式或运行观察整理，不应据此主张拥有其上游实现、数据或美术资产的权利。例如 `scripts/smaa_cpu.py` 自述为 Huaxu `C69G59uD2.js` 三段 SMAA 的 NumPy 翻译，并保留其 `SOURCE_SHA256`：

```text
172188ea0193106745299323b5b2e2ac9cc8b7d33535e6d538798b1685dd8d9e
```

原有来源说明、来源哈希与适用范围均予保留；本次整理未独立确认这些来源是否允许再许可。因此不添加 MIT、Apache 或其他覆盖全部代码的许可证，也不将来源公式或源派生代码重新宣称为原创。对外复用或再分发前，使用者须确认适用权利与条款。

Blender、mmd_tools、NumPy、Pillow、imageio-ffmpeg、FFmpeg 与各自的外部依赖拥有独立的权利和许可要求。本仓库不打包这些软件、wheels、可执行文件或依赖源码。

角色模型、PMX/GLB、纹理、LUT、SMAA Area/Search 图、音频、源网页资源和角色专用配置不随本仓库分发。使用者须自行取得授权，保存原作者归属，并遵守模型、角色和资源的使用条款。本仓库没有授予这些资源的任何许可。

## 外部动作与场景资源

`source_motion.py` / `source_motion_layer.py` 处理用户另行提供的许可动作与节点层级；配套验证脚本仅生成自有合成旋转数据。既有 Stand02 动作和节点层级的外部再分发权尚未核实，原数据和提取后的数据均未发布。

独立的本地走近后接物试作用过 Khronos glTF Sample Assets 中的 [CesiumMan](https://github.com/KhronosGroup/glTF-Sample-Assets/blob/main/Models/CesiumMan/README.md)。其作者标注为 © 2017 Cesium，模型关联文件列为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；[官方许可文件](https://github.com/KhronosGroup/glTF-Sample-Assets/blob/main/Models/CesiumMan/LICENSE.md)另列徽标和商标的权利边界。这不构成对本仓库代码的统一许可。

本次通用发布没有附带 CesiumMan 模型、徽标、原始或提取后的骨架/动画，也没有发布该试作的角色专用重定向及组合代码，因此没有将其派生动作数据放入通用配置。需要此资源时从官方模型目录单独获取，保存实际版本、作者、许可、修改记录和所需署名；对提取、重定向、时间裁切等修改明确说明，不把动作资源的许可扩大到目标角色模型。

静态场景导入只包含通用文件校验和导入逻辑。外部场景、纹理及授权文件不随包分发；自制临时测试几何也不作为资源包发布。
